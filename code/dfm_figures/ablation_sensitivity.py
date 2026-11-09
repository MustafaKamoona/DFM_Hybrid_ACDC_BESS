"""Ablation of the DFM components and sensitivity to the DFM design parameters.

Ablation panel: Monte Carlo mean of each metric for the ablated formulations M1 (no health/degradation
limitation), M2 (no uncertainty reserve) and M3 (no network envelope), relative to the complete
formulation M0 (= DFM), on a symmetric-logarithmic axis. Sensitivity panels: change of each Monte
Carlo mean with respect to the nominal parameter value (dashed vertical line).

Data: data/ablation/results_ablation_summary.csv, data/sensitivity/results_sensitivity_summary.csv.
"""
from .common import *  # noqa: F401,F403  (style, palette, study constants, read_result)

# ---------------------------------------------------------------------- 1. Figure and layout
FIG_NAME = "Fig_ablation_sensitivity"
FIG_WIDTH, FIG_HEIGHT = 7.2, 5.0
HSPACE, WSPACE = 0.34, 0.34
LEFT, RIGHT, TOP, BOTTOM = 0.098, 0.99, 0.99, 0.095

# ---------------------------------------------------------------------- 2. Fonts
FONT_AXIS, FONT_TICK, FONT_LEGEND, FONT_ABL_LEGEND, FONT_ANNOTATION = 11.5, 9.5, 10.5, 10.0, 10.0

# ---------------------------------------------------------------------- 3. Line, marker and bar styles
LW_LINE, MS_MARKER = 1.5, 4.5
C_ZERO, LW_ZERO, LS_ZERO = INK_SECONDARY, 0.9, "-"               # zero change
C_NOMINAL, LW_NOMINAL, LS_NOMINAL = INK_SECONDARY, 1.0, (0, (4, 2))   # nominal parameter value
BAR_WIDTH, BAR_STEP = 0.24, 0.26
C_BAR_EDGE, LW_BAR_EDGE = INK_PRIMARY, 0.5

# ---------------------------------------------------------------------- 4. Grid
GRID_COLOR, GRID_ALPHA, GRID_LW, GRID_LS = "#8a8a8a", 0.95, 1.5, ":"

# ---------------------------------------------------------------------- 5. Ablation panel
COLORS_ABL = {"M1": STRATEGY_COLORS["M1"], "M2": STRATEGY_COLORS["M2"], "M3": STRATEGY_COLORS["M3"]}
NAMES_ABL = {"M1": STRATEGY_LABELS["M1"], "M2": STRATEGY_LABELS["M2"], "M3": STRATEGY_LABELS["M3"]}
ABL_METRICS = [("rel_mc_cost_corr_EUR_pct", "Cost"), ("rel_mc_E_curt_kWh_pct", r"$E_{\mathrm{curt}}$"),
               ("rel_mc_dSOH_rainflow_pct", r"$\Delta\mathrm{SOH}$"), ("rel_mc_E_dev_kWh_pct", "Imbal.")]
YLABEL_ABL = r"Change vs $\mathcal{M}_0$ [%]"
SYMLOG_LINTHRESH, YLIM_ABL = 10, (-15, 2000)
ABL_LEGEND_LOC, ABL_LEGEND_ROWSPACE = "upper left", 0.25

# ---------------------------------------------------------------------- 6. Sensitivity panels: (summary column, legend label, color, marker)
SERIES = [("mc_mean_cost_corr_EUR", "Cost", CAT["blue"], "o"),
          ("mc_mean_dSOH_rainflow", r"$\Delta\mathrm{SOH}$", CAT["orange"], "s"),
          ("mc_mean_E_dev_kWh", "Uncovered imbalance", CAT["aqua"], "^"),
          ("mc_mean_mean_P_safe_dis_kW", r"Mean $P^{\mathrm{dis}}_{\mathrm{safe}}$", CAT["violet"], "D")]
