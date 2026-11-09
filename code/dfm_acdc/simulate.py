"""Closed-loop 24-h simulation of one strategy under one (nominal or sampled) realization.

At every 15-min interval k:
  1. envelope F_k (energy, degradation, network, reserve) from the current BESS state;
  2. rolling-horizon EMS -> scheduled P_B^sched (first step applied);
  3. real-time correction of the realized DC-subsystem net forecast error within the
     strategy's real-time bounds (B1/B2: rating + SOC; DFM family: physical envelope + SOC);
  4. true BESS update (SOC, SOH via the online degradation estimator);
  5. network-security layer on the PyDAE model with realized demand/renewables
     (minimum renewable curtailment) -> grid import, losses, V/I/VSC loading.
Network quantities depending only on the forecast (P_net, curtailment model, base import)
are precomputed once per forecast (they do not depend on the strategy or realization).
"""
import time
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd

from .config import (NetworkParams, RenewableParams, BESSParams, DegradationParams, DFMParams,
                     UncertaintyParams, EMSParams)
from .network import Topology3
from .oracle import NetworkOracle, Realization
from .profiles import build_day
from .degradation import XuDegradation
from .bess import BESSPlant, soc_feasible_bounds
from .envelope import build_envelope, degradation_allowance
from .ems import Strategy, solve_ems, strategies
from .uncertainty import sample_scenarios, reserve_quantiles


@dataclass
class StudyParams:
    net: NetworkParams
    ren: RenewableParams
    b: BESSParams
    degp: DegradationParams
    dfm: DFMParams
    unc: UncertaintyParams
    ems: EMSParams


def default_params(**over):
    p = StudyParams(NetworkParams(), RenewableParams(), BESSParams(), DegradationParams(),
                    DFMParams(), UncertaintyParams(), EMSParams())
    for k, v in over.items():
        setattr(p, k, v)
    return p


