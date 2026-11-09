"""Shared plotting style, study constants and data access for the published figures.

All figures read the released CSV files in ``data/`` and never execute a network
simulation, an optimization or a Monte Carlo experiment. The constants below are
the study parameters used to produce the published results (``code/dfm_acdc/config.py``);
they are scientific values and should not be changed to restyle a figure.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")                     # file output only; no display is required
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

__all__ = ["np", "pd", "plt", "Line2D", "Patch", "REPO_ROOT", "DATA_DIR", "read_result", "apply_style",
           "CAT", "INK_PRIMARY", "INK_SECONDARY", "INK_MUTED", "LIMIT_RED", "STRATEGY_COLORS", "STRATEGY_LABELS",
           "P_RATED_KW", "E_RATED_KWH", "SOC_MIN", "SOC_MAX", "SOH_0", "H_F_H", "N_REF", "DOD_REF", "DT_H",
           "WT_RATED_KW", "SIGMA_PV_REL", "SIGMA_WT_REL", "SIGMA_WT_ABS_PU", "SIGMA_LOAD_REL", "AR1_PHI",
           "N_SAMPLES_RESERVE", "RESERVE_SEED",
           "V_NOM_LN", "V_MIN_PU", "V_MAX_PU", "V_DC_NOM", "V_DC_MAX_PU", "I_FEEDER_MAX"]

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


def read_result(name, **kwargs):
    """Read one released result file by name from any sub-folder of ``data/``.

    ``float_precision="round_trip"`` reproduces the stored floating-point values exactly.
    """
    matches = sorted(DATA_DIR.rglob(name))
    if len(matches) != 1:
        raise FileNotFoundError(f"expected exactly one '{name}' under {DATA_DIR}, found {len(matches)}")
    return pd.read_csv(matches[0], float_precision="round_trip", **kwargs)


def apply_style(serif=True):
    """Matplotlib settings shared by all figures: Times New Roman text, STIX mathematics,
    and TrueType (Type 42) font embedding so that the PDF text remains selectable.
    With ``serif=False`` the Matplotlib default sans-serif fonts are kept (used by the
    supporting degradation-model figure, which retains its original typography)."""
    plt.rcdefaults()
    plt.rcParams.update({
        "font.size": 8.5, "axes.labelsize": 9, "axes.titlesize": 9, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "legend.fontsize": 7, "lines.linewidth": 1.3, "axes.grid": True, "grid.linewidth": 0.6, "grid.alpha": 0.7,
        "grid.color": "#b7b6ae", "axes.edgecolor": "#c3c2b7", "figure.dpi": 150, "savefig.dpi": 300,
        "pdf.fonttype": 42, "ps.fonttype": 42, "figure.facecolor": "white", "axes.facecolor": "white",
    })
    if not serif:
        return
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman"],
        "mathtext.fontset": "stix",
    })


# ----------------------------------------------------------------------- color palette
CAT = {"blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100",
       "magenta": "#e87ba4", "green": "#008300", "violet": "#4a3aa7", "red": "#e34948"}
INK_PRIMARY, INK_SECONDARY, INK_MUTED = "#0b0b0b", "#52514e", "#898781"
LIMIT_RED = "#d03b3b"
STRATEGY_COLORS = {"B0": "#898781", "B1": CAT["blue"], "B2": CAT["orange"], "DFM": CAT["aqua"],
                   "M1": CAT["yellow"], "M2": CAT["magenta"], "M3": CAT["green"]}
STRATEGY_LABELS = {"B0": "B0 (no BESS)", "B1": "B1 (SOC-based)", "B2": "B2 (deg.-aware)", "DFM": "DFM (proposed)",
                   "M1": r"$\mathcal{M}_1$", "M2": r"$\mathcal{M}_2$", "M3": r"$\mathcal{M}_3$"}

# ----------------------------------------------------------------------- study constants
# BESS rating, SOC window, initial state of health and DFM design parameters
P_RATED_KW, E_RATED_KWH = 150.0, 300.0
SOC_MIN, SOC_MAX, SOH_0 = 0.10, 0.90, 0.90
H_F_H, N_REF, DOD_REF = 1.0, 1.0, 0.8    # support horizon [h], reference cycles per day, reference depth
DT_H = 0.25                              # supervisory interval [h]
# AC voltages are phase-to-neutral; the DC voltage is the pole-to-pole voltage of the 800-V DC grid
V_NOM_LN, V_MIN_PU, V_MAX_PU = 231.0, 0.95, 1.05
V_DC_NOM, V_DC_MAX_PU = 800.0, 1.05
# Feeder-head current limits [A]: 724.6 / 231.9 / 434.8 A (R01/I01/C01); Industrial (I01): 160-kVA current basis.
I_FEEDER_MAX = {"R01": 500e3 / 690, "I01": 160e3 / 690, "C01": 300e3 / 690}

# Forecast-error model of the uncertainty reserve: AR(1) processes with correlation AR1_PHI and
# standard deviations relative to the forecast (wind: plus a floor relative to the rating)
WT_RATED_KW = 60.0
SIGMA_PV_REL, SIGMA_WT_REL, SIGMA_WT_ABS_PU, SIGMA_LOAD_REL, AR1_PHI = 0.10, 0.15, 0.03, 0.05, 0.8
N_SAMPLES_RESERVE, RESERVE_SEED = 20000, 12345
