"""Nominal 24-h operating trajectory shared by every strategy.

* Demand: Load Case 3 of the validated benchmark (hourly residential / industrial /
  commercial factors and charger profiles from cigre_lv.xlsx, linearly interpolated
  by the original tool). Evaluated at the midpoint of each 15-min interval.
* PV (new): clear-sky output for Seville on a representative spring day
  (Haurwitz clear-sky GHI, horizontal modules, constant performance ratio),
  distributed over the DC load buses in proportion to their Case-3 DC rating.
* Wind (new): diurnal hub-height wind-speed profile mapped through a standard
  cubic power curve (cut-in / rated / cut-out).
* Tariff: 3-period time-of-use energy price.
"""
from dataclasses import dataclass
from typing import Dict

import numpy as np

from .config import RenewableParams, EMSParams


def time_grid(ems: EMSParams):
    """Interval start times [h] and midpoints [h] of the 24-h day."""
    t0 = np.arange(ems.n_steps_day) * ems.dt_h
    return t0, t0 + 0.5 * ems.dt_h


def clear_sky_ghi(t_solar_h, latitude_deg, day_of_year):
    """Haurwitz clear-sky global horizontal irradiance [W/m2] (solar time)."""
    phi = np.deg2rad(latitude_deg)
    decl = np.deg2rad(23.45) * np.sin(2 * np.pi * (284 + day_of_year) / 365.0)
    omega = np.deg2rad(15.0 * (np.asarray(t_solar_h) - 12.0))
    cos_z = np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(omega)
    ghi = np.where(cos_z > 0.0, 1098.0 * cos_z * np.exp(-0.057 / np.maximum(cos_z, 1e-6)), 0.0)
    return ghi


def pv_profile_kw(t_h, ren: RenewableParams):
    ghi = clear_sky_ghi(t_h, ren.latitude_deg, ren.day_of_year)
    return ren.pv_rated_kwp * ren.pv_performance_ratio * ghi / 1000.0


def wind_speed(t_h, ren: RenewableParams):
    return ren.wt_v_mean + ren.wt_v_amp * np.cos(2 * np.pi * (np.asarray(t_h) - ren.wt_t_peak_h) / 24.0)


def wind_power_kw(v, ren: RenewableParams):
    v = np.asarray(v, dtype=float)
    p = np.zeros_like(v)
    a = (v >= ren.wt_v_cut_in) & (v < ren.wt_v_rated)
    p[a] = ren.wt_rated_kw * (v[a] ** 3 - ren.wt_v_cut_in ** 3) / (ren.wt_v_rated ** 3 - ren.wt_v_cut_in ** 3)
    p[(v >= ren.wt_v_rated) & (v < ren.wt_v_cut_out)] = ren.wt_rated_kw
    return p


def tou_price(t_h, ems: EMSParams):
    h = np.mod(np.asarray(t_h, dtype=float), 24.0)
    price = np.full(h.shape, ems.price_flat)
    price[h < 8.0] = ems.price_valley
    peak = ((h >= 10.0) & (h < 14.0)) | ((h >= 18.0) & (h < 22.0))
    price[peak] = ems.price_peak
    return price


def pv_bus_shares(net_model, ren: RenewableParams) -> Dict[str, float]:
    """PV allocation over DC buses proportional to the Case-3 DC load rating (Pdc kW)."""
    pdc = net_model.load.df_loads_dc["Pdc (kW)"]
    w = np.array([float(pdc.loc[b]) for b in ren.pv_buses])
    return dict(zip(ren.pv_buses, w / w.sum()))


@dataclass
class DayProfiles:
    t0: np.ndarray            # interval starts [h]
    tm: np.ndarray            # interval midpoints [h] (profile evaluation instants)
    P_ac: np.ndarray          # AC demand [kW]
    Q_ac: np.ndarray
    P_dc: np.ndarray          # DC demand [kW]
    P_pv: np.ndarray          # available PV [kW]
    P_wt: np.ndarray          # available wind [kW]
    price: np.ndarray         # EUR/kWh
    pv_shares: Dict[str, float]

    @property
    def P_load(self):
        return self.P_ac + self.P_dc

    @property
    def P_res(self):
        return self.P_pv + self.P_wt


def build_day(net_model, ren: RenewableParams, ems: EMSParams) -> DayProfiles:
    t0, tm = time_grid(ems)
    P_ac, Q_ac, P_dc = [], [], []
    for h in tm:
        d = net_model.demand_totals(net_model.load_params(h), net_model.dc_load_buses)
        P_ac.append(d["P_ac"]); Q_ac.append(d["Q_ac"]); P_dc.append(d["P_dc"])
    return DayProfiles(t0=t0, tm=tm, P_ac=np.array(P_ac), Q_ac=np.array(Q_ac), P_dc=np.array(P_dc),
                       P_pv=pv_profile_kw(tm, ren), P_wt=wind_power_kw(wind_speed(tm, ren), ren),
                       price=tou_price(tm, ems), pv_shares=pv_bus_shares(net_model, ren))
