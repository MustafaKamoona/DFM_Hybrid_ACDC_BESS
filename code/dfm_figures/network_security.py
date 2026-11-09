"""AC/DC network-security indicators of the four strategies on the nominal day.

Panels: minimum and maximum AC phase-to-neutral voltage; maximum DC voltage; maximum feeder-head
loading (largest of the three feeder-head currents, each normalized by its current limit); and maximum
VSC utilization (apparent power over rating). The logs hold network-wide extrema per interval.
Dashed red lines are the operating limits. The annotations read their values from the logs.

Data: data/nominal/log_nominal_{B0,B1,B2,DFM}.csv.
"""
from .common import *  # noqa: F401,F403  (style, palette, study constants, read_result)

# ---------------------------------------------------------------------- 1. Figure and layout
FIG_NAME = "Fig_network_security"
FIG_WIDTH, FIG_HEIGHT = 5.3, 6.9     # same width as the energy-performance figure, so that both appear at the same scale
GAP_LEGEND = 0.62                     # height ratio of the row holding the shared legend
# Rows: gap (shared legend), AC voltage, DC voltage, feeder loading, VSC utilization
HEIGHT_RATIOS = [GAP_LEGEND, 1.1, 0.9, 1.0, 1.0]
HSPACE = 0.11
LEFT, RIGHT, TOP, BOTTOM = 0.165, 0.985, 0.995, 0.075    # margins shared with the energy-performance figure

# ---------------------------------------------------------------------- 2. Fonts and line widths
FONT_AXIS, FONT_TICK, FONT_LEGEND, FONT_ANNOTATION = 11.5, 9.5, 9, 10.5
# B0 is drawn first and wide, so it stays visible where the other strategies follow it; DFM is drawn last
LW = {"B0": 2.4, "B1": 1.4, "B2": 1.4, "DFM": 1.6}
LW_LIMIT = 1.2

# ---------------------------------------------------------------------- 3. Colors and line styles
COLORS = {"B0": "darkred", "B1": STRATEGY_COLORS["B1"], "B2": STRATEGY_COLORS["B2"], "DFM": STRATEGY_COLORS["DFM"]}
LINESTYLES = {"B0": "--", "B1": "-", "B2": "-", "DFM": "-"}
C_LIMIT_VOLTAGE, LS_LIMIT_VOLTAGE = LIMIT_RED, (0, (4, 2))
C_LIMIT_LOADING, LS_LIMIT_LOADING = LIMIT_RED, (0, (4, 2))
C_ANNOTATION, LW_ARROW = INK_PRIMARY, 1

# ---------------------------------------------------------------------- 4. Grid
GRID_COLOR, GRID_ALPHA, GRID_LW, GRID_LS = "#8a8a8a", 0.95, 0.85, ":"

# ---------------------------------------------------------------------- 5. Labels
NAMES = {s: STRATEGY_LABELS[s] for s in ("B0", "B1", "B2", "DFM")}
LABEL_LIMIT_VOLTAGE = "Voltage limits (AC: 0.95, 1.05 pu; DC: 1.05 pu)"
LABEL_LIMIT_LOADING = "Feeder-current and VSC limits (1.0 pu)"
YLABEL_AC = "AC voltage\nmin/max [pu]"
YLABEL_DC = "Max DC\nvoltage [pu]"
YLABEL_FEEDER = "Max feeder\nloading [pu]"
YLABEL_VSC = "Max VSC\nutilization [pu]"
XLABEL = "Time [h]"

# ---------------------------------------------------------------------- 6. Axis limits and ticks
XLIM, XTICKS = (0, 24), range(0, 25, 4)
YLIM_AC, YTICKS_AC = (0.94, 1.06), (0.95, 1.00, 1.05)
YLIM_DC, YTICKS_DC = (0.99, 1.06), (1.00, 1.01, 1.02, 1.03, 1.04, 1.05)
YLIM_FEEDER, YTICKS_FEEDER = (0.4, 1.1), (0.4, 0.6, 0.8, 1.0)      # same scale as the VSC panel
YLIM_VSC, YTICKS_VSC = (0.4, 1.1), (0.4, 0.6, 0.8, 1.0)

