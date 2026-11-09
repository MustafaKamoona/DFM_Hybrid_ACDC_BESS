"""Forecast-error model and quantile-based uncertainty reserve.

Errors are stationary AR(1) Gaussian processes at the EMS resolution (unit variance,
correlation phi), scaled per source:
    PV   : P_pv  = max(0, P_pv_hat * (1 + s_pv * x_pv))                    (multiplicative)
    wind : P_wt  = clip(P_wt_hat + (s_wt*P_wt_hat + s_abs*P_wt_r) * x_wt, 0, P_wt_r)
    load : P_L   = P_L_hat * (1 + s_L * x_L)      independent processes for AC and DC demand
The BESS serves the DC subsystem, so its net forecast error (Eq. net_forecast_error) is
    eps_net = (P_dc - P_dc_hat) - (P_pv - P_pv_hat) - (P_wt - P_wt_hat)
(positive = more net demand than forecast -> more discharge needed).
Directional reserves (risk tolerance eps):
    P_res_dis = Q_{1-eps}( [eps_net]^+ ),   P_res_ch = Q_{1-eps}( [-eps_net]^+ )
so that Pr(eps_net <= P_res_dis) >= 1-eps and Pr(-eps_net <= P_res_ch) >= 1-eps.
"""
from dataclasses import dataclass

import numpy as np

from .config import UncertaintyParams
from .profiles import DayProfiles


def ar1(rng, n_steps, n_paths, phi):
    x = np.empty((n_paths, n_steps))
    x[:, 0] = rng.standard_normal(n_paths)
    s = np.sqrt(1.0 - phi ** 2)
    for k in range(1, n_steps):
        x[:, k] = phi * x[:, k - 1] + s * rng.standard_normal(n_paths)
    return x


@dataclass
class Scenarios:
    P_pv: np.ndarray        # (n, K) realized available PV [kW]
    P_wt: np.ndarray
    mult_ac: np.ndarray     # (n, K) AC demand multiplier
    mult_dc: np.ndarray
    eps_net: np.ndarray     # (n, K) DC-subsystem net forecast error [kW]
    eps_pv: np.ndarray
    eps_wt: np.ndarray
    eps_dc: np.ndarray


def sample_scenarios(day: DayProfiles, up: UncertaintyParams, wt_rated: float, n: int, seed: int) -> Scenarios:
    rng = np.random.default_rng(seed)
    K = len(day.tm)
    x_pv, x_wt, x_ac, x_dc = (ar1(rng, K, n, up.ar1_phi) for _ in range(4))
    P_pv = np.maximum(0.0, day.P_pv[None, :] * (1.0 + up.sigma_pv_rel * x_pv))
    sw = up.sigma_wt_rel * day.P_wt[None, :] + up.sigma_wt_abs_pu * wt_rated
    P_wt = np.clip(day.P_wt[None, :] + sw * x_wt, 0.0, wt_rated)
    mult_ac = 1.0 + up.sigma_load_rel * x_ac
    mult_dc = 1.0 + up.sigma_load_rel * x_dc
    eps_pv = P_pv - day.P_pv[None, :]
    eps_wt = P_wt - day.P_wt[None, :]
    eps_dc = (mult_dc - 1.0) * day.P_dc[None, :]
    eps_net = eps_dc - eps_pv - eps_wt
    return Scenarios(P_pv, P_wt, mult_ac, mult_dc, eps_net, eps_pv, eps_wt, eps_dc)


def reserve_quantiles(eps_net: np.ndarray, eps_risk: float):
    """Directional (1-eps) quantiles of the positive / negative parts, per interval."""
    pos = np.maximum(eps_net, 0.0)
    neg = np.maximum(-eps_net, 0.0)
    return np.quantile(pos, 1.0 - eps_risk, axis=0), np.quantile(neg, 1.0 - eps_risk, axis=0)


def reserve_gaussian_reference(day: DayProfiles, up: UncertaintyParams, wt_rated: float, eps_risk: float):
    """Analytical reference ignoring the (small) truncation at 0: eps_net ~ N(0, sigma_net^2),
    so Q_{1-eps}([eps]^+) = sigma_net * Phi^{-1}(1-eps) for eps < 0.5."""
    from scipy.stats import norm
    s_pv = up.sigma_pv_rel * day.P_pv
    s_wt = up.sigma_wt_rel * day.P_wt + up.sigma_wt_abs_pu * wt_rated
    s_dc = up.sigma_load_rel * day.P_dc
    s_net = np.sqrt(s_pv ** 2 + s_wt ** 2 + s_dc ** 2)
    return s_net * norm.ppf(1.0 - eps_risk), s_net
