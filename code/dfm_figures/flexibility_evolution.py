"""Evolution of the dynamic flexibility envelope of the DFM strategy.

Left column: nominal (forecast) day. Right column: one uncertain realization (Monte Carlo trial 0).
Rows: SOC; remaining daily degradation allowance; rated, physical and safe flexibility envelopes with
the scheduled and executed BESS power; and the active limiter of each side of the envelope.

Data: data/nominal/log_nominal_DFM.csv, data/uncertainty/log_trial0_DFM.csv,
data/nominal/results_nominal_summary.csv, data/monte_carlo/results_mc_trials.csv.
The physical envelope is the intersection of the energy/health, degradation and network limits;
the safe envelope additionally withholds the directional uncertainty reserve.
"""
from .common import *  # noqa: F401,F403  (style, palette, study constants, read_result)

# ---------------------------------------------------------------------- 1. Figure and layout
FIG_NAME = "Fig_flexibility_evolution"
LIMITER_LEGEND_POSITION = "above"     # "above": between power panels and limiter strips; "below": under the time axes
FIG_WIDTH = 7.2
GAP_ENV = 0.43                        # height ratio of the gap holding the shared BESS legend
GAP_LIM = 0.25                        # height ratio of the gap holding the limiter legend ("above" only)
# Rows: SOC, allowance, gap (BESS legend), BESS power, [gap (limiter legend)], active limiter
if LIMITER_LEGEND_POSITION == "above":
    FIG_HEIGHT, BOTTOM, HEIGHT_RATIOS = 7.3, 0.068, [0.72, 0.72, GAP_ENV, 2.0, GAP_LIM, 0.46]
    AX_ROWS, GAP_ROW_ENV, GAP_ROW_LIM = (0, 1, 3, 5), 2, 4
elif LIMITER_LEGEND_POSITION == "below":
    FIG_HEIGHT, BOTTOM, HEIGHT_RATIOS = 7.3, 0.094, [0.72, 0.72, GAP_ENV, 2.0, 0.46]
    AX_ROWS, GAP_ROW_ENV, GAP_ROW_LIM = (0, 1, 3, 4), 2, None
else:
    raise ValueError('LIMITER_LEGEND_POSITION must be "above" or "below"')
HSPACE, WSPACE = 0.09, 0.085
LEFT, RIGHT, TOP = 0.098, 0.99, 0.96

# ---------------------------------------------------------------------- 2. Fonts and line widths
FONT_AXIS, FONT_TICK, FONT_TITLE, FONT_NOTE, FONT_LIMITER_TICK = 11.5, 9.5, 11.0, 9.5, 9.5
FONT_LEGEND_ENV, FONT_LEGEND_LIMITER = 10.5, 9.5
LW_SOC, LW_ALLOW, LW_SOC_LIMIT, LW_RATED = 1.6, 1.6, 1.2, 1.2
LW_SCHED, LW_EXEC, LW_ENVELOPE_EDGE = 1.7, 0.8, 0.5

# ---------------------------------------------------------------------- 3. Colors and line styles
C_SOC, C_ALLOW, C_SOC_LIMIT, C_NOTE = CAT["blue"], CAT["orange"], LIMIT_RED, INK_PRIMARY
NOTE_BOX = dict(facecolor="white", edgecolor="none", alpha=0.8, pad=0.8)   # subtle background behind in-panel notes
LS_SOC_LIMIT = "--"
C_RATED, LS_RATED = "#3d3c39", (0, (5, 2.5))     # rated boundaries: dashed, so they differ from the dotted grid
# Envelope regions are opaque: the legend patches match them exactly, and the safe region stays
# distinct where it lies on top of the physical one.
C_PHYS_FILL, C_PHYS_EDGE = "#d9d2f2", "#7566c4"
C_SAFE_FILL, C_SAFE_EDGE = "#9edcc3", "#1a8f65"
# Scheduled: thick dark line. Executed: thin bright line drawn on top, so both remain visible where they coincide.
C_SCHED, C_EXEC = INK_PRIMARY, "#ff3b30"
# Active limiter (same classification as the saved logs)
LIMITER_STYLE = {"en": (CAT["blue"], "Energy/health"), "deg": (CAT["orange"], "Degradation"),
                 "net": (CAT["violet"], "Network"), "rated": ("#9d9c95", "Rated (none)")}