# ---------------------------------------------------------------------- 7. Legend (strategies, then limits, in one gap row)
LEGEND_HANDLE, LEGEND_HANDLETEXT = 2.0, 0.5
STRATEGY_LEGEND_NCOL, STRATEGY_LEGEND_COLSPACE, STRATEGY_LEGEND_ROWSPACE, STRATEGY_LEGEND_Y = 4, 0.8, 0.3, 0.3   # center within the gap row (0 = bottom, 1 = top)
LIMIT_LEGEND_NCOL, LIMIT_LEGEND_ROWSPACE, LIMIT_LEGEND_Y, LIMIT_LEGEND_COLSPACE = 2, 0.3, 0.002, 0.5

# ---------------------------------------------------------------------- 8. Annotations (values are read from the saved logs)
SHOW_ANNOTATIONS = True               # master switch
SHOW_ANNOTATION_VSC = True            # the only limit violation of the four strategies
SHOW_ANNOTATION_FEEDER = True         # the tightest feeder-current margin of the four strategies
ANNOTATION_VSC = dict(strategy="B1", t_h=22.0, text="B1 violation: {:.3f} pu", xytext=(20.6, 1.055))
ANNOTATION_FEEDER = dict(strategy="B2", t_h=17.75, text="B2 peak: {:.3f} pu", xytext=(16.4, 1.055))
NOTE_BOX = dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.8)


