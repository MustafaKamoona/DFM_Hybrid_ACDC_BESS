"""Network-deliverable BESS limits for the forecast conditions (supporting figure).

Network-deliverable discharge and charge power of the BESS at bus H02, the required renewable curtailment
without storage (B0), the rated power, and the intervals in which the converter rating (discharge) or the
feeder-head current (charge) is the binding network constraint. These limits form the network component
of the DFM envelope; they are evaluated on the network model for the forecast conditions.

Data: data/nominal/precompute_network_forecast.csv.
"""
from .common import *  # noqa: F401,F403  (style, palette, study constants, read_result)

# ---------------------------------------------------------------------- 1. Figure and layout
FIG_NAME = "Fig_flexibility_limits"
FIG_WIDTH, FIG_HEIGHT = 7.2, 3.9
GAP_LEGEND = 0.19                     # height ratio of the row holding the legend (the plot has ratio 1)
HSPACE = 0.03
LEFT, RIGHT, TOP, BOTTOM = 0.09, 0.99, 0.995, 0.115

# ---------------------------------------------------------------------- 2. Fonts
FONT_AXIS, FONT_TICK, FONT_LEGEND = 11.5, 9.5, 10.5

# ---------------------------------------------------------------------- 3. Colors and line styles
C_NET, LW_NET = CAT["violet"], 1.7
LS_NET_DIS, LS_NET_CH = "-", (0, (4, 1.6))
C_CURT, ALPHA_CURT = LIMIT_RED, 0.3
C_RATED, LW_RATED, LS_RATED = INK_SECONDARY, 1.1, (0, (6, 1.6, 1.2, 1.6))
C_BIND_DIS, C_BIND_CH = CAT["violet"], CAT["orange"]
MS_BIND, MEW_BIND = 6.5, 1.1           # marker size and width of the binding-constraint ticks
BIND_OFFSET = 8                        # kW beyond the rated line (marker position only; carries no value)

# ---------------------------------------------------------------------- 4. Grid
GRID_COLOR, GRID_ALPHA, GRID_LW, GRID_LS = "#8a8a8a", 0.95, 0.85, ":"

# ---------------------------------------------------------------------- 5. Labels
LABEL_DIS = r"$P^{\mathrm{dis}}_{\mathrm{net},k}$"
LABEL_CH = r"$-P^{\mathrm{ch}}_{\mathrm{net},k}$"
LABEL_CURT = "Required curtailment (B0)"
LABEL_RATED = rf"Rated power ($\pm${P_RATED_KW:g} kW)"
LABEL_BIND_DIS = "Binding, discharge: I01-H01 converter rating"
LABEL_BIND_CH = "Binding, charge: feeder-head current"
XLABEL, YLABEL = "Time [h]", "Power [kW]"

# ---------------------------------------------------------------------- 6. Axis limits and ticks
XLIM, XTICKS = (0, 24), range(0, 25, 4)
YLIM, YTICKS = (-P_RATED_KW - 35, P_RATED_KW + 30), range(-150, 151, 50)

# ---------------------------------------------------------------------- 7. Legend (two coordinated rows in the gap row)
LEGEND_HANDLE, LEGEND_HANDLETEXT = 2.4, 0.5
TOP_LEGEND_COLSPACE, TOP_LEGEND_Y = 1.8, 0.80        # row center within the gap row (0 = bottom, 1 = top)
BIND_LEGEND_COLSPACE, BIND_LEGEND_Y = 1.8, 0.24


