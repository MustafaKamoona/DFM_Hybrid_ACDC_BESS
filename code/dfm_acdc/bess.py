"""DC-side BESS plant model (the "true" battery used by every strategy).

    P_B = P_dis - P_ch           (P_B > 0 discharge, P_B < 0 charge, never both)
    SOC_{k+1} = SOC_k + (eta_ch P_ch - P_dis / eta_dis) dt / E_use_k
    E_use_k   = SOH_k E_rated
    SOH_{k+1} = 1 - L(F_{k+1}),  F_{k+1} = F_k + dF_cyc + dF_cal   (online estimator)
"""
from dataclasses import dataclass, field
from typing import List

import numpy as np

from .config import BESSParams
from .degradation import XuDegradation


def split_power(P_B):
    return max(P_B, 0.0), max(-P_B, 0.0)


def soc_feasible_bounds(soc, E_use, b: BESSParams, dt_h, P_lo=None, P_hi=None):
    """Range of P_B that keeps SOC_{k+1} within [soc_min, soc_max] and |P_B| <= P_rated."""
    P_dis_max = (soc - b.soc_min) * E_use * b.eta_dis / dt_h
    P_ch_max = (b.soc_max - soc) * E_use / (b.eta_ch * dt_h)
    hi = min(b.P_rated_kw, max(P_dis_max, 0.0))
    lo = -min(b.P_rated_kw, max(P_ch_max, 0.0))
    if P_hi is not None:
        hi = min(hi, P_hi)
    if P_lo is not None:
        lo = max(lo, P_lo)
    return lo, hi


@dataclass
class BESSState:
    soc: float
    soh: float
    F: float                     # linearized degradation (Xu)
    F_cyc_day: float = 0.0       # cycle stress accumulated today
    E_thr: float = 0.0           # cumulative throughput [kWh] (charge + discharge, AC/DC terminal)


class BESSPlant:
    def __init__(self, b: BESSParams, deg: XuDegradation):
        self.b, self.deg = b, deg
        self.reset()

    def reset(self, soc0=None, soh0=None):
        soc0 = self.b.soc_0 if soc0 is None else soc0
        soh0 = self.b.soh_0 if soh0 is None else soh0
        self.state = BESSState(soc=soc0, soh=soh0, F=self.deg.F_from_soh(soh0))
        self.log: List[dict] = []

    @property
    def E_use(self):
        return self.state.soh * self.b.E_rated_kwh

    def step(self, P_B, dt_h):
        """Apply P_B for one interval (caller guarantees feasibility; SOC is clipped only to
        absorb floating-point round-off, and any clipping is recorded)."""
        b, s = self.b, self.state
        P_dis, P_ch = split_power(P_B)
        E_use = self.E_use
        dsoc = (b.eta_ch * P_ch - P_dis / b.eta_dis) * dt_h / E_use
        soc_raw = s.soc + dsoc
        soc_next = min(max(soc_raw, b.soc_min), b.soc_max)
        dF_cyc = float(self.deg.dF_cycle(s.soc, soc_next))
        dF_cal = float(self.deg.dF_calendar(0.5 * (s.soc + soc_next), dt_h))
        F_next = s.F + dF_cyc + dF_cal
        rec = {"soc": s.soc, "soc_next": soc_next, "soh": s.soh, "E_use": E_use,
               "P_B": P_B, "P_dis": P_dis, "P_ch": P_ch,
               "E_in": b.eta_ch * P_ch * dt_h, "E_out": P_dis / b.eta_dis * dt_h,
               "E_loss": (1 - b.eta_ch) * P_ch * dt_h + (1 / b.eta_dis - 1) * P_dis * dt_h,
               "dF_cyc": dF_cyc, "dF_cal": dF_cal,
               "dD": self.deg.L(F_next) - self.deg.L(s.F), "clip": soc_raw - soc_next}
        s.soc = soc_next
        s.F = F_next
        s.F_cyc_day += dF_cyc
        s.soh = 1.0 - float(self.deg.L(F_next))
        s.E_thr += (P_ch + P_dis) * dt_h
        self.log.append(rec)
        return rec
