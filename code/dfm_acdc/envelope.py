"""Dynamic flexibility envelope (Section 3 of the paper).

    F_en   : energy/health-limited sustainable power over the support horizon H_f
    F_deg  : degradation-feasible power (largest P whose sustained H_f use stays within D_allow)
    F_net  : network-deliverable power (from the PyDAE oracle, see oracle.py)
    F_phys = F_en  ∩ F_deg ∩ F_net     ->  P_flex = min(P_en, P_deg, P_net) per side
    F_safe = [-max(0, P_flex_ch - P_res_ch), max(0, P_flex_dis - P_res_dis)]
Active limiter: argmin over {en, deg, net}; reported as 'rated' when none is below the
converter rating (i.e. the static nameplate bound is the active one).
"""
from dataclasses import dataclass

import numpy as np

from .config import BESSParams, DFMParams
from .degradation import XuDegradation

LIMITERS = ("en", "deg", "net")


def energy_flex(soc, E_use, b: BESSParams, H_f):
    P_dis = min(b.P_rated_kw, max(soc - b.soc_min, 0.0) * E_use * b.eta_dis / H_f)
    P_ch = min(b.P_rated_kw, max(b.soc_max - soc, 0.0) * E_use / (b.eta_ch * H_f))
    return P_dis, P_ch


def degradation_allowance(deg: XuDegradation, F_k, F_cyc_day, dfm: DFMParams):
    """Remaining cycle-degradation allowance of the current day in SOH units:
    D_max_cyc = L'(F) * N_ref * G(DoD_ref), D_rem = D_max_cyc - D_cyc,k, D_allow = D_rem.
    (Calendar aging is not dispatch-controllable and is excluded from the allowance.)"""
    dL = float(deg.dL(F_k))
    F_budget = dfm.N_ref_cycles_per_day * deg.reference_cycle_F(dfm.DoD_ref)
    D_max = dL * F_budget
    D_used = dL * F_cyc_day
    return max(D_max - D_used, 0.0), D_max, D_used


def _deg_cost(deg, soc, E_use, b, H_f, F_k, P, side):
    """Degradation (SOH units) incurred if P were sustained for H_f from SOC (one side)."""
    if side > 0:
        dsoc = min(P * H_f / (b.eta_dis * E_use), max(soc - b.soc_min, 0.0))
        soc_end = soc - dsoc
    else:
        dsoc = min(b.eta_ch * P * H_f / E_use, max(b.soc_max - soc, 0.0))
        soc_end = soc + dsoc
    return float(deg.dL(F_k)) * float(deg.dF_cycle(soc, soc_end))


def degradation_flex(deg, soc, E_use, b: BESSParams, H_f, F_k, D_allow, tol=1e-3):
    out = []
    for side in (+1, -1):
        if _deg_cost(deg, soc, E_use, b, H_f, F_k, b.P_rated_kw, side) <= D_allow:
            out.append(b.P_rated_kw)
            continue
        lo, hi = 0.0, b.P_rated_kw
        while hi - lo > tol:
            mid = 0.5 * (lo + hi)
            if _deg_cost(deg, soc, E_use, b, H_f, F_k, mid, side) <= D_allow:
                lo = mid
            else:
                hi = mid
        out.append(lo)
    return out[0], out[1]


@dataclass
class Envelope:
    P_en_dis: float
    P_en_ch: float
    P_deg_dis: float
    P_deg_ch: float
    P_net_dis: float
    P_net_ch: float
    P_res_dis: float
    P_res_ch: float
    P_rated: float

    @property
    def P_flex_dis(self):
        return min(self.P_en_dis, self.P_deg_dis, self.P_net_dis)

    @property
    def P_flex_ch(self):
        return min(self.P_en_ch, self.P_deg_ch, self.P_net_ch)

    @property
    def P_safe_dis(self):
        return max(0.0, self.P_flex_dis - self.P_res_dis)

    @property
    def P_safe_ch(self):
        return max(0.0, self.P_flex_ch - self.P_res_ch)

    def limiter(self, side, tol=1e-6):
        vals = ((self.P_en_dis, self.P_deg_dis, self.P_net_dis) if side > 0
                else (self.P_en_ch, self.P_deg_ch, self.P_net_ch))
        m = min(vals)
        if m >= self.P_rated - tol:
            return "rated"
        return LIMITERS[int(np.argmin(vals))]

    def as_dict(self):
        return {"P_en_dis": self.P_en_dis, "P_en_ch": self.P_en_ch,
                "P_deg_dis": self.P_deg_dis, "P_deg_ch": self.P_deg_ch,
                "P_net_dis": self.P_net_dis, "P_net_ch": self.P_net_ch,
                "P_res_dis": self.P_res_dis, "P_res_ch": self.P_res_ch,
                "P_flex_dis": self.P_flex_dis, "P_flex_ch": self.P_flex_ch,
                "P_safe_dis": self.P_safe_dis, "P_safe_ch": self.P_safe_ch,
                "lim_dis": self.limiter(+1), "lim_ch": self.limiter(-1)}


def build_envelope(b: BESSParams, deg: XuDegradation, dfm: DFMParams, soc, E_model, F_k, F_cyc_day,
                   P_net_dis, P_net_ch, P_res_dis, P_res_ch,
                   use_deg=True, use_net=True, use_res=True):
    H_f = dfm.H_f_h
    P_en_dis, P_en_ch = energy_flex(soc, E_model, b, H_f)
    if use_deg:
        D_allow, _, _ = degradation_allowance(deg, F_k, F_cyc_day, dfm)
        P_deg_dis, P_deg_ch = degradation_flex(deg, soc, E_model, b, H_f, F_k, D_allow)
    else:
        P_deg_dis = P_deg_ch = b.P_rated_kw
    if not use_net:
        P_net_dis = P_net_ch = b.P_rated_kw
    if not use_res:
        P_res_dis = P_res_ch = 0.0
    return Envelope(P_en_dis, P_en_ch, P_deg_dis, P_deg_ch, P_net_dis, P_net_ch,
                    P_res_dis, P_res_ch, b.P_rated_kw)