YLABEL_SENS = "Change vs nominal [%]"
# parameter -> x-axis label, nominal value, x-ticks (the tested values), tick format, x-axis scale, y-limits (None = automatic)
PARAMETERS = {"H_f_h": dict(xlabel=r"Support horizon $H_{\mathrm{f}}$ [h]", nominal=H_F_H, xticks=(0.25, 0.5, 1, 2), fmt="{:g}", log2=True, ylim=None),
              "eps_risk": dict(xlabel=r"Risk tolerance $\varepsilon$", nominal=0.05, xticks=(0.01, 0.05, 0.1, 0.2), fmt="{:g}", log2=False, ylim=None),
              "soh_0": dict(xlabel=r"Initial health $\mathrm{SOH}_0$", nominal=SOH_0, xticks=(0.85, 0.90, 0.95, 1.00), fmt="{:.2f}", log2=False, ylim=None),
              "N_ref_cycles_per_day": dict(xlabel=r"Allowance $N_{\mathrm{ref}}$ [cycles/day]", nominal=N_REF, xticks=(0.25, 0.5, 1, 1.5), fmt="{:g}", log2=False, ylim=None)}

# ---------------------------------------------------------------------- 7. Framed legend (bottom-right cell, describes the sensitivity panels)
LEGEND_FRAME_COLOR = "darkred"
LEGEND_FRAME_LW = 1.0
LEGEND_FRAME_FACE = "white"
LEGEND_FRAME_ALPHA = 0.98
LEGEND_TITLE = "Sensitivity metrics"   # None removes the title
LEGEND_LOC, LEGEND_ANCHOR = "center right", (1.0, 0.5)   # frame aligned with the right edge of the panel above it
LEGEND_PAD, LEGEND_ROWSPACE, LEGEND_HANDLE, LEGEND_HANDLETEXT = 0.8, 0.5, 2.0, 0.5

# ---------------------------------------------------------------------- 8. Annotations (values are read from the saved summary; offsets in points from the bar top)
SHOW_ANNOTATIONS = True               # master switch
ANNOTATIONS = [dict(show=True, config="M3", metric="rel_mc_E_curt_kWh_pct", offset=(5, 0), ha="left", va="center"),
               dict(show=True, config="M2", metric="rel_mc_E_dev_kWh_pct", offset=(0, 2), ha="center", va="bottom")]


