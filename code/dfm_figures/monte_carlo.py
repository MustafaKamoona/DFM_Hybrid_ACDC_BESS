"""Monte Carlo robustness: distributions over 100 paired realizations of the forecast errors.

Panels: energy cost (terminal-energy corrected), battery health consumption (rainflow counting),
renewable curtailment, and uncovered imbalance. All samples are shown; box-plot statistics are
Matplotlib defaults (median, quartiles, whiskers at 1.5 IQR, points beyond the whiskers as outliers).

Data: data/monte_carlo/results_mc_trials.csv.
"""
from .common import *  # noqa: F401,F403  (style, palette, study constants, read_result)
from matplotlib.colors import to_rgb, to_rgba

# ---------------------------------------------------------------------- 1. Figure and layout
FIG_NAME = "Fig_monte_carlo"
FIG_WIDTH, FIG_HEIGHT = 6.4, 5.4
HSPACE, WSPACE = 0.13, 0.27
LEFT, RIGHT, TOP, BOTTOM = 0.095, 0.99, 0.99, 0.05

# ---------------------------------------------------------------------- 2. Fonts
FONT_AXIS, FONT_TICK = 11.5, 9.5

# ---------------------------------------------------------------------- 3. Strategy colors and boxes
COLORS = {"B0": "darkred", "B1": STRATEGY_COLORS["B1"], "B2": STRATEGY_COLORS["B2"], "DFM": STRATEGY_COLORS["DFM"]}
BOX_WIDTH = 0.55
BOX_OPACITY = 0.55                    # strength of the box fill over white (the fill itself is opaque, so the grid stays behind it)
C_BOX_EDGE, LW_BOX_EDGE = INK_PRIMARY, 0.9
C_MEDIAN, LW_MEDIAN = INK_PRIMARY, 1.5
C_WHISKER, LW_WHISKER, LS_WHISKER = INK_PRIMARY, 0.9, "-"
C_CAP, LW_CAP = INK_PRIMARY, 0.9

# ---------------------------------------------------------------------- 4. Outliers (drawn in the color of their strategy)
SHOW_OUTLIERS = True
MARKER_OUTLIER, MS_OUTLIER = "o", 3.6
OUTLIER_OPACITY = 0.6                 # fill opacity, so that neighbouring outliers remain distinguishable
OUTLIER_EDGE_OPACITY, MEW_OUTLIER = 1.0, 0.55   # the edge uses the strategy color as well

# ---------------------------------------------------------------------- 5. Grid (horizontal lines only)
GRID_COLOR, GRID_ALPHA, GRID_LW, GRID_LS = "#8a8a8a", 0.95, 0.85, ":"

# ---------------------------------------------------------------------- 6. DFM tick label
DFM_LABEL_WEIGHT = "bold"
C_DFM_LABEL = INK_PRIMARY

# ---------------------------------------------------------------------- 7. Panels: (column, y-label, multiplier, strategies, y-limits, y-ticks)
# y-limits or y-ticks = None: Matplotlib's automatic limits and ticks
ALL_STRATEGIES = ("B0", "B1", "B2", "DFM")
PANELS = [("cost_corr_EUR", "Energy cost [EUR]", 1, ALL_STRATEGIES, None, None),
          ("dSOH_rainflow", r"$\Delta\mathrm{SOH}$ [$10^{-5}$]", 1e5, ("B1", "B2", "DFM"), None, None),
          ("E_curt_kWh", "Curtailment energy [kWh]", 1, ALL_STRATEGIES, None, None),
          ("E_dev_kWh", "Uncovered imbalance [kWh]", 1, ALL_STRATEGIES, None, None)]


def build():
    """Create the figure from the released data and return it."""
    apply_style()
    # ---------------------------------------------------------------------- 8. Load saved data
    trials = read_result("results_mc_trials.csv")

    def box_fill(color):
        """Opaque tint of a strategy color over white."""
        return BOX_OPACITY * np.array(to_rgb(color)) + (1 - BOX_OPACITY)

    # ---------------------------------------------------------------------- 9. Create figure
    fig = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT))
    gs = fig.add_gridspec(2, 2, hspace=HSPACE, wspace=WSPACE, left=LEFT, right=RIGHT, top=TOP, bottom=BOTTOM)
    axes = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(2)]

    # ---------------------------------------------------------------------- 10. Box plots
    for ax, (col, ylabel, scale, strategies, ylim, yticks) in zip(axes, PANELS):
        data = [trials[trials.strategy == s][col].values * scale for s in strategies]
        bp = ax.boxplot(data, widths=BOX_WIDTH, patch_artist=True, showfliers=SHOW_OUTLIERS,
                        boxprops=dict(edgecolor=C_BOX_EDGE, linewidth=LW_BOX_EDGE),
                        medianprops=dict(color=C_MEDIAN, lw=LW_MEDIAN),
                        whiskerprops=dict(color=C_WHISKER, lw=LW_WHISKER, ls=LS_WHISKER),
                        capprops=dict(color=C_CAP, lw=LW_CAP))
        for box, fliers, s in zip(bp["boxes"], bp["fliers"], strategies):
            box.set_facecolor(box_fill(COLORS[s]))
            fliers.set(marker=MARKER_OUTLIER, markersize=MS_OUTLIER, markerfacecolor=to_rgba(COLORS[s], OUTLIER_OPACITY),
                       markeredgecolor=to_rgba(COLORS[s], OUTLIER_EDGE_OPACITY), markeredgewidth=MEW_OUTLIER)

        # ------------------------------------------------------------------ 11. Formatting
        ax.set_xticks(range(1, len(strategies) + 1), labels=strategies)
        for label in ax.get_xticklabels():
            if label.get_text() == "DFM":
                label.set(fontweight=DFM_LABEL_WEIGHT, color=C_DFM_LABEL)
        ax.set_ylabel(ylabel, fontsize=FONT_AXIS)
        ax.tick_params(labelsize=FONT_TICK)
        if ylim is not None:
            ax.set_ylim(*ylim)
        if yticks is not None:
            ax.set_yticks(yticks)
        ax.grid(False, axis="x")
        ax.grid(True, axis="y", color=GRID_COLOR, alpha=GRID_ALPHA, linewidth=GRID_LW, linestyle=GRID_LS)
        ax.set_axisbelow(True)
    fig.align_ylabels([axes[0], axes[2]])
    fig.align_ylabels([axes[1], axes[3]])
    return fig
