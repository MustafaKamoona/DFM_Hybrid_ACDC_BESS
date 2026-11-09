"""Battery degradation model (published, not fitted in this study).

Xu, B., Oudalov, A., Ulbig, A., Andersson, G., Kirschen, D. S., "Modeling of lithium-ion
battery degradation for cell life assessment", IEEE Trans. Smart Grid 9(2):1131-1140, 2018
(LMO cell parameters), with the piecewise-linear cycle-depth representation of
Xu, Zhao, Zheng, Litvinov, Kirschen, "Factoring the cycle aging cost of batteries
participating in electricity markets", IEEE Trans. Power Syst. 33(2):2248-2259, 2018.

Linearized degradation (stress) F accumulates cycle and calendar terms:
    cycle i of depth delta_i, mean SOC sigma_i, count n_i in {1/2, 1}:
        F_cyc += n_i * Phi(delta_i) * S_sigma(sigma_i)
    calendar:  F_cal += k_t * dt * S_sigma(SOC)
    Phi(delta)   = 1 / (k_d1 * delta**k_d2 + k_d3)         (cycle-depth stress)
    S_sigma(s)   = exp(k_sigma * (s - sigma_ref))           (SOC stress)
Capacity fade (accumulated degradation D = 1 - SOH), including SEI-film formation:
    D = L(F) = 1 - alpha_sei*exp(-beta_sei*F) - (1 - alpha_sei)*exp(-F)
Temperature is taken at the reference value (stress factor = 1).

Online (per-interval) increment used by the envelope and the EMS -- cycle depth measured
from the upper SOC limit (Xu et al. TPWRS convention), each half cycle carrying half of
the full-cycle stress:
    delta = soc_max - SOC,   G(delta) = Phi(delta) * S_sigma(soc_max - delta/2)
    dF_cyc = 0.5 * | G(delta_{k+1}) - G(delta_k) |
so a full cycle from soc_max to depth delta and back costs exactly Phi(delta)S_sigma(mean SOC),
i.e. the rainflow value. Ex-post SOH is always evaluated with full rainflow counting.
"""
import numpy as np

from .config import DegradationParams