C_LIMITER_EDGE, LW_LIMITER_EDGE = "white", 0.5    # thin separator between limiter blocks
C_LIMITER_PATCH_EDGE, LW_LIMITER_PATCH_EDGE = INK_SECONDARY, 0.5

# ---------------------------------------------------------------------- 4. Grid (no grid on the limiter strips)
GRID_COLOR, GRID_ALPHA, GRID_LW, GRID_LS = "#8a8a8a", 0.95, 0.85, ":"

# ---------------------------------------------------------------------- 5. Labels and titles
TITLE_LEFT, TITLE_RIGHT = "Nominal forecast (deterministic)", "Uncertain realization (Monte Carlo trial #0)"
YLABEL_SOC, YLABEL_ALLOW, YLABEL_POWER, YLABEL_LIMITER = "SOC", r"$D^{allow}_k$ [$10^{-6}$]", "BESS power [kW]", "Limiter"
XLABEL = "Time [h]"
LABEL_SOC_MAX, LABEL_SOC_MIN = r"$SOC_{\mathrm{max}}$", r"$SOC_{\mathrm{min}}$"
LABEL_RATED, LABEL_PHYS, LABEL_SAFE = r"Rated $\mathcal{F}^{\mathrm{rated}}$", r"Physical $\mathcal{F}^{\mathrm{physical}}_{k}$", r"Safe $\mathcal{F}^{\mathrm{safe}}_{k}$"
LABEL_SCHED, LABEL_EXEC = r"Scheduled $P_{\mathrm{B},k}$ (EMS)", r"Executed $P_{\mathrm{B},k}$ (with correction)"
LABEL_LIMITER_LEGEND = "Active limiter:"
LIMITER_ROW_LABELS = ("ch.", "dis.")

# ---------------------------------------------------------------------- 6. Axis limits and ticks (identical in both columns)
XLIM, XTICKS = (0, 24), range(0, 25, 4)
YLIM_SOC, YTICKS_SOC = (0, 1), (0, 0.25, 0.5, 0.75, 1.0)
YLIM_ALLOW, YTICKS_ALLOW = (0, 33), range(0, 31, 10)
YLIM_POWER, YTICKS_POWER = (-165, 165), range(-150, 151, 50)

# ---------------------------------------------------------------------- 7. Legends and in-panel notes
LEGEND_HANDLE, LEGEND_HANDLETEXT = 2.0, 0.5
ENV_LEGEND_COLSPACE, ENV_LEGEND_ROWSPACE = 1.6, 0.35
ENV_LEGEND_Y = 0.32                   # BESS legend center within its gap row (0 = bottom, 1 = top)
LIMITER_LEGEND_COLSPACE = 1.2
LIMITER_LEGEND_Y_ABOVE = 0.2          # limiter legend center within its gap row ("above")
LIMITER_LEGEND_Y_BELOW = 0.008        # figure fraction of the legend's bottom edge ("below")
NOTE_DSOH_XY = (0.985, 0.87)          # Delta-SOH note, axes fraction (allowance panel)
NOTE_SOC_X = 0.35                     # left end of the SOC-limit labels [h]


