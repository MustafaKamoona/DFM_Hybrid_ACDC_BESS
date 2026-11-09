"""Energy-management performance of the four strategies on the nominal day.

Panels: BESS power; state of charge; change of the grid exchange with respect to B0 (no storage);
renewable curtailment. B0 is shown only in the curtailment panel, because it has no BESS and is the
reference of the grid-exchange panel (zero line).

Data: data/nominal/log_nominal_{B0,B1,B2,DFM}.csv.
"""
from .common import *  # noqa: F401,F403  (style, palette, study constants, read_result)

# ---------------------------------------------------------------------- 1. Figure and layout
FIG_NAME = "Fig_energy_performance"
FIG_WIDTH, FIG_HEIGHT = 5.3, 6.3
GAP_SHARED = 0.20                     # height ratio of the row holding the legend of panels 1-3
GAP_PANEL4 = 0.40                     # height ratio of the row holding the legend of panel 4
# Rows: gap (shared legend), BESS power, SOC, grid change, gap (panel 4 legend), curtailment
HEIGHT_RATIOS = [GAP_SHARED, 1.0, 0.86, 1.0, GAP_PANEL4, 1.0]
HSPACE = 0.11
LEFT, RIGHT, TOP, BOTTOM = 0.165, 0.985, 0.995, 0.075

# ---------------------------------------------------------------------- 2. Fonts and line widths
FONT_AXIS, FONT_TICK, FONT_LEGEND_SHARED, FONT_LEGEND_PANEL4 = 11.5, 9.5, 10.5, 10.5
# DFM is drawn last and slightly thicker; B0 (panel 4 only) is drawn first and wide enough to stay visible beneath the others
LW = {"B0": 2.8, "B1": 1.4, "B2": 1.4, "DFM": 1.6}
LW_ZERO = 0.9

# ---------------------------------------------------------------------- 3. Colors and line styles (strategy colors shared by all figures)
COLORS = {"B0": "darkred", "B1": STRATEGY_COLORS["B1"], "B2": STRATEGY_COLORS["B2"], "DFM": STRATEGY_COLORS["DFM"]}
LINESTYLES = {"B0": "--", "B1": "-", "B2": "-", "DFM": "-"}
C_ZERO, LS_ZERO = INK_SECONDARY, "-"

# ---------------------------------------------------------------------- 4. Grid
GRID_COLOR, GRID_ALPHA, GRID_LW, GRID_LS = "#8a8a8a", 0.95, 0.85, ":"

# ---------------------------------------------------------------------- 5. Labels
NAMES = {s: STRATEGY_LABELS[s] for s in ("B0", "B1", "B2", "DFM")}
YLABEL_POWER = "BESS power\n" + r"$P_{\mathrm{B},k}$ [kW]"
YLABEL_SOC = "State of charge\nSOC"
YLABEL_GRID = "Grid power vs B0\n" + r"$\Delta P_{\mathrm{grid}}$ [kW]"
YLABEL_CURT = "Curtailment\n" + r"$P_{\mathrm{curt},k}$ [kW]"
XLABEL = "Time [h]"

# ---------------------------------------------------------------------- 6. Axis limits and ticks
XLIM, XTICKS = (0, 24), range(0, 25, 4)
YLIM_POWER, YTICKS_POWER = (-175, 175), range(-150, 151, 75)   # same scale as the grid-power panel
YLIM_SOC, YTICKS_SOC = (0, 1), (0, 0.25, 0.5, 0.75, 1.0)
YLIM_GRID, YTICKS_GRID = (-175, 175), range(-150, 151, 75)
YLIM_CURT, YTICKS_CURT = (-6, 225), range(0, 201, 50)          # small margin below 0 so zero-curtailment lines are not clipped

# ---------------------------------------------------------------------- 7. Legends
LEGEND_HANDLE, LEGEND_HANDLETEXT = 1.8, 0.5
# Legend of panels 1-3 (one row, centered in its gap row)
SHARED_LEGEND_NCOL, SHARED_LEGEND_COLSPACE, SHARED_LEGEND_Y = 3, 1.3, 0.25
# Legend of panel 4 (two balanced rows, closer to panel 4 than to panel 3)
PANEL4_LEGEND_NCOL, PANEL4_LEGEND_COLSPACE, PANEL4_LEGEND_ROWSPACE, PANEL4_LEGEND_Y = 2, 2.2, 0.3, 0.25


