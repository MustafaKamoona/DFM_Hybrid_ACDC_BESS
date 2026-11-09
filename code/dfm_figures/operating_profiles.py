"""Nominal 24-h operating conditions.

Panels: (a) AC, DC and total demand; (b) available DC-side PV and wind generation together with the
curtailment required by the network without storage (B0); (c) time-of-use energy price.

Data: data/nominal/results_profiles.csv, data/nominal/results_B0_renewables.csv.
Profiles are piecewise constant over each 15-min interval and are drawn as step plots.
"""
from .common import *  # noqa: F401,F403  (style, palette, study constants, read_result)

# ---------------------------------------------------------------------- 1. Figure and layout
FIG_NAME = "Fig_operating_profiles"
FIG_WIDTH, FIG_HEIGHT = 5, 5.6             # figure size [in]
HEIGHT_RATIOS = [1.0, 1.0, 0.58]      # panels (a), (b), (c)
HSPACE = 0.19                         # gap between panels (holds the (a) and (b) labels)
LEFT, RIGHT, TOP, BOTTOM = 0.155, 0.865, 0.99, 0.135

# ---------------------------------------------------------------------- 2. Fonts and line widths
FONT_AXIS, FONT_TICK, FONT_LEGEND, FONT_PANEL = 10.5, 9.5, 9, 10.0
LW_AC, LW_DC, LW_TOTAL = 1.6, 1.6, 1.6
LW_PV, LW_WIND, LW_CURT_EDGE, LW_PRICE = 1.6, 1.6, 1.6, 1.6

# ---------------------------------------------------------------------- 3. Colors and line styles
C_AC, LS_AC = CAT["blue"], "-"
C_DC, LS_DC = CAT["red"], "-."
C_TOTAL, LS_TOTAL = INK_PRIMARY, "-"
C_PV, LS_PV = CAT["green"], "-"
C_WIND, LS_WIND = CAT["red"], "-"
C_CURT, CURT_ALPHA = "purple", 0.75
C_PRICE, LS_PRICE = "darkred", "-"

# ---------------------------------------------------------------------- 4. Grid
GRID_COLOR, GRID_ALPHA, GRID_LW, GRID_LS = "#8a8a8a", 0.95, 0.85, ":"

# ---------------------------------------------------------------------- 5. Labels
LABELS = {"ac": "AC demand", "dc": "DC demand", "total": "Total demand",
          "pv": "PV (available)", "wt": "Wind (available)", "curt": "B0 network-forced curtailment"}
YLABEL_A, YLABEL_B, YLABEL_WIND, YLABEL_C = "Demand [kW]", "PV, curtailment [kW]", "Wind [kW]", "Price [c/kWh]"
XLABEL = "Time [h]"

# ---------------------------------------------------------------------- 6. Axis limits and ticks
XLIM, XTICKS = (0, 24), range(0, 25, 4)
YLIM_A, YTICKS_A = (0, 1000), range(0, 1001, 250)
YLIM_B, YTICKS_B = (0, 450), range(0, 451, 150)     # the two axes of panel (b) share gridlines:
YLIM_WIND, YTICKS_WIND = (0, 30), range(0, 31, 10)  # both are divided into the same three intervals
YLIM_C, YTICKS_C = (0, 25), range(0, 26, 5)

# ---------------------------------------------------------------------- 7. Legends (inside, top of panel)
LEGEND_HANDLE, LEGEND_COLSPACE, LEGEND_HANDLETEXT, LEGEND_AXPAD = 1.8, 1.8, 0.45, 0.12
LEGEND_B_ROW_STEP = 0.1             # panel (b): vertical distance between its two legend rows (axes fraction)

# ---------------------------------------------------------------------- 8. Panel labels (centered below each panel)
PANEL_GAP_PT = 4.5                    # points below the axis, panels (a) and (b)
PANEL_GAP_LAST_PT = 28.0              # points below the axis, panel (c): clears the ticks and "Time [h]"