def build():
    """Create the figure from the released data and return it."""
    apply_style()
    # ---------------------------------------------------------------------- 8. Load saved data
    L_nom = read_result("log_nominal_DFM.csv")
    L_tr0 = read_result("log_trial0_DFM.csv")
    dsoh_nom = read_result("results_nominal_summary.csv", index_col=0).loc["DFM", "dSOH_rainflow"]
    mc = read_result("results_mc_trials.csv")
    dsoh_tr0 = mc[(mc.strategy == "DFM") & (mc.trial == 0)].dSOH_rainflow.iloc[0]

    # ---------------------------------------------------------------------- 9. Create figure
    fig = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT))
    gs = fig.add_gridspec(len(HEIGHT_RATIOS), 2, height_ratios=HEIGHT_RATIOS, hspace=HSPACE, wspace=WSPACE,
                          left=LEFT, right=RIGHT, top=TOP, bottom=BOTTOM)
    axes = np.empty((4, 2), dtype=object)
    for r, row in enumerate(AX_ROWS):
        for c in range(2):
            axes[r, c] = fig.add_subplot(gs[row, c], sharex=axes[0, 0], sharey=axes[r, 0])

    # ---------------------------------------------------------------------- 10. Individual subplots
    def stairs(L, y):
        """Step arrays covering the full last interval: its saved value is held until 24 h."""
        y = np.asarray(y, dtype=float)
        return np.r_[L.t_h.values, 24.0], np.r_[y, y[-1]]

    def plot_column(col, L, dsoh):
        ax_soc, ax_allow, ax_power, ax_limiter = axes[:, col]

        # ---- SOC
        ax_soc.plot(np.r_[L.t_h.values, 24.0], np.r_[L.soc.values, L.soc_next.values[-1]], color=C_SOC, lw=LW_SOC)
        for level, label, va, dy in ((SOC_MAX, LABEL_SOC_MAX, "top", -0.02), (SOC_MIN, LABEL_SOC_MIN, "bottom", 0.02)):
            ax_soc.axhline(level, color=C_SOC_LIMIT, lw=LW_SOC_LIMIT, ls=LS_SOC_LIMIT)
            ax_soc.text(NOTE_SOC_X, level + dy, label, ha="left", va=va, fontsize=FONT_NOTE, color=C_NOTE, bbox=NOTE_BOX)

        # ---- Degradation allowance
        ax_allow.step(*stairs(L, L.D_allow * 1e6), where="post", color=C_ALLOW, lw=LW_ALLOW)
        ax_allow.text(*NOTE_DSOH_XY, rf"$\Delta SOH$ = {dsoh*1e5:.2f}$\times10^{{-5}}$", transform=ax_allow.transAxes,
                      ha="right", va="top", fontsize=FONT_NOTE, color=C_NOTE, bbox=NOTE_BOX)

        # ---- Flexibility envelopes and BESS power
        x, phys_dis = stairs(L, L.st_P_flex_dis); _, phys_ch = stairs(L, -L.st_P_flex_ch)
        _, safe_dis = stairs(L, L.st_P_safe_dis); _, safe_ch = stairs(L, -L.st_P_safe_ch)
        ax_power.fill_between(x, phys_ch, phys_dis, step="post", facecolor=C_PHYS_FILL, edgecolor="none", zorder=1)
        ax_power.fill_between(x, safe_ch, safe_dis, step="post", facecolor=C_SAFE_FILL, edgecolor="none", zorder=1.1)
        for y, c_edge in ((phys_dis, C_PHYS_EDGE), (phys_ch, C_PHYS_EDGE), (safe_dis, C_SAFE_EDGE), (safe_ch, C_SAFE_EDGE)):
            ax_power.step(x, y, where="post", color=c_edge, lw=LW_ENVELOPE_EDGE, zorder=1.6)
        for level in (P_RATED_KW, -P_RATED_KW):
            ax_power.axhline(level, color=C_RATED, lw=LW_RATED, ls=LS_RATED, zorder=2)
        ax_power.step(*stairs(L, L.P_sched), where="post", color=C_SCHED, lw=LW_SCHED, zorder=3)
        ax_power.step(*stairs(L, L.P_B), where="post", color=C_EXEC, lw=LW_EXEC, zorder=4)

        # ---- Active limiter: consecutive intervals with the same saved label form one block
        for row, column in ((1, "st_lim_dis"), (0, "st_lim_ch")):
            labels = L[column].values
            start = 0
            for k in range(1, len(labels) + 1):
                if k == len(labels) or labels[k] != labels[start]:
                    ax_limiter.add_patch(plt.Rectangle((L.t_h.values[start], row + 0.06), (k - start) * DT_H, 0.88,
                                                       facecolor=LIMITER_STYLE[labels[start]][0],
                                                       edgecolor=C_LIMITER_EDGE, lw=LW_LIMITER_EDGE))
                    start = k

    plot_column(0, L_nom, dsoh_nom)
    plot_column(1, L_tr0, dsoh_tr0)

    # ---------------------------------------------------------------------- 11. Shared formatting
    for ax in axes[3]:
        ax.set_yticks([0.5, 1.5]); ax.set_yticklabels(LIMITER_ROW_LABELS, fontsize=FONT_LIMITER_TICK)
        ax.set_xlabel(XLABEL, fontsize=FONT_AXIS, labelpad=2)
        ax.grid(False)
    for ax in axes[:3].ravel():
        ax.grid(True, color=GRID_COLOR, alpha=GRID_ALPHA, linewidth=GRID_LW, linestyle=GRID_LS)
    for ax in axes.ravel():
        ax.tick_params(labelsize=FONT_TICK)
    for ax in axes[:3].ravel():
        ax.tick_params(labelbottom=False)
    for ax in axes[:, 1]:
        ax.tick_params(labelleft=False)
    axes[3, 0].tick_params(axis="y", labelsize=FONT_LIMITER_TICK)
    axes[0, 0].set_xlim(*XLIM); axes[0, 0].set_xticks(XTICKS)
    axes[0, 0].set_ylim(*YLIM_SOC); axes[0, 0].set_yticks(YTICKS_SOC)
    axes[1, 0].set_ylim(*YLIM_ALLOW); axes[1, 0].set_yticks(YTICKS_ALLOW)
    axes[2, 0].set_ylim(*YLIM_POWER); axes[2, 0].set_yticks(YTICKS_POWER)
    axes[3, 0].set_ylim(0, 2)
    for r, ylabel in enumerate((YLABEL_SOC, YLABEL_ALLOW, YLABEL_POWER, YLABEL_LIMITER)):
        axes[r, 0].set_ylabel(ylabel, fontsize=FONT_AXIS)
    fig.align_ylabels(axes[:, 0])
    axes[0, 0].set_title(TITLE_LEFT, fontsize=FONT_TITLE)
    axes[0, 1].set_title(TITLE_RIGHT, fontsize=FONT_TITLE)

    # ---------------------------------------------------------------------- Legends: BESS legend above the power panels;
    # limiter legend above the strips or below the time axes (LIMITER_LEGEND_POSITION)
    x_center = 0.5 * (axes[0, 0].get_position().x0 + axes[0, 1].get_position().x1)
    legend_style = dict(frameon=False, handlelength=LEGEND_HANDLE, handletextpad=LEGEND_HANDLETEXT, borderaxespad=0, borderpad=0)

    def gap_y(row, fraction):
        box = gs[row, :].get_position(fig)
        return box.y0 + fraction * (box.y1 - box.y0)

    # Two rows, filled column by column: Rated / Physical / Safe on top, Scheduled / Executed below
    envelope_handles = [Line2D([], [], color=C_RATED, lw=LW_RATED, ls=LS_RATED, label=LABEL_RATED),
                        Line2D([], [], color=C_SCHED, lw=LW_SCHED, label=LABEL_SCHED),
                        Patch(facecolor=C_PHYS_FILL, edgecolor=C_PHYS_EDGE, lw=LW_ENVELOPE_EDGE, label=LABEL_PHYS),
                        Line2D([], [], color=C_EXEC, lw=LW_EXEC, label=LABEL_EXEC),
                        Patch(facecolor=C_SAFE_FILL, edgecolor=C_SAFE_EDGE, lw=LW_ENVELOPE_EDGE, label=LABEL_SAFE)]
    fig.legend(handles=envelope_handles, loc="center", ncol=3, bbox_to_anchor=(x_center, gap_y(GAP_ROW_ENV, ENV_LEGEND_Y)),
               fontsize=FONT_LEGEND_ENV, columnspacing=ENV_LEGEND_COLSPACE, labelspacing=ENV_LEGEND_ROWSPACE, **legend_style)

    limiter_handles = [Line2D([], [], ls="", label=LABEL_LIMITER_LEGEND)]
    limiter_handles += [Patch(facecolor=LIMITER_STYLE[k][0], edgecolor=C_LIMITER_PATCH_EDGE, lw=LW_LIMITER_PATCH_EDGE,
                              label=LIMITER_STYLE[k][1]) for k in ("en", "deg", "net", "rated")]
    if LIMITER_LEGEND_POSITION == "above":
        limiter_loc, limiter_anchor = "center", (x_center, gap_y(GAP_ROW_LIM, LIMITER_LEGEND_Y_ABOVE))
    else:
        limiter_loc, limiter_anchor = "lower center", (x_center, LIMITER_LEGEND_Y_BELOW)
    fig.legend(handles=limiter_handles, loc=limiter_loc, ncol=5, bbox_to_anchor=limiter_anchor, fontsize=FONT_LEGEND_LIMITER,
               columnspacing=LIMITER_LEGEND_COLSPACE, **legend_style)
    return fig
