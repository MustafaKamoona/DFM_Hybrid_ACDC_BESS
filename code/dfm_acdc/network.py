"""Thin, fast wrapper around the validated (compiled, unmodified) PyDAE model of the
hybrid CIGRE LV Topology-3 (acdc_6w, decentralized P-V droop on 8 PQ VSCs, Vdc-Q
converter at I01-H01).

Nothing in the compiled model is changed. The DC-side BESS, PV and wind units are
represented as constant-power injections superposed on the existing constant-power
DC load inputs ``p_load_<bus>`` (exact, because the DC loads are constant-power).

Conventions
-----------
* P_B > 0 discharge (injection into the DC grid), P_B < 0 charge  [kW].
* p_vsc > 0 : power delivered to the AC side (DC->AC)            [kW].
* AC voltages are phase-to-neutral magnitudes |V_ph - V_n| [V] (the quantity a load sees);
  phase-to-ground magnitudes (the quantity reported by the original benchmark notebooks
  via pydae.grid_tools 'V_an_m') are also returned for regression purposes.
"""
import os
import sys
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np
import hjson

from .config import NetworkParams


@contextmanager
def _cwd(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def _import_topology3(model_dir):
    if model_dir not in sys.path:
        sys.path.insert(0, model_dir)
    with _cwd(model_dir):
        import cigre_eu_lv_acdc_6w  # compiled PyDAE model (validated, unmodified)
        import cigre_eu_lv_acdc_tools as tools  # original load-profile tool (validated, unmodified)
    return cigre_eu_lv_acdc_6w, tools


class _CappedNumpy:
    """numpy proxy whose zeros() returns a tiny array for very large requests (used only while
    constructing the compiled model, see Topology3.__init__)."""
    LIMIT = 2_000_000

    def __getattr__(self, name):
        return getattr(np, name)

    @staticmethod
    def zeros(shape, *args, **kwargs):
        if int(np.prod(shape)) > _CappedNumpy.LIMIT:
            return np.zeros(8, *args, **kwargs)
        return np.zeros(shape, *args, **kwargs)


@dataclass
class Injections:
    """DC-side injections for one operating point [kW]."""
    P_B: float = 0.0
    pv_kw: Dict[str, float] = field(default_factory=dict)   # per DC bus, after curtailment
    wt_kw: Dict[str, float] = field(default_factory=dict)   # per DC bus, after curtailment


class Topology3:
    def __init__(self, net: Optional[NetworkParams] = None):
        self.net = net or NetworkParams()
        mod, tools = _import_topology3(self.net.model_dir)
        self._mod, self.tools = mod, tools
        with _cwd(self.net.model_dir):
            # The compiled model pre-allocates ~1 GB of time-domain trajectory storage that the
            # steady-state solver (ini) never uses; cap those allocations during construction
            # only, so that many models can run in parallel. Numerics are untouched.
            mod.np = _CappedNumpy()
            try:
                self.model = mod.model()
            finally:
                mod.np = np
            self.model.load_xy_0("xy_0.json")
        # The generated solver passes MKL-PARDISO's internal handle array `pt` as a 64 x int32
        # buffer (256 bytes), but PARDISO uses it as 64 pointers (512 bytes on x64): a latent heap
        # overflow that corrupts memory under long repeated use. Provide a correctly sized buffer
        # and zero it completely before every solve (each ini() initializes and releases PARDISO).
        self.model.pt_ini = np.zeros(256, dtype=np.int32)
        self.model.pt_run = np.zeros(256, dtype=np.int32)
        self.xy0_ref = np.copy(self.model.xy_0)
        self.grid = hjson.load(open(os.path.join(self.net.model_dir, "cigre_eu_lv_acdc_6w.hjson")))
        self.ac_buses = [b["name"] for b in self.grid["buses"] if b["U_kV"] == 0.4]
        self.dc_buses = [b["name"] for b in self.grid["buses"] if b["U_kV"] == 0.8]
        self.ac_lines = [l for l in self.grid["lines"] if "dc" not in l["code"]]
        self.dc_lines = [l for l in self.grid["lines"] if "dc" in l["code"]]
        self.line_imax = {k: v["I_max"] for k, v in self.grid["line_codes"].items()}
        self.load = tools.loads()
        self.load.case = self.net.load_case
        self.load.read(os.path.join(self.net.model_dir, self.net.excel_file))
        self.dc_load_buses = list(self.load.df_loads_dc.index)
        self._build_index()
        self.n_solves = 0

    # ------------------------------------------------------------------ indexing
    def _build_index(self):
        m = self.model
        self._iu_ini = {n: i for i, n in enumerate(m.inputs_ini_list)}
        self._iu_run = {n: i for i, n in enumerate(m.inputs_run_list)}
        self._ip = {n: i for i, n in enumerate(m.params_list)}
        iy = {n: m.N_x + i for i, n in enumerate(m.y_run_list)}
        iz = {n: i for i, n in enumerate(m.outputs_list)}

        def vec(names, where):
            idx = np.array([where[n] for n in names], dtype=int)
            return idx

        # AC node voltages (phases 0..2 and neutral 3) -> from xy
        names = [f"V_{b}_{n}_{c}" for b in self.ac_buses for n in range(4) for c in "ri"]
        self._i_vac = vec(names, iy).reshape(len(self.ac_buses), 4, 2)
        names = [f"V_{b}_{n}_r" for b in self.dc_buses for n in range(2)]
        self._i_vdc = vec(names, iy).reshape(len(self.dc_buses), 2)
        names = [f"i_t_MV0_{a}_2_{ph}_{c}" for a in ("R01", "I01", "C01") for ph in range(3) for c in "ri"]
        self._i_ifeed = vec(names, iz).reshape(3, 3, 2)
        names = [f"i_l_{l['bus_j']}_{ph}_{l['bus_k']}_{ph}_{c}" for l in self.ac_lines for ph in range(3) for c in "ri"]
        self._i_iac = vec(names, iz).reshape(len(self.ac_lines), 3, 2)
        self._imax_ac = np.array([self.line_imax[l["code"]] for l in self.ac_lines])
        names = [f"i_l_{l['bus_j']}_0_{l['bus_k']}_0_r" for l in self.dc_lines]
        self._i_idc = vec(names, iz)
        self._i_pvsc = vec([f"p_vsc_{v}" for v in self.net.all_vscs], iz)
        self._i_pmv0 = iz["p_MV0"]
        self._i_qmv0 = iz["q_MV0"]
        self._vsc_rating = np.array([self.net.vsc_rating_kva[v] for v in self.net.all_vscs])
        self._q_inputs = {v: [f"q_vsc_{ph}_{v}" for ph in "abc"] for v in self.net.all_vscs}

    # ------------------------------------------------------------------ parameters
    def base_params(self) -> dict:
        n = self.net
        e = n.e_mv_pu * 11547.00
        p = {"K_xif": n.K_xif, "e_ao_m_MV0": e, "e_bo_m_MV0": e, "e_co_m_MV0": e}
        for b in n.droop_vscs:
            p[f"K_acdc_{b}"] = n.K_droop
        return p

    def load_params(self, h: float, mult_ac: float = 1.0, mult_dc: float = 1.0) -> dict:
        """Case-3 loads at profile hour h via the original tool, optionally scaled
        (uniform multiplicative demand realization for AC and DC loads)."""
        p = self.base_params()
        self.load.set_loads(h, p)
        if mult_ac != 1.0 or mult_dc != 1.0:
            for k in list(p.keys()):
                if k.startswith("p_load_") or k.startswith("q_load_"):
                    bus = k.split("_")[2]
                    if bus in self.dc_load_buses and k.startswith("p_load_") and k.count("_") == 2:
                        p[k] *= mult_dc
                    elif k.count("_") == 3:
                        p[k] *= mult_ac
        return p

    @staticmethod
    def demand_totals(p: dict, dc_load_buses) -> Dict[str, float]:
        """Total AC and DC demand [kW] contained in a parameter dict (before injections)."""
        p_ac = sum(v for k, v in p.items() if k.startswith("p_load_") and k.count("_") == 3) / 1e3
        q_ac = sum(v for k, v in p.items() if k.startswith("q_load_") and k.count("_") == 3) / 1e3
        p_dc = sum(p.get(f"p_load_{b}", 0.0) for b in dc_load_buses) / 1e3
        return {"P_ac": p_ac, "Q_ac": q_ac, "P_dc": p_dc}

    def apply_injections(self, p: dict, inj: Injections) -> dict:
        q = dict(p)
        bus = self.net.bess_bus
        q[f"p_load_{bus}"] = q.get(f"p_load_{bus}", 0.0) - inj.P_B * 1e3
        for b, v in inj.pv_kw.items():
            q[f"p_load_{b}"] = q.get(f"p_load_{b}", 0.0) - v * 1e3
        for b, v in inj.wt_kw.items():
            q[f"p_load_{b}"] = q.get(f"p_load_{b}", 0.0) - v * 1e3
        return q

    # ------------------------------------------------------------------ solving
    def _set(self, up: dict):
        m = self.model
        for k, v in up.items():
            hit = False
            i = self._iu_ini.get(k)
            if i is not None:
                m.u_ini[i] = v
                hit = True
            i = self._iu_run.get(k)
            if i is not None:
                m.u_run[i] = v
                hit = True
            if not hit:
                i = self._ip.get(k)
                if i is None:
                    raise KeyError(f"unknown input/parameter {k}")
                m.p[i] = v

    def solve(self, up: dict) -> bool:
        """Steady state (quasi-static operating point) from the stored initial guess, so
        every evaluation is independent of evaluation order."""
        m = self.model
        self._set(up)
        m.xy_0[:] = self.xy0_ref
        m.pt_ini[:] = 0
        ok = m.ini({}, {})
        self.n_solves += 1
        return bool(ok)

    # ------------------------------------------------------------------ measurements
    def measure(self) -> dict:
        m = self.model
        xy, z = m.xy, m.z
        v = xy[self._i_vac[..., 0]] + 1j * xy[self._i_vac[..., 1]]       # (nbus, 4)
        V_ln = np.abs(v[:, :3] - v[:, 3:4])
        V_lg = np.abs(v[:, :3])
        vdc = xy[self._i_vdc[:, 0]] - xy[self._i_vdc[:, 1]]
        ifd = np.hypot(z[self._i_ifeed[..., 0]], z[self._i_ifeed[..., 1]])  # (3 feeders, 3 ph)
        iac = np.hypot(z[self._i_iac[..., 0]], z[self._i_iac[..., 1]])      # (nline, 3)
        idc = np.abs(z[self._i_idc])
        p_vsc = z[self._i_pvsc] / 1e3
        q_vsc = np.array([sum(m.u_run[self._iu_run[n]] for n in self._q_inputs[v]) for v in self.net.all_vscs]) / 1e3
        return {
            "P_MV0": z[self._i_pmv0] / 1e3, "Q_MV0": z[self._i_qmv0] / 1e3,
            "V_ln": V_ln, "V_lg": V_lg, "V_dc": vdc,
            "I_feeder": ifd, "I_ac": iac, "I_dc": idc,
            "p_vsc": p_vsc, "s_vsc": np.hypot(p_vsc, q_vsc),
        }

    def exceedance(self, meas: dict) -> np.ndarray:
        """Normalized constraint exceedance vector (>0 = violated) for every monitored
        constraint: AC voltages (40 buses x 3 phases, lower & upper), feeder-head currents,
        AC line currents, DC line currents, DC voltages (lower & upper), VSC apparent power."""
        n = self.net
        V = meas["V_ln"].ravel() / n.V_nom_ln
        e_v_lo = n.V_min_pu - V
        e_v_hi = V - n.V_max_pu
        lim = np.array([n.I_feeder_max[a] for a in ("R01", "I01", "C01")])[:, None]
        e_if = (meas["I_feeder"] / lim - 1.0).ravel()
        e_iac = (meas["I_ac"] / self._imax_ac[:, None] - 1.0).ravel()
        e_idc = meas["I_dc"] / n.I_dc_line_max - 1.0
        vdc = meas["V_dc"] / n.V_dc_nom
        e_vdc_lo = n.V_dc_min_pu - vdc
        e_vdc_hi = vdc - n.V_dc_max_pu
        e_vsc = meas["s_vsc"] / self._vsc_rating - 1.0
        return np.concatenate([e_v_lo, e_v_hi, e_if, e_iac, e_idc, e_vdc_lo, e_vdc_hi, e_vsc])

    def exceedance_groups(self):
        nb, nl = len(self.ac_buses), len(self.ac_lines)
        sizes = [("V_ac_low", 3 * nb), ("V_ac_high", 3 * nb), ("I_feeder", 9), ("I_ac_line", 3 * nl),
                 ("I_dc_line", len(self.dc_lines)), ("V_dc_low", len(self.dc_buses)),
                 ("V_dc_high", len(self.dc_buses)), ("S_vsc", len(self.net.all_vscs))]
        out, s = {}, 0
        for name, k in sizes:
            out[name] = slice(s, s + k)
            s += k
        return out

    def losses_kw(self, meas: dict, p_loads: dict, inj: Injections) -> float:
        """Network losses = MV import + DC-side injections - AC demand - DC demand [kW]."""
        d = self.demand_totals(p_loads, self.dc_load_buses)
        gen = inj.P_B + sum(inj.pv_kw.values()) + sum(inj.wt_kw.values())
        return meas["P_MV0"] + gen - d["P_ac"] - d["P_dc"]

    # ------------------------------------------------------------------ regression
    def run_original_case(self, case: str = "Case 3", droop: bool = True):
        """Re-run the original 32-h benchmark experiment exactly as in
        cigre_eu_lv_acdc_6w_ini_Droop_T3_L2.ipynb (same model, same call sequence)."""
        mod, tools = self._mod, self.tools
        e = self.net.e_mv_pu * 11547.00
        params_0 = {"K_xif": 0.01, "e_ao_m_MV0": e, "e_bo_m_MV0": e, "e_co_m_MV0": e}
        if droop:
            for b in self.net.droop_vscs:
                params_0[f"K_acdc_{b}"] = 1e6
        load = tools.loads()
        load.case = case
        load.read(os.path.join(self.net.model_dir, self.net.excel_file))
        with _cwd(self.net.model_dir):
            model = mod.model()
            params = dict(params_0)
            Dt_large = 60 * 60
            load.set_loads(0, params)
            model.ini(params, "xy_0.json")
            for t in np.arange(0, 32 * Dt_large, Dt_large):
                model.Dt = Dt_large / 5
                model.run(t, params)
                load.set_loads(t / 3600 - 3, params)
                model.Dt = 1.0
                model.run(t + 2.0, params)
            model.post()
        return model