def build():
    """Create the figure from the released data and return it."""
    apply_style()
    # ---------------------------------------------------------------------- 8. Load saved data
    STRATEGIES = ("B0", "B1", "B2", "DFM")
    logs = {s: read_result(f"log_nominal_{s}.csv") for s in STRATEGIES}
    t = logs["B0"].t_h.values

    def stairs(y):
        """Step arrays covering the full last interval: its saved value is held until 24 h."""
        y = np.asarray(y, dtype=float)
        return np.r_[t, 24.0], np.r_[y, y[-1]]

    # ---------------------------------------------------------------------- 9. Create figure
    fig = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT))
    gs = fig.add_gridspec(len(HEIGHT_RATIOS), 1, height_ratios=HEIGHT_RATIOS, hspace=HSPACE,
                          left=LEFT, right=RIGHT, top=TOP, bottom=BOTTOM)
    ax_power = fig.add_subplot(gs[1, 0])
    ax_soc = fig.add_subplot(gs[2, 0], sharex=ax_power)
    ax_grid = fig.add_subplot(gs[3, 0], sharex=ax_power)
    ax_curt = fig.add_subplot(gs[5, 0], sharex=ax_power)
    axes = (ax_power, ax_soc, ax_grid, ax_curt)

    # ---------------------------------------------------------------------- 10a. Panels 1-3: B1, B2, DFM
    for s in ("B1", "B2", "DFM"):
        style = dict(color=COLORS[s], lw=LW[s], ls=LINESTYLES[s])
        L = logs[s]
        ax_power.step(*stairs(L.P_B), where="post", **style)
        ax_soc.plot(np.r_[t, 24.0], np.r_[L.soc.values, L.soc_next.values[-1]], **style)
        ax_grid.step(*stairs(L.P_MV0 - logs["B0"].P_MV0), where="post", **style)
    ax_grid.axhline(0, color=C_ZERO, lw=LW_ZERO, ls=LS_ZERO, zorder=1.8)   # zero line = B0, the reference of this panel

    # ---------------------------------------------------------------------- 10b. Panel 4: B0, B1, B2, DFM
    for s in STRATEGIES:
        ax_curt.step(*stairs(logs[s].P_curt), where="post", color=COLORS[s], lw=LW[s], ls=LINESTYLES[s])

    # ---------------------------------------------------------------------- 11. Shared formatting
    for ax, ylabel, ylim, yticks in ((ax_power, YLABEL_POWER, YLIM_POWER, YTICKS_POWER), (ax_soc, YLABEL_SOC, YLIM_SOC, YTICKS_SOC),
                                     (ax_grid, YLABEL_GRID, YLIM_GRID, YTICKS_GRID), (ax_curt, YLABEL_CURT, YLIM_CURT, YTICKS_CURT)):
        ax.set_ylabel(ylabel, fontsize=FONT_AXIS)
        ax.set_ylim(*ylim); ax.set_yticks(yticks)
        ax.tick_params(labelsize=FONT_TICK)
        ax.grid(True, color=GRID_COLOR, alpha=GRID_ALPHA, linewidth=GRID_LW, linestyle=GRID_LS)
    for ax in axes[:3]:
        ax.tick_params(labelbottom=False)
    ax_curt.set_xlim(*XLIM); ax_curt.set_xticks(XTICKS)
    ax_curt.set_xlabel(XLABEL, fontsize=FONT_AXIS, labelpad=2)
    fig.align_ylabels(axes)

    # ---------------------------------------------------------------------- Legends
    x_center = 0.5 * (ax_power.get_position().x0 + ax_power.get_position().x1)
    legend_style = dict(frameon=False, handlelength=LEGEND_HANDLE, handletextpad=LEGEND_HANDLETEXT, borderaxespad=0, borderpad=0)

    def gap_y(row, fraction):
        box = gs[row, 0].get_position(fig)
        return box.y0 + fraction * (box.y1 - box.y0)

    def handle(s):
        return Line2D([], [], color=COLORS[s], lw=LW[s], ls=LINESTYLES[s], label=NAMES[s])

    fig.legend(handles=[handle(s) for s in ("B1", "B2", "DFM")], loc="center", ncol=SHARED_LEGEND_NCOL,
               bbox_to_anchor=(x_center, gap_y(0, SHARED_LEGEND_Y)), fontsize=FONT_LEGEND_SHARED,
               columnspacing=SHARED_LEGEND_COLSPACE, **legend_style)
    # Two rows, filled column by column: B0 and B1 on the first row, B2 and DFM on the second
    fig.legend(handles=[handle(s) for s in ("B0", "B2", "B1", "DFM")], loc="center", ncol=PANEL4_LEGEND_NCOL,
               bbox_to_anchor=(x_center, gap_y(4, PANEL4_LEGEND_Y)), fontsize=FONT_LEGEND_PANEL4,
               columnspacing=PANEL4_LEGEND_COLSPACE, labelspacing=PANEL4_LEGEND_ROWSPACE, **legend_style)
    return fig