class Study:
    """Holds the network, the nominal day, the oracle and the forecast-only precomputation."""

    def __init__(self, sp: Optional[StudyParams] = None, net_model: Optional[Topology3] = None):
        self.sp = sp or default_params()
        self.net = net_model or Topology3(self.sp.net)
        self.day = build_day(self.net, self.sp.ren, self.sp.ems)
        self.oracle = NetworkOracle(self.net, self.day, self.sp.ren.wt_bus, self.sp.b.P_rated_kw)
        self.deg = XuDegradation(self.sp.degp, self.sp.b.soc_max, self.sp.b.soc_min)
        self.pre = None

    # ---------------------------------------------------------------- precomputation
    def precompute(self, dP=20.0, verbose=False):
        rows = []
        t0 = time.perf_counter()
        for k in range(self.sp.ems.n_steps_day):
            r0 = self.oracle.evaluate(k, 0.0, 0.0)
            a0, ra = self.oracle.min_curtailment(k, 0.0)
            C0 = ra["P_curt"]
            _, rp = self.oracle.min_curtailment(k, +dP)
            _, rm = self.oracle.min_curtailment(k, -dP)
            g_dis = float(np.clip((rp["P_curt"] - C0) / dP, 0.0, 1.0))
            g_ch = float(np.clip((C0 - rm["P_curt"]) / dP, 0.0, 1.0))
            Pd, gd = self.oracle.deliverable(k, +1, a0, tol_kw=self.sp.net.tol_kw)
            Pc, gc = self.oracle.deliverable(k, -1, a0, tol_kw=self.sp.net.tol_kw)
            rows.append({"k": k, "t_h": self.day.t0[k], "P_grid0": r0["P_MV0"], "loss0": r0["loss"],
                         "alpha0": a0, "C0": C0, "g_dis": g_dis, "g_ch": g_ch,
                         "P_net_dis": Pd, "P_net_ch": Pc, "net_bind_dis": gd, "net_bind_ch": gc,
                         "P_res_avail": self.day.P_res[k]})
            if verbose and k % 12 == 0:
                print(f"  k={k:2d}  P_net_dis={Pd:6.1f} ({gd})  P_net_ch={Pc:6.1f} ({gc})  C0={C0:5.1f}")
        self.pre = pd.DataFrame(rows)
        self.pre_time = time.perf_counter() - t0
        return self.pre

    def load_or_precompute(self, path, verbose=False):
        """Forecast-only network precomputation, cached to CSV (identical for every strategy,
        Monte Carlo trial and BESS-state sensitivity case)."""
        import os
        if os.path.exists(path):
            self.pre = pd.read_csv(path)
        else:
            self.precompute(verbose=verbose)
            self.pre.to_csv(path, index=False)
        return self.pre

    def reserve(self, eps_risk=None, n=None, seed=12345):
        """Directional reserve per interval from the forecast-error distribution
        (independent sample set from the Monte Carlo evaluation set)."""
        eps_risk = self.sp.dfm.eps_risk if eps_risk is None else eps_risk
        n = self.sp.unc.n_samples_reserve if n is None else n
        sc = sample_scenarios(self.day, self.sp.unc, self.sp.ren.wt_rated_kw, n, seed)
        return reserve_quantiles(sc.eps_net, eps_risk)

    # ---------------------------------------------------------------- one day
    def run(self, st: Strategy, real: Optional[dict] = None, P_res=None, soc0=None, soh0=None,
            record_envelope=True):
        """real: None (nominal) or dict with arrays P_pv, P_wt, mult_ac, mult_dc, eps_net (len K)."""
        sp, day, pre = self.sp, self.day, self.pre
        b, ems, dfm = sp.b, sp.ems, sp.dfm
        K, dt = ems.n_steps_day, ems.dt_h
        if P_res is None:
            P_res = (np.zeros(K), np.zeros(K))
        plant = BESSPlant(b, self.deg)
        plant.reset(soc0, soh0)
        data = {"b": b, "ems": ems, "dfm": dfm, "deg": self.deg, "price": day.price,
                "P_grid0": pre["P_grid0"].values, "P_res_avail": pre["P_res_avail"].values,
                "C0": pre["C0"].values, "g_dis": pre["g_dis"].values, "g_ch": pre["g_ch"].values,
                "P_net_dis": pre["P_net_dis"].values, "P_net_ch": pre["P_net_ch"].values,
                "P_res_dis": P_res[0], "P_res_ch": P_res[1],
                "lambda_deg": ems.bess_cost_eur_per_kwh * b.E_rated_kwh / (1.0 - sp.degp.soh_eol),
                "soc_target": b.soc_0 if soc0 is None else soc0}
        logs = []
        for k in range(K):
            s = plant.state
            E_true = plant.E_use
            E_model = E_true if st.health_aware else b.E_rated_kwh
            rec = {"k": k, "t_h": day.t0[k], "soc": s.soc, "soh": s.soh, "F": s.F, "E_use": E_true}
            # ---------------- envelope (reference DFM envelope logged for every strategy)
            D_allow, D_max, D_used = degradation_allowance(self.deg, s.F, s.F_cyc_day, dfm)
            env_ref = build_envelope(b, self.deg, dfm, s.soc, E_true, s.F, s.F_cyc_day,
                                     pre["P_net_dis"][k], pre["P_net_ch"][k], P_res[0][k], P_res[1][k])
            env_st = None
            if st.use_bess and st.envelope:
                env_st = build_envelope(b, self.deg, dfm, s.soc, E_model, s.F, s.F_cyc_day,
                                        pre["P_net_dis"][k], pre["P_net_ch"][k], P_res[0][k], P_res[1][k],
                                        use_deg=st.deg_limit, use_net=st.network, use_res=st.reserve)
            if record_envelope:
                rec.update({f"ref_{n}": v for n, v in env_ref.as_dict().items()})
                if env_st is not None:
                    rec.update({f"st_{n}": v for n, v in env_st.as_dict().items()})
            rec.update({"D_allow": D_allow, "D_max_cyc": D_max, "D_used_cyc": D_used})
            # ---------------- EMS
            if st.use_bess:
                sol = solve_ems(st, k, s.soc, E_model, s.F, s.F_cyc_day, data, env_st)
                P_sched = sol["P_B"] if sol["ok"] else 0.0
                rec.update({"t_solve": sol["t_solve"], "ems_ok": sol["ok"], "ems_status": sol["status"]})
            else:
                P_sched = 0.0
                rec.update({"t_solve": 0.0, "ems_ok": True, "ems_status": 0})
            # ---------------- realization and real-time correction
            if real is None:
                rz, eps = Realization(), 0.0
            else:
                rz = Realization(real["mult_ac"][k], real["mult_dc"][k], real["P_pv"][k], real["P_wt"][k])
                eps = float(real["eps_net"][k])
            rt_net_limited = False
            if st.use_bess:
                lo, hi = soc_feasible_bounds(s.soc, E_true, b, dt)
                if env_st is not None:
                    # battery-side physical limits (sustained energy over H_f, degradation)
                    lo = max(lo, -min(env_st.P_en_ch, env_st.P_deg_ch))
                    hi = min(hi, min(env_st.P_en_dis, env_st.P_deg_dis))
                lo, hi = min(lo, 0.0), max(hi, 0.0)
                P_base = float(np.clip(P_sched, lo, hi))
                P_act = float(np.clip(P_sched + eps, lo, hi))
                if env_st is not None and st.network and abs(P_act - P_base) > 1e-9:
                    # network deliverability of the correction on the realized (measured) state:
                    # it must not create or aggravate any violation w.r.t. the scheduled point
                    e_ref = np.maximum(self.oracle.evaluate(k, P_base, 0.0, rz)["e"], 0.0)
                    feas = lambda P: bool(np.all(self.oracle.evaluate(k, P, 0.0, rz)["e"] <= e_ref + 1e-9))
                    if not feas(P_act):
                        rt_net_limited = True
                        lam_lo, lam_hi = 0.0, 1.0
                        while (lam_hi - lam_lo) * abs(P_act - P_base) > self.sp.net.tol_kw:
                            lam = 0.5 * (lam_lo + lam_hi)
                            if feas(P_base + lam * (P_act - P_base)):
                                lam_lo = lam
                            else:
                                lam_hi = lam
                        P_act = P_base + lam_lo * (P_act - P_base)
            else:
                P_act = 0.0
            dev = (P_sched + eps) - P_act
            brec = plant.step(P_act, dt)
            # ---------------- network-security layer (PyDAE, realized conditions)
            alpha, rn = self.oracle.min_curtailment(k, P_act, rz)
            r_full = self.oracle.evaluate(k, P_act, alpha, rz, full=True)
            meas = r_full["meas"]
            e = r_full["e"]
            G = self.oracle.groups
            rec.update({"P_sched": P_sched, "eps_net": eps, "P_B": P_act, "dev": dev,
                        "rt_net_limited": rt_net_limited,
                        "P_dis": brec["P_dis"], "P_ch": brec["P_ch"], "soc_next": brec["soc_next"],
                        "E_bess_loss": brec["E_loss"], "dF_cyc": brec["dF_cyc"], "dF_cal": brec["dF_cal"],
                        "dD": brec["dD"], "soc_clip": brec["clip"],
                        "alpha": alpha, "P_curt": r_full["P_curt"], "P_res_avail_real": r_full["P_res_avail"],
                        "P_MV0": r_full["P_MV0"], "loss": r_full["loss"], "price": day.price[k],
                        "P_ac": r_full["demand"]["P_ac"], "P_dc": r_full["demand"]["P_dc"],
                        "e_max": float(e.max()),
                        "V_min": float(meas["V_ln"].min()), "V_max": float(meas["V_ln"].max()),
                        "Vdc_min": float(meas["V_dc"].min()), "Vdc_max": float(meas["V_dc"].max()),
                        "I_R01": float(meas["I_feeder"][0].max()), "I_I01": float(meas["I_feeder"][1].max()),
                        "I_C01": float(meas["I_feeder"][2].max()), "I_dc_max": float(meas["I_dc"].max()),
                        "S_H01": float(meas["s_vsc"][0]),
                        "util_vsc_max": float(np.max(meas["s_vsc"] / self.net._vsc_rating)),
                        "pf_ok": r_full["ok"]})
            for gname, sl in G.items():
                rec[f"e_{gname}"] = float(e[sl].max())
            logs.append(rec)
        log = pd.DataFrame(logs)
        log.attrs["strategy"] = st.name
        return log