def build():
    """Create the figure from the released data and return it."""
    apply_style()
    # ---------------------------------------------------------------------- 9. Load saved data
    STRATEGIES = ("B0", "B1", "B2", "DFM")
    logs = {s: read_result(f"log_nominal_{s}.csv") for s in STRATEGIES}
    t = logs["B0"].t_h.values

    def stairs(y):
        """Step arrays covering the full last interval: its saved value is held until 24 h."""
        y = np.asarray(y, dtype=float)
        return np.r_[t, 24.0], np.r_[y, y[-1]]

    def feeder_loading(L):
        """Largest feeder-head current (R01, I01, C01) relative to its limit."""
        return np.maximum.reduce([L.I_R01 / I_FEEDER_MAX["R01"], L.I_I01 / I_FEEDER_MAX["I01"], L.I_C01 / I_FEEDER_MAX["C01"]])

    # ---------------------------------------------------------------------- 10. Create figure
    fig = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT))
    gs = fig.add_gridspec(len(HEIGHT_RATIOS), 1, height_ratios=HEIGHT_RATIOS, hspace=HSPACE,
                          left=LEFT, right=RIGHT, top=TOP, bottom=BOTTOM)
    ax_ac = fig.add_subplot(gs[1, 0])
    ax_dc = fig.add_subplot(gs[2, 0], sharex=ax_ac)
    ax_feeder = fig.add_subplot(gs[3, 0], sharex=ax_ac)
    ax_vsc = fig.add_subplot(gs[4, 0], sharex=ax_ac)
    axes = (ax_ac, ax_dc, ax_feeder, ax_vsc)

    # ---------------------------------------------------------------------- 11. Strategy curves
    for s in STRATEGIES:
        L = logs[s]
        style = dict(where="post", color=COLORS[s], lw=LW[s], ls=LINESTYLES[s])
        ax_ac.step(*stairs(L.V_min / V_NOM_LN), **style)
        ax_ac.step(*stairs(L.V_max / V_NOM_LN), **style)
        ax_dc.step(*stairs(L.Vdc_max / V_DC_NOM), **style)
        ax_feeder.step(*stairs(feeder_loading(L)), **style)
        ax_vsc.step(*stairs(L.util_vsc_max), **style)

    # ---------------------------------------------------------------------- 12. Operating limits
    voltage_limit = dict(color=C_LIMIT_VOLTAGE, lw=LW_LIMIT, ls=LS_LIMIT_VOLTAGE)
    loading_limit = dict(color=C_LIMIT_LOADING, lw=LW_LIMIT, ls=LS_LIMIT_LOADING)
    ax_ac.axhline(V_MIN_PU, **voltage_limit)
    ax_ac.axhline(V_MAX_PU, **voltage_limit)
    ax_dc.axhline(V_DC_MAX_PU, **voltage_limit)
    ax_feeder.axhline(1.0, **loading_limit)
    ax_vsc.axhline(1.0, **loading_limit)

    # ---------------------------------------------------------------------- 13. Shared formatting
    for ax, ylabel, ylim, yticks in ((ax_ac, YLABEL_AC, YLIM_AC, YTICKS_AC), (ax_dc, YLABEL_DC, YLIM_DC, YTICKS_DC),
                                     (ax_feeder, YLABEL_FEEDER, YLIM_FEEDER, YTICKS_FEEDER), (ax_vsc, YLABEL_VSC, YLIM_VSC, YTICKS_VSC)):
        ax.set_ylabel(ylabel, fontsize=FONT_AXIS)
        ax.set_ylim(*ylim); ax.set_yticks(yticks)
        ax.tick_params(labelsize=FONT_TICK)
        ax.grid(True, color=GRID_COLOR, alpha=GRID_ALPHA, linewidth=GRID_LW, linestyle=GRID_LS)
    # Hide the gridline lying exactly under a limit, so the limit reads as a clean dashed line
    for ax, levels in ((ax_ac, (V_MIN_PU, V_MAX_PU)), (ax_dc, (V_DC_MAX_PU,)), (ax_feeder, (1.0,)), (ax_vsc, (1.0,))):
        for loc, tick in zip(ax.get_yticks(), ax.yaxis.get_major_ticks()):
            if np.isclose(loc, levels).any():
                tick.gridline.set_visible(False)
    for ax in axes[:3]:
        ax.tick_params(labelbottom=False)
    ax_vsc.set_xlim(*XLIM); ax_vsc.set_xticks(XTICKS)
    ax_vsc.set_xlabel(XLABEL, fontsize=FONT_AXIS, labelpad=2)
    fig.align_ylabels(axes)

    # ---------------------------------------------------------------------- 14. Annotations
    def annotate_event(ax, series, event):
        """Arrow to the middle of the saved interval, labelled with its saved value."""
        k = int(np.flatnonzero(t == event["t_h"])[0])
        value = float(np.asarray(series)[k])
        ax.annotate(event["text"].format(value), xy=(event["t_h"] + 0.5 * DT_H, value), xytext=event["xytext"],
                    ha="right", va="center", fontsize=FONT_ANNOTATION, color=C_ANNOTATION, bbox=NOTE_BOX,
                    arrowprops=dict(arrowstyle="-|>", color=C_ANNOTATION, lw=LW_ARROW, shrinkA=1, shrinkB=1, mutation_scale=8))

    if SHOW_ANNOTATIONS and SHOW_ANNOTATION_VSC:
        annotate_event(ax_vsc, logs[ANNOTATION_VSC["strategy"]].util_vsc_max, ANNOTATION_VSC)
    if SHOW_ANNOTATIONS and SHOW_ANNOTATION_FEEDER:
        annotate_event(ax_feeder, feeder_loading(logs[ANNOTATION_FEEDER["strategy"]]), ANNOTATION_FEEDER)

    # ---------------------------------------------------------------------- 15. Shared legend: strategies on the first row, limits on the second
    LEGEND_X_SHIFT = -0.05  # horizontal offset of both legend rows (figure fraction)
    x_center = 0.5 * (ax_ac.get_position().x0 + ax_ac.get_position().x1) + LEGEND_X_SHIFT
    legend_style = dict(frameon=False, handlelength=LEGEND_HANDLE, handletextpad=LEGEND_HANDLETEXT, borderaxespad=0, borderpad=0)

    def gap_y(row, fraction):
        box = gs[row, 0].get_position(fig)
        return box.y0 + fraction * (box.y1 - box.y0)

    # Two rows, filled column by column: B0 and B1 on the first row, B2 and DFM on the second
    strategy_handles = [Line2D([], [], color=COLORS[s], lw=LW[s], ls=LINESTYLES[s], label=NAMES[s]) for s in ("B0", "B1", "B2", "DFM")]
    limit_handles = [Line2D([], [], label=LABEL_LIMIT_VOLTAGE, **voltage_limit), Line2D([], [], label=LABEL_LIMIT_LOADING, **loading_limit)]
    fig.legend(handles=strategy_handles, loc="center", ncol=STRATEGY_LEGEND_NCOL, bbox_to_anchor=(x_center, gap_y(0, STRATEGY_LEGEND_Y)),
               fontsize=FONT_LEGEND, columnspacing=STRATEGY_LEGEND_COLSPACE, labelspacing=STRATEGY_LEGEND_ROWSPACE, **legend_style)
    fig.legend(handles=limit_handles, loc="center", ncol=LIMIT_LEGEND_NCOL, bbox_to_anchor=(x_center, gap_y(0, LIMIT_LEGEND_Y)),
               fontsize=FONT_LEGEND, columnspacing=LIMIT_LEGEND_COLSPACE, labelspacing=LIMIT_LEGEND_ROWSPACE, **legend_style)
    return fig
