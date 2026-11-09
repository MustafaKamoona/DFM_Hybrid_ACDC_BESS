"""Network oracle: every network-dependent quantity used by the study is obtained
from steady-state solutions of the validated PyDAE Topology-3 model.

* evaluate(...)          -- full operating point (grid import, losses, V, I, VSC loading).
* min_curtailment(...)   -- minimum uniform renewable curtailment fraction that removes
                            renewable-driven constraint violations (DC-side converters reduce
                            output under DC over-voltage / interface over-load). Common to every
                            strategy (network-security layer).
* deliverable(...)       -- network-deliverable BESS discharge / charge power P_net (Eqs.
                            grid_dis_max / grid_ch_max): the largest |P_B| for which no monitored
                            constraint is violated, or -- for a constraint already violated at
                            P_B = 0 -- not aggravated.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .network import Topology3, Injections
from .profiles import DayProfiles


@dataclass
class Realization:
    """Realized (or forecast) exogenous conditions for one interval."""
    mult_ac: float = 1.0
    mult_dc: float = 1.0
    P_pv: Optional[float] = None    # total available PV [kW]; None -> forecast
    P_wt: Optional[float] = None


def violation_measure(e):
    return float(np.sum(np.maximum(e, 0.0)))


class NetworkOracle:
    def __init__(self, net: Topology3, day: DayProfiles, wt_bus: str, P_rated_bess: float):
        self.net = net
        self.day = day
        self.wt_bus = wt_bus
        self.P_rated = P_rated_bess
        self.groups = net.exceedance_groups()

    # -------------------------------------------------------------- operating point
    def _point(self, k, P_B, alpha, real: Optional[Realization]):
        real = real or Realization()
        p_loads = self.net.load_params(self.day.tm[k], real.mult_ac, real.mult_dc)
        P_pv = self.day.P_pv[k] if real.P_pv is None else real.P_pv
        P_wt = self.day.P_wt[k] if real.P_wt is None else real.P_wt
        inj = Injections(P_B=P_B,
                         pv_kw={b: s * P_pv * (1.0 - alpha) for b, s in self.day.pv_shares.items()},
                         wt_kw={self.wt_bus: P_wt * (1.0 - alpha)})
        return p_loads, inj, P_pv, P_wt

    def evaluate(self, k, P_B=0.0, alpha=0.0, real: Optional[Realization] = None, full=False):
        p_loads, inj, P_pv, P_wt = self._point(k, P_B, alpha, real)
        ok = self.net.solve(self.net.apply_injections(p_loads, inj))
        meas = self.net.measure()
        e = self.net.exceedance(meas)
        out = {"ok": ok, "e": e, "P_MV0": meas["P_MV0"],
               "loss": self.net.losses_kw(meas, p_loads, inj),
               "P_curt": alpha * (P_pv + P_wt), "P_res_avail": P_pv + P_wt}
        if full:
            out["meas"] = meas
            out["demand"] = self.net.demand_totals(p_loads, self.net.dc_load_buses)
        return out

    def binding_group(self, e, base=None):
        d = e if base is None else e - base
        return max(self.groups, key=lambda g: d[self.groups[g]].max())

    # -------------------------------------------------------------- curtailment
    def min_curtailment(self, k, P_B=0.0, real: Optional[Realization] = None, tol=2e-3):
        r0 = self.evaluate(k, P_B, 0.0, real)
        v0 = violation_measure(r0["e"])
        if v0 <= 0.0 or r0["P_res_avail"] <= 1e-9:
            return 0.0, r0
        r1 = self.evaluate(k, P_B, 1.0, real)
        v1 = violation_measure(r1["e"])
        if v1 >= v0 - 1e-12:                 # violation not renewable-driven: curtailment cannot help
            return 0.0, r0
        lo, hi, rhi = 0.0, 1.0, r1
        while hi - lo > tol:
            mid = 0.5 * (lo + hi)
            rm = self.evaluate(k, P_B, mid, real)
            if violation_measure(rm["e"]) <= v1 + 1e-9:
                hi, rhi = mid, rm
            else:
                lo = mid
        return hi, rhi

    # -------------------------------------------------------------- deliverability
    def deliverable(self, k, side: int, alpha: float = 0.0, real: Optional[Realization] = None,
                    tol_kw: float = 0.25, P_max: Optional[float] = None):
        """side=+1 discharge, side=-1 charge. Returns (P_net >= 0, binding group or 'none')."""
        P_max = self.P_rated if P_max is None else P_max
        base = np.maximum(self.evaluate(k, 0.0, alpha, real)["e"], 0.0)

        def feasible(P):
            e = self.evaluate(k, side * P, alpha, real)["e"]
            return bool(np.all(e <= base + 1e-9)), e

        ok, e = feasible(P_max)
        if ok:
            return P_max, "none"
        lo, hi, e_hi = 0.0, P_max, e
        while hi - lo > tol_kw:
            mid = 0.5 * (lo + hi)
            ok, e = feasible(mid)
            if ok:
                lo = mid
            else:
                hi, e_hi = mid, e
        return lo, self.binding_group(e_hi, base)