def build():
    """Create the figure from the released data and return it."""
    apply_style()
    # ---------------------------------------------------------------------- 9. Load saved data
    ablsum = read_result("results_ablation_summary.csv", index_col=0)
    summ = read_result("results_sensitivity_summary.csv")

    # ---------------------------------------------------------------------- 10. Create figure (ablation, H_f, eps / SOH_0, N_ref, legend)
    fig = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT))
    gs = fig.add_gridspec(2, 3, hspace=HSPACE, wspace=WSPACE, left=LEFT, right=RIGHT, top=TOP, bottom=BOTTOM)
    ax0 = fig.add_subplot(gs[0, 0])
    axes = [fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
    ax_legend = fig.add_subplot(gs[1, 2]); ax_legend.axis("off")

    # ---------------------------------------------------------------------- 11. Ablation panel
    x = np.arange(len(ABL_METRICS))
    metric_columns = [m for m, _ in ABL_METRICS]
    configs = ("M1", "M2", "M3")
    for i, cfg in enumerate(configs):
        vals = [ablsum.loc[cfg, m] for m in metric_columns]
        ax0.bar(x + (i - 1) * BAR_STEP, vals, width=BAR_WIDTH, color=COLORS_ABL[cfg], edgecolor=C_BAR_EDGE, linewidth=LW_BAR_EDGE,
                label=NAMES_ABL[cfg], zorder=2.5)
    ax0.axhline(0, color=C_ZERO, lw=LW_ZERO, ls=LS_ZERO, zorder=3)
    ax0.set_xticks(x, labels=[label for _, label in ABL_METRICS])
    ax0.set_ylabel(YLABEL_ABL, fontsize=FONT_AXIS)
    ax0.set_yscale("symlog", linthresh=SYMLOG_LINTHRESH); ax0.set_ylim(*YLIM_ABL)
    ax0.tick_params(labelsize=FONT_TICK)
    ax0.grid(False, axis="x")
    ax0.grid(True, axis="y", color=GRID_COLOR, alpha=GRID_ALPHA, linewidth=GRID_LW, linestyle=GRID_LS)
    ax0.set_axisbelow(True)
    ax0.legend(frameon=False, fontsize=FONT_ABL_LEGEND, loc=ABL_LEGEND_LOC, labelspacing=ABL_LEGEND_ROWSPACE, handlelength=1.4, handletextpad=0.5)
    if SHOW_ANNOTATIONS:
        for note in ANNOTATIONS:
            if note["show"]:
                value = ablsum.loc[note["config"], note["metric"]]
                bar_x = metric_columns.index(note["metric"]) + (configs.index(note["config"]) - 1) * BAR_STEP
                ax0.annotate(f"{value:+.0f}%", xy=(bar_x, value), xytext=note["offset"], textcoords="offset points",
                             ha=note["ha"], va=note["va"], fontsize=FONT_ANNOTATION, color=INK_PRIMARY)

    # ---------------------------------------------------------------------- 12. Sensitivity panels
    for ax, (par, p) in zip(axes, PARAMETERS.items()):
        d = summ[summ.parameter == par].sort_values("value")
        ref = d[np.isclose(d.value, p["nominal"])].iloc[0]
        for col, label, color, marker in SERIES:
            ax.plot(d.value, 100 * (d[col] - ref[col]) / ref[col], "-", marker=marker, ms=MS_MARKER, lw=LW_LINE, color=color, label=label)
        ax.axhline(0, color=C_ZERO, lw=LW_ZERO, ls=LS_ZERO)
        ax.axvline(p["nominal"], color=C_NOMINAL, lw=LW_NOMINAL, ls=LS_NOMINAL)
        ax.set_xlabel(p["xlabel"], fontsize=FONT_AXIS); ax.set_ylabel(YLABEL_SENS, fontsize=FONT_AXIS)
        if p["log2"]:
            ax.set_xscale("log", base=2)
        ax.set_xticks(p["xticks"], labels=[p["fmt"].format(v) for v in p["xticks"]])
        ax.minorticks_off()
        if p["ylim"] is not None:
            ax.set_ylim(*p["ylim"])
        ax.tick_params(labelsize=FONT_TICK)
        ax.grid(True, color=GRID_COLOR, alpha=GRID_ALPHA, linewidth=GRID_LW, linestyle=GRID_LS)
        # Hide the vertical gridline lying under the nominal marker, so that it reads as a clean dashed line
        for loc, tick in zip(ax.get_xticks(), ax.xaxis.get_major_ticks()):
            if np.isclose(loc, p["nominal"]):
                tick.gridline.set_visible(False)
    fig.align_ylabels([ax0, axes[2]])
    fig.align_ylabels([axes[0], axes[3]])
    fig.align_xlabels(axes[2:])

    # ---------------------------------------------------------------------- 13. Framed legend
    framed = ax_legend.legend(*axes[0].get_legend_handles_labels(), loc=LEGEND_LOC, bbox_to_anchor=LEGEND_ANCHOR, borderaxespad=0, title=LEGEND_TITLE,
                              fontsize=FONT_LEGEND, title_fontsize=FONT_LEGEND, frameon=True, fancybox=False, shadow=False,
                              edgecolor=LEGEND_FRAME_COLOR, facecolor=LEGEND_FRAME_FACE, framealpha=LEGEND_FRAME_ALPHA,
                              borderpad=LEGEND_PAD, labelspacing=LEGEND_ROWSPACE, handlelength=LEGEND_HANDLE, handletextpad=LEGEND_HANDLETEXT)
    framed.get_frame().set_linewidth(LEGEND_FRAME_LW)
    return fig