def build():
    """Create the figure from the released data and return it."""
    apply_style()
    # ---------------------------------------------------------------------- 9. Load saved data
    prof = read_result("results_profiles.csv")
    b0 = read_result("results_B0_renewables.csv")
    t = prof.t_h

    # ---------------------------------------------------------------------- 10. Create figure
    fig, axes = plt.subplots(3, 1, figsize=(FIG_WIDTH, FIG_HEIGHT), sharex=True,
                             gridspec_kw={"height_ratios": HEIGHT_RATIOS})
    fig.subplots_adjust(left=LEFT, right=RIGHT, top=TOP, bottom=BOTTOM, hspace=HSPACE)
    legend_style = dict(loc="upper center", frameon=False, fontsize=FONT_LEGEND, handlelength=LEGEND_HANDLE,
                        handletextpad=LEGEND_HANDLETEXT, columnspacing=LEGEND_COLSPACE, borderaxespad=LEGEND_AXPAD)

    # ---------------------------------------------------------------------- 11. Panel (a): demand
    ax = axes[0]
    ax.step(t, prof.P_ac_kW, where="post", color=C_AC, ls=LS_AC, lw=LW_AC, label=LABELS["ac"])
    ax.step(t, prof.P_dc_kW, where="post", color=C_DC, ls=LS_DC, lw=LW_DC, label=LABELS["dc"])
    ax.step(t, prof.P_ac_kW + prof.P_dc_kW, where="post", color=C_TOTAL, ls=LS_TOTAL, lw=LW_TOTAL, label=LABELS["total"])
    ax.set_ylabel(YLABEL_A, fontsize=FONT_AXIS)
    ax.set_ylim(*YLIM_A); ax.set_yticks(YTICKS_A)
    ax.legend(ncol=3, bbox_to_anchor=(0.5, 1.0), **legend_style)

    # ---------------------------------------------------------------------- 12. Panel (b): PV and curtailment (left), wind (right)
    ax = axes[1]
    pv_line, = ax.step(t, prof.P_pv_kW, where="post", color=C_PV, ls=LS_PV, lw=LW_PV, zorder=3)
    curt_fill = ax.fill_between(t, 0, b0.P_curt_kW, step="post", facecolor=C_CURT, alpha=CURT_ALPHA, lw=0, zorder=2)
    ax.step(t, b0.P_curt_kW, where="post", color=C_CURT, lw=LW_CURT_EDGE, zorder=4)
    ax.set_ylabel(YLABEL_B, fontsize=FONT_AXIS)
    ax.set_ylim(*YLIM_B); ax.set_yticks(YTICKS_B)

    ax_wind = ax.twinx()
    wind_line, = ax_wind.step(t, prof.P_wt_kW, where="post", color=C_WIND, ls=LS_WIND, lw=LW_WIND, zorder=5)
    ax_wind.set_ylabel(YLABEL_WIND, fontsize=FONT_AXIS, color=C_WIND)
    ax_wind.set_ylim(*YLIM_WIND); ax_wind.set_yticks(YTICKS_WIND)
    ax_wind.tick_params(axis="y", labelsize=FONT_TICK, labelcolor=C_WIND)
    ax_wind.grid(False)
    # two balanced, centered legend rows: PV and wind on the first, curtailment on the second
    legend_b1 = ax_wind.legend([pv_line, wind_line], [LABELS["pv"], LABELS["wt"]], ncol=2, bbox_to_anchor=(0.5, 1.0), **legend_style)
    ax_wind.add_artist(legend_b1)
    legend_b2 = ax_wind.legend([curt_fill], [LABELS["curt"]], ncol=1, bbox_to_anchor=(0.5, 1.0 - LEGEND_B_ROW_STEP), **legend_style)

    # ---------------------------------------------------------------------- 13. Panel (c): energy price
    ax = axes[2]
    ax.step(t, prof.price_EUR_kWh * 100, where="post", color=C_PRICE, ls=LS_PRICE, lw=LW_PRICE)
    ax.set_ylabel(YLABEL_C, fontsize=FONT_AXIS)
    ax.set_ylim(*YLIM_C); ax.set_yticks(YTICKS_C)
    ax.set_xlabel(XLABEL, fontsize=FONT_AXIS, labelpad=2)
    ax.set_xlim(*XLIM); ax.set_xticks(XTICKS)

    # ---------------------------------------------------------------------- 14. Common formatting
    for ax, lab, gap in zip(axes, "abc", (PANEL_GAP_PT, PANEL_GAP_PT, PANEL_GAP_LAST_PT)):
        ax.tick_params(labelsize=FONT_TICK)
        ax.grid(True, color=GRID_COLOR, alpha=GRID_ALPHA, linewidth=GRID_LW, linestyle=GRID_LS)
        ax.annotate(f"({lab})", xy=(0.5, 0), xycoords="axes fraction", xytext=(0, -gap), textcoords="offset points",
                    ha="center", va="top", fontsize=FONT_PANEL, annotation_clip=False)
    fig.align_ylabels(axes)
    return fig