class XuDegradation:
    def __init__(self, p: DegradationParams = None, soc_max: float = 0.9, soc_min: float = 0.1):
        self.p = p or DegradationParams()
        self.soc_max, self.soc_min = soc_max, soc_min

    # ---------------------------------------------------------------- stress functions
    def phi(self, delta):
        d = np.maximum(np.asarray(delta, dtype=float), 0.0)
        out = np.zeros_like(d)
        nz = d > 1e-12
        out[nz] = 1.0 / (self.p.k_d1 * d[nz] ** self.p.k_d2 + self.p.k_d3)
        return out if out.ndim else float(out)

    def s_sigma(self, soc):
        return np.exp(self.p.k_sigma * (np.asarray(soc, dtype=float) - self.p.sigma_ref))

    def G(self, delta):
        """Stress of a full cycle starting at soc_max with depth delta."""
        delta = np.asarray(delta, dtype=float)
        return self.phi(delta) * self.s_sigma(self.soc_max - 0.5 * delta)

    # ---------------------------------------------------------------- capacity fade
    def L(self, F):
        a, b = self.p.alpha_sei, self.p.beta_sei
        return 1.0 - a * np.exp(-b * F) - (1.0 - a) * np.exp(-F)

    def dL(self, F):
        a, b = self.p.alpha_sei, self.p.beta_sei
        return a * b * np.exp(-b * F) + (1.0 - a) * np.exp(-F)

    def F_from_soh(self, soh):
        """Invert D = L(F) for the linearized degradation corresponding to a given SOH."""
        D = 1.0 - soh
        if D <= 0.0:
            return 0.0
        lo, hi = 0.0, 5.0
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if self.L(mid) < D:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    # ---------------------------------------------------------------- online increments
    def dF_cycle(self, soc_now, soc_next):
        d0 = self.soc_max - np.clip(soc_now, self.soc_min, self.soc_max)
        d1 = self.soc_max - np.clip(soc_next, self.soc_min, self.soc_max)
        return 0.5 * np.abs(self.G(d1) - self.G(d0))

    def dF_calendar(self, soc, dt_h):
        return self.p.k_t * dt_h * 3600.0 * self.s_sigma(soc)

    def reference_cycle_F(self, dod_ref):
        """Stress of one reference cycle of depth dod_ref starting at soc_max."""
        return float(self.G(dod_ref))

    # ---------------------------------------------------------------- piecewise-linear (EMS)
    def segment_costs(self):
        """Marginal stress per unit SOC of each of J equal cycle-depth segments over
        [0, soc_max - soc_min], from the shallowest (j=0) to the deepest. The lower convex
        envelope is used so that the LP/MILP representation is exact for a convex function
        (cheapest segments are always used first, as required by Xu et al. 2018)."""
        J = self.p.J_segments
        w = (self.soc_max - self.soc_min) / J
        edges = np.arange(J + 1) * w
        Gc = self.G(edges)
        slopes = np.diff(Gc) / w
        # lower convex envelope of the cumulative cost (pool adjacent violators on slopes)
        blocks = [[s, 1] for s in slopes]
        merged = []
        for s, n in blocks:
            merged.append([s, n])
            while len(merged) > 1 and merged[-2][0] > merged[-1][0]:
                s2, n2 = merged.pop()
                s1, n1 = merged.pop()
                merged.append([(s1 * n1 + s2 * n2) / (n1 + n2), n1 + n2])
        hull = np.concatenate([[s] * n for s, n in merged])
        return hull, w, slopes

    # ---------------------------------------------------------------- rainflow (ex post)
    @staticmethod
    def turning_points(x):
        x = np.asarray(x, dtype=float)
        if len(x) < 3:
            return x
        dx = np.diff(x)
        keep = [0]
        last_sign = 0
        for i in range(len(dx)):
            s = np.sign(dx[i])
            if s == 0:
                continue
            if last_sign != 0 and s != last_sign:
                keep.append(i)
            last_sign = s
        keep.append(len(x) - 1)
        tp = x[keep]
        return tp

    @classmethod
    def rainflow(cls, x):
        """ASTM E1049 three-point rainflow counting. Returns list of
        (range, mean, count) with count in {0.5, 1.0}."""
        tp = list(cls.turning_points(x))
        stack, cycles = [], []
        for p in tp:
            stack.append(p)
            while len(stack) >= 3:
                X = abs(stack[-1] - stack[-2])
                Y = abs(stack[-2] - stack[-3])
                if X < Y:
                    break
                if len(stack) == 3:
                    cycles.append((Y, 0.5 * (stack[-2] + stack[-3]), 0.5))
                    stack.pop(0)
                else:
                    cycles.append((Y, 0.5 * (stack[-2] + stack[-3]), 1.0))
                    last = stack.pop()
                    stack.pop()
                    stack.pop()
                    stack.append(last)
        for i in range(len(stack) - 1):
            cycles.append((abs(stack[i + 1] - stack[i]), 0.5 * (stack[i + 1] + stack[i]), 0.5))
        return cycles

    def F_rainflow(self, soc_series, dt_h):
        cyc = self.rainflow(soc_series)
        F_cyc = sum(n * float(self.phi(r)) * float(self.s_sigma(m)) for r, m, n in cyc if r > 0)
        soc = np.asarray(soc_series, dtype=float)
        soc_mid = 0.5 * (soc[1:] + soc[:-1])
        F_cal = float(np.sum(self.dF_calendar(soc_mid, dt_h)))
        return F_cyc, F_cal, cyc

    def soh_after(self, soh0, soc_series, dt_h):
        F0 = self.F_from_soh(soh0)
        F_cyc, F_cal, cyc = self.F_rainflow(soc_series, dt_h)
        return 1.0 - self.L(F0 + F_cyc + F_cal), F_cyc, F_cal