def _envelope_stats(log: pd.DataFrame):
    """Mean envelope widths and active-limiter shares (strategy's own envelope if it has one,
    otherwise the reference DFM envelope evaluated along its trajectory)."""
    pre = "st_" if "st_P_flex_dis" in log.columns else ("ref_" if "ref_P_flex_dis" in log.columns else None)
    if pre is None:
        return {}
    out = {f"mean_{c}_kW": float(log[pre + c].mean()) for c in ("P_flex_dis", "P_flex_ch", "P_safe_dis", "P_safe_ch")}
    for side in ("dis", "ch"):
        vc = log[f"{pre}lim_{side}"].value_counts(normalize=True)
        for lim in ("en", "deg", "net", "rated"):
            out[f"share_lim_{side}_{lim}"] = float(vc.get(lim, 0.0))
    out["envelope_source"] = pre.rstrip("_")
    return out


def summarize(log: pd.DataFrame, study: Study, soh0=None):
    sp = study.sp
    b, dt = sp.b, sp.ems.dt_h
    soh0 = b.soh_0 if soh0 is None else soh0
    soc_series = np.concatenate([log["soc"].values, [log["soc_next"].values[-1]]])
    soh_rf, Fc, Fcal = study.deg.soh_after(soh0, soc_series, dt)
    E_thr = float(np.sum(log["P_dis"] + log["P_ch"]) * dt)
    E_res = float(np.sum(log["P_res_avail_real"]) * dt)
    E_curt = float(np.sum(log["P_curt"]) * dt)
    viol = log["e_max"].values > 1e-6
    imp = np.maximum(log["P_MV0"].values, 0.0)
    exp_ = np.maximum(-log["P_MV0"].values, 0.0)
    dE_term = float((log["soc"].values[0] - log["soc_next"].values[-1]) * log["E_use"].values[-1])
    dE_grid_term = dE_term / b.eta_ch if dE_term > 0 else dE_term * b.eta_dis
    return {
        "strategy": log.attrs.get("strategy", ""),
        "E_grid_kWh": float(np.sum(imp) * dt),
        "cost_EUR": float(np.sum(log["price"].values * imp - sp.ems.price_export * exp_) * dt),
        "P_grid_peak_kW": float(imp.max()),
        "E_curt_kWh": E_curt,
        "eta_RES": 1.0 - E_curt / E_res if E_res > 0 else 1.0,
        "E_loss_kWh": float(np.sum(log["loss"]) * dt),
        "E_bess_loss_kWh": float(np.sum(log["E_bess_loss"])),
        "dSOH_rainflow": soh0 - soh_rf,
        "dSOH_online": float(np.sum(log["dD"])),
        "F_cyc_rainflow": Fc, "F_cal": Fcal, "F_cyc_online": float(np.sum(log["dF_cyc"])),
        "E_thr_kWh": E_thr,
        "N_EFC": E_thr / (2.0 * b.E_rated_kwh),
        "E_dev_kWh": float(np.sum(np.abs(log["dev"])) * dt),
        "n_viol_intervals": int(viol.sum()),
        "max_exceedance": float(log["e_max"].max()),
        "min_margin": float(-log["e_max"].max()),
        "soc_final": float(log["soc_next"].values[-1]),
        # battery energy below (+) / above (-) the initial level at the end of the day [kWh]
        "dE_terminal_kWh": dE_term,
        # terminal-corrected grid energy / cost: a deficit is restored from the grid (charging
        # efficiency) and a surplus credited (discharge efficiency), both at the valley price
        "E_grid_corr_kWh": float(np.sum(imp) * dt) + dE_grid_term,
        "cost_corr_EUR": float(np.sum(log["price"].values * imp - sp.ems.price_export * exp_) * dt)
                         + dE_grid_term * sp.ems.price_valley,
        "t_solve_mean_ms": float(log["t_solve"].mean() * 1e3),
        "t_solve_p95_ms": float(np.percentile(log["t_solve"], 95) * 1e3),
        "t_solve_max_ms": float(log["t_solve"].max() * 1e3),
        **_envelope_stats(log),
        "ems_fail": int((~log["ems_ok"].astype(bool)).sum()),
        "ems_time_limit_hits": int((log["ems_status"] == 1).sum()),
    }
