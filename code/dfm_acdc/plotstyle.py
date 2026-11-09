"""Shared figure formatting (same sizes and palette as the TCST_CRI project) and a single validated color system
used by every notebook, so all eight paper figures read as one visual
family. Colors are taken unmodified from a pre-validated categorical /
status / sequential / diverging palette (CVD-safe adjacent pairs, checked
contrast) -- see the dataviz palette this project's figures were built
against; nothing here re-derives or eyeballs a color.
"""
from typing import Optional, Sequence
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

IEEE_COL_WIDTH_IN = 3.45
IEEE_PAGE_WIDTH_IN = 7.16

FIGSIZE_1COL = (IEEE_COL_WIDTH_IN, 4.6)
FIGSIZE_1COL_SHORT = (IEEE_COL_WIDTH_IN, 3.0)
FIGSIZE_1COL_TALL = (IEEE_COL_WIDTH_IN, 6.0)
FIGSIZE_1COL_STACK3 = (IEEE_COL_WIDTH_IN, 5.4)     # 3 stacked (a)/(b)/(c) panels
FIGSIZE_DASHBOARD = (IEEE_PAGE_WIDTH_IN, 7.6)      # full-width, many stacked panels
FIGSIZE_2COL_SHORT = (IEEE_PAGE_WIDTH_IN, 3.2)
FIGSIZE_2x2 = (IEEE_COL_WIDTH_IN * 1.55, IEEE_COL_WIDTH_IN * 1.4)

BASE_RC = {
    "font.size": 8.5,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7,
    "lines.linewidth": 1.3,
    "axes.grid": True,
    "grid.linewidth": 0.6,
    "grid.alpha": 0.7,
    "grid.color": "#b7b6ae",
    "axes.edgecolor": "#c3c2b7",
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
}


def apply_style():
    plt.rcParams.update(BASE_RC)


def savefig(fig, path):
    fig.tight_layout()
    fig.savefig(path, format="pdf", bbox_inches="tight")


# --- Categorical palette (fixed order; never cycled/reassigned) -----------
CAT = {
    "blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100",
    "magenta": "#e87ba4", "green": "#008300", "violet": "#4a3aa7", "red": "#e34948",
}

# Strategies, in the fixed categorical order (B0 is the no-storage reference -> neutral ink).
STRATEGY_COLORS = {"B0": "#898781", "B1": CAT["blue"], "B2": CAT["orange"], "DFM": CAT["aqua"],
                   "M1": CAT["yellow"], "M2": CAT["magenta"], "M3": CAT["green"]}
STRATEGY_LABELS = {"B0": "B0 (no BESS)", "B1": "B1 (SOC-based)", "B2": "B2 (deg.-aware)",
                   "DFM": "DFM (proposed)", "M1": r"$\mathcal{M}_1$", "M2": r"$\mathcal{M}_2$",
                   "M3": r"$\mathcal{M}_3$"}

# Active flexibility limiters (Eq. active_limiter): energy, degradation, network, rated (none active)
LIMITER_COLORS = {"en": CAT["blue"], "deg": CAT["orange"], "net": CAT["violet"], "rated": "#c3c2b7"}
LIMITER_LABELS = {"en": "Energy/health", "deg": "Degradation", "net": "Network", "rated": "Rated (none)"}
LIMITER_CODE = {"en": 0, "deg": 1, "net": 2, "rated": 3}

# Status palette (reserved: limits / violations only)
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
LIMIT_COLOR = STATUS["critical"]

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"

# --- Sequential ramp (single hue, light -> dark blue) ----------------------
_SEQ_BLUE_STEPS = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
SEQUENTIAL_CMAP = LinearSegmentedColormap.from_list("seq_blue", _SEQ_BLUE_STEPS)

# --- Diverging pair (blue <-> red, neutral gray midpoint) -------------------
_DIV_STEPS = ["#0d366b", "#2a78d6", "#f0efec", "#e34948", "#7a1414"]
DIVERGING_CMAP = LinearSegmentedColormap.from_list("div_blue_red", _DIV_STEPS)


def shade_limiter_bg(ax, t, labels, alpha=0.18, dt=0.25):
    """Shade the background of a time axis by the active limiter at each interval."""
    for ti, lab in zip(t, labels):
        ax.axvspan(ti, ti + dt, color=LIMITER_COLORS.get(lab, "#ffffff"), alpha=alpha, lw=0)


def limiter_legend_handles():
    from matplotlib.patches import Patch
    return [Patch(facecolor=LIMITER_COLORS[k], alpha=0.5, label=LIMITER_LABELS[k]) for k in ("en", "deg", "net", "rated")]
