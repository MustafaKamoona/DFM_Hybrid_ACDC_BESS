"""Single source of truth for every numerical parameter used in the study.

Groups:
  NetworkParams      -- the validated hybrid CIGRE LV Topology-3 (unchanged) plus
                        the constraint limits used to judge network feasibility.
  RenewableParams    -- DC-side PV and wind additions (new in this study).
  BESSParams         -- DC-side BESS rating, efficiencies, SOC limits, initial state.
  DegradationParams  -- published cycle/calendar aging model (Xu et al., 2018).
  DFMParams          -- support horizon, risk tolerance, degradation allowance.
  UncertaintyParams  -- forecast-error model.
  EMSParams          -- rolling-horizon EMS settings, tariff, objective weights.
  MCParams           -- Monte Carlo settings.

The parameter table of the paper is generated from these values
(experiments/11_tables_export.ipynb), so no value is typed twice.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple
import os

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(PKG_DIR))          # repository root
# External PyDAE model of the hybrid CIGRE LV Topology-3 (not distributed here; see external/README.md).
TOPOLOGY3_DIR = os.environ.get("DFM_TOPOLOGY3_DIR", os.path.join(ROOT_DIR, "external", "topology3"))
# A full re-run writes its results and diagnostic figures under output/, so that the released
# data in data/ and the final figures in figures/ are never overwritten.
RESULTS_DIR = os.path.join(ROOT_DIR, "output", "results")
FIG_DIR = os.path.join(ROOT_DIR, "output", "experiment_figures")


@dataclass
class NetworkParams:
    """Validated Topology-3 (droop on, Load Case 3) and feasibility limits."""
    model_dir: str = TOPOLOGY3_DIR
    excel_file: str = "cigre_lv.xlsx"
    load_case: str = "Case 3"            # code label; = "Load-2" (Topology paper), "Load Scenario-4" (IEEE Access)
    e_mv_pu: float = 1.04                # MV source e.m.f. used in the validated runs
    K_xif: float = 0.01
    K_droop: float = 1e6                 # identical droop gain for all 8 PQ VSCs (validated value)
    droop_vscs: Tuple[str, ...] = ("R01", "R10", "R14", "I02", "C01", "C09", "C11", "C16")
    vdc_former: str = "I01"              # I01-H01 Vdc-Q converter (DC slack / grid-forming interface)
    all_vscs: Tuple[str, ...] = ("I01", "R01", "C01", "R10", "R14", "I02", "C09", "C11", "C16")
    # Converter ratings [kVA]: 8 PQ VSCs from the IEEE Access study on the identical network;
    # the I01-H01 Vdc-forming converter is rated equal to its industrial transformer (150 kVA).
    vsc_rating_kva: Dict[str, float] = field(default_factory=lambda: {
        "I01": 150.0, "R01": 150.0, "R10": 50.0, "R14": 20.0, "I02": 50.0,
        "C01": 150.0, "C09": 20.0, "C11": 50.0, "C16": 20.0})
    # AC voltage limits: +/-5 % of 231 V (phase-to-neutral), as in the validated benchmark
    V_nom_ln: float = 231.0
    V_min_pu: float = 0.95
    V_max_pu: float = 1.05
    # Feeder-head (transformer secondary) current limits [A]: 724.6 / 231.9 / 434.8 A (R01/I01/C01); Industrial (I01): 160-kVA current basis
    I_feeder_max: Dict[str, float] = field(default_factory=lambda: {
        "R01": 500e3 / 690, "I01": 160e3 / 690, "C01": 300e3 / 690})
    # DC grid
    V_dc_nom: float = 800.0
    V_dc_min_pu: float = 0.95
    V_dc_max_pu: float = 1.05
    I_dc_line_max: float = 300.0
    # BESS point of connection (DC hub tying the S-, H- and D-subgrids and the Vdc-former)
    bess_bus: str = "H02"
    # numerical
    tol_kw: float = 0.25                 # bisection tolerance for network-deliverable power [kW]


@dataclass
class RenewableParams:
    """DC-side renewable generation added to Topology-3 for this study."""
    pv_rated_kwp: float = 450.0
    # PV is distributed over the DC load buses in proportion to their Case-3 DC load rating
    pv_buses: Tuple[str, ...] = ("S11", "S15", "S16", "S17", "S18", "H02", "D12", "D17", "D19", "D20")
    latitude_deg: float = 37.39          # Seville
    day_of_year: int = 105               # 15 April (representative spring day)
    pv_performance_ratio: float = 0.85
    wt_rated_kw: float = 60.0
    wt_bus: str = "D19"
    wt_v_mean: float = 7.0               # m/s, hub height daily mean
    wt_v_amp: float = 1.5                # m/s, diurnal amplitude
    wt_t_peak_h: float = 15.0            # hour of diurnal wind-speed maximum
    wt_v_cut_in: float = 3.0
    wt_v_rated: float = 12.0
    wt_v_cut_out: float = 25.0


@dataclass
class BESSParams:
    P_rated_kw: float = 150.0            # charge = discharge rating
    E_rated_kwh: float = 300.0           # 2-h system (0.5 C)
    eta_ch: float = 0.95
    eta_dis: float = 0.95
    soc_min: float = 0.10
    soc_max: float = 0.90
    soc_0: float = 0.50
    soh_0: float = 0.90


@dataclass
class DegradationParams:
    """Xu, Oudalov, Ulbig, Andersson, Kirschen, IEEE Trans. Smart Grid 9(2):1131-1140, 2018
    (LMO cell). Cycle-depth stress, SOC stress, calendar aging, SEI-film nonlinear fade."""
    k_d1: float = 1.4e5
    k_d2: float = -0.501
    k_d3: float = -1.23e5
    k_sigma: float = 1.04
    sigma_ref: float = 0.5
    k_t: float = 4.14e-10                # 1/s, calendar
    alpha_sei: float = 5.75e-2
    beta_sei: float = 121.0
    soh_eol: float = 0.80
    J_segments: int = 10                 # piecewise-linear cycle-depth segments for the EMS (Xu et al., TPWRS 2018)


@dataclass
class DFMParams:
    H_f_h: float = 1.0                   # flexibility-support horizon [h]
    eps_risk: float = 0.05               # risk tolerance of the uncertainty reserve
    N_ref_cycles_per_day: float = 1.0    # degradation allowance: reference cycles per day
    DoD_ref: float = 0.8                 # depth of the reference cycle


@dataclass
class UncertaintyParams:
    sigma_pv_rel: float = 0.10           # std of PV error relative to forecast
    sigma_wt_rel: float = 0.15           # std of wind error relative to forecast
    sigma_wt_abs_pu: float = 0.03        # + floor relative to rating
    sigma_load_rel: float = 0.05         # std of demand error relative to forecast (AC and DC)
    ar1_phi: float = 0.8                 # 15-min AR(1) correlation of forecast errors
    n_samples_reserve: int = 20000       # samples used to estimate the reserve quantiles


@dataclass
class EMSParams:
    dt_h: float = 0.25                   # 15-min supervisory interval
    n_steps_day: int = 96
    horizon_steps: int = 96              # prediction horizon: shrinking, from interval k to the end of the day (<= 24 h)
    # representative 3-period time-of-use energy tariff [EUR/kWh] (2.0TD-type periods)
    price_valley: float = 0.09           # 00-08 h
    price_flat: float = 0.14             # 08-10, 14-18, 22-24 h
    price_peak: float = 0.22             # 10-14, 18-22 h
    price_export: float = 0.04
    lambda_curt: float = 0.05            # EUR/kWh, renewable-curtailment penalty (on top of lost energy)
    bess_cost_eur_per_kwh: float = 300.0 # replacement cost -> lambda_deg = C_rep / (1 - SOH_eol)
    mip_rel_gap: float = 1e-4
    n_fine_steps: int = 16            # 15-min planning stages over the first 4 h (move blocking)
    block_steps: int = 4              # then 1-h planning blocks
    time_limit_s: float = 20.0


@dataclass
class MCParams:
    n_trials: int = 100
    seed: int = 2026