def build():
    """Create the figure from the released data and return it."""
    apply_style()
    # ---------------------------------------------------------------------- 8. Load saved data
    pre = read_result("precompute_network_forecast.csv")
    t = pre.t_h.values

    def stairs(y):
        """Step arrays covering the full last interval: its saved value is held until 24 h."""
        y = np.asarray(y, dtype=float)
        return np.r_[t, 24.0], np.r_[y, y[-1]]

    # ---------------------------------------------------------------------- 9. Create figure
    fig = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT))
    gs = fig.add_gridspec(2, 1, height_ratios=[GAP_LEGEND, 1.0], hspace=HSPACE, left=LEFT, right=RIGHT, top=TOP, bottom=BOTTOM)
    ax = fig.add_subplot(gs[1, 0])

    # ---------------------------------------------------------------------- 10. Curtailment, limits and binding-constraint ticks
    x_step, y_curt = stairs(pre.C0)
    ax.fill_between(x_step, 0, y_curt, step="post", color=C_CURT, alpha=ALPHA_CURT, lw=0)
    ax.step(*stairs(pre.P_net_dis), where="post", color=C_NET, lw=LW_NET, ls=LS_NET_DIS, zorder=3)
    ax.step(*stairs(-pre.P_net_ch), where="post", color=C_NET, lw=LW_NET, ls=LS_NET_CH, zorder=3)
    ax.axhline(P_RATED_KW, color=C_RATED, lw=LW_RATED, ls=LS_RATED, zorder=2)
    ax.axhline(-P_RATED_KW, color=C_RATED, lw=LW_RATED, ls=LS_RATED, zorder=2)
    bind_dis = (pre.net_bind_dis == "S_vsc").values      # intervals in which this constraint is binding
    bind_ch = (pre.net_bind_ch == "I_feeder").values
    ax.plot(t[bind_dis] + 0.5 * DT_H, np.full(bind_dis.sum(), P_RATED_KW + BIND_OFFSET), ls="", marker="|", ms=MS_BIND, mew=MEW_BIND, color=C_BIND_DIS)
    ax.plot(t[bind_ch] + 0.5 * DT_H, np.full(bind_ch.sum(), -P_RATED_KW - BIND_OFFSET), ls="", marker="|", ms=MS_BIND, mew=MEW_BIND, color=C_BIND_CH)

    # ---------------------------------------------------------------------- 11. Formatting
    ax.set_xlim(*XLIM); ax.set_xticks(XTICKS); ax.set_xlabel(XLABEL, fontsize=FONT_AXIS, labelpad=2)
    ax.set_ylim(*YLIM); ax.set_yticks(YTICKS); ax.set_ylabel(YLABEL, fontsize=FONT_AXIS)
    ax.tick_params(labelsize=FONT_TICK)
    ax.grid(True, color=GRID_COLOR, alpha=GRID_ALPHA, linewidth=GRID_LW, linestyle=GRID_LS)
    # Hide the gridlines lying exactly under the rated lines, so that these read cleanly
    for loc, tick in zip(ax.get_yticks(), ax.yaxis.get_major_ticks()):
        if np.isclose(abs(loc), P_RATED_KW):
            tick.gridline.set_visible(False)

    # ---------------------------------------------------------------------- 12. Legend: curves and limits on the first row, binding constraints on the second
    x_center = 0.5 * (ax.get_position().x0 + ax.get_position().x1)
    legend_style = dict(frameon=False, handlelength=LEGEND_HANDLE, handletextpad=LEGEND_HANDLETEXT, borderaxespad=0, borderpad=0)

    def gap_y(fraction):
        box = gs[0, 0].get_position(fig)
        return box.y0 + fraction * (box.y1 - box.y0)

    top_handles = [Line2D([], [], color=C_NET, lw=LW_NET, ls=LS_NET_DIS, label=LABEL_DIS),
                   Line2D([], [], color=C_NET, lw=LW_NET, ls=LS_NET_CH, label=LABEL_CH),
                   Line2D([], [], color=C_RATED, lw=LW_RATED, ls=LS_RATED, label=LABEL_RATED),
                   Patch(facecolor=C_CURT, alpha=ALPHA_CURT, lw=0, label=LABEL_CURT)]
    bind_handles = [Line2D([], [], ls="", marker="|", ms=MS_BIND + 1.5, mew=MEW_BIND, color=C_BIND_DIS, label=LABEL_BIND_DIS),
                    Line2D([], [], ls="", marker="|", ms=MS_BIND + 1.5, mew=MEW_BIND, color=C_BIND_CH, label=LABEL_BIND_CH)]
    fig.legend(handles=top_handles, loc="center", ncol=len(top_handles), bbox_to_anchor=(x_center, gap_y(TOP_LEGEND_Y)),
               fontsize=FONT_LEGEND, columnspacing=TOP_LEGEND_COLSPACE, **legend_style)
    fig.legend(handles=bind_handles, loc="center", ncol=len(bind_handles), bbox_to_anchor=(x_center, gap_y(BIND_LEGEND_Y)),
               fontsize=FONT_LEGEND, columnspacing=BIND_LEGEND_COLSPACE, **legend_style)
    return fig
