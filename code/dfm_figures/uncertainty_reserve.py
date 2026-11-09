"""Net forecast-error distribution and directional uncertainty reserves.

Percentile bands (P1-P99, P5-P95, P25-P75) of the DC-subsystem net forecast error and the directional
reserves at risk tolerance 0.05. The reserve curves are the released values. The percentile bands are
not stored; they are recomputed from the same 20,000 forecast-error trajectories used by the study,
drawn deterministically (fixed seed, same generator and draw order) from the released nominal profiles.
Before plotting, the figure checks that these samples reproduce every released reserve value (four risk
tolerances, both directions); otherwise it stops. No network simulation or optimization is run.

Data: data/uncertainty/results_reserve.csv, data/nominal/results_profiles.csv.
"""
from .common import *  # noqa: F401,F403  (style, palette, study constants, read_result)

# ---------------------------------------------------------------------- 1. Figure and layout
FIG_NAME = "Fig_uncertainty_reserve"
FIG_WIDTH, FIG_HEIGHT = 7.2, 3.9
GAP_LEGEND = 0.19                     # height ratio of the row holding the legend (the plot has ratio 1)
HSPACE = 0.03
LEFT, RIGHT, TOP, BOTTOM = 0.09, 0.99, 0.995, 0.115

# ---------------------------------------------------------------------- 2. Fonts
FONT_AXIS, FONT_TICK, FONT_LEGEND, FONT_ANNOTATION = 11.5, 9.5, 10.5, 10.5

# ---------------------------------------------------------------------- 3. Percentile bands (opaque and drawn outermost first, so colors never mix)
# Each entry: (lower percentile, upper percentile, fill color, alpha, boundary color, boundary line width)
BANDS = [(1, 99, "#d4e5f8", 1.0, "#7fa9d9", 0.6),
         (5, 95, "#94bdec", 1.0, "#5f93d0", 0.6),
         (25, 75, "#4a86cf", 1.0, "#2f68ad", 0.6)]

# ---------------------------------------------------------------------- 4. Reserve curves and zero line (drawn above the bands)
RESERVE_EPS = 0.05                    # risk tolerance of the plotted reserves
C_DIS, LW_DIS, LS_DIS = "#c2410c", 1.8, "-"
C_CH, LW_CH, LS_CH = "#c2410c", 1.8, (0, (4, 1.6))
C_ZERO, LW_ZERO, LS_ZERO = INK_PRIMARY, 0.8, "-"

# ---------------------------------------------------------------------- 5. Grid
GRID_COLOR, GRID_ALPHA, GRID_LW, GRID_LS = "#8a8a8a", 0.95, 0.85, ":"

# ---------------------------------------------------------------------- 6. Axes
XLABEL, XLIM, XTICKS = "Time [h]", (0, 24), range(0, 25, 4)
YLABEL = r"Net forecast error $\epsilon^{\mathrm{net}}_{k}$ [kW]"
YLIM, YTICKS = (-100, 100), range(-100, 101, 25)

# ---------------------------------------------------------------------- 7. Legend (two coordinated rows in the gap row)
LABEL_DIS = rf"Discharge reserve $P^{{\mathrm{{dis}}}}_{{\mathrm{{res}},k}}$, $\varepsilon={RESERVE_EPS:g}$"
LABEL_CH = rf"Negative charging reserve $-P^{{\mathrm{{ch}}}}_{{\mathrm{{res}},k}}$, $\varepsilon={RESERVE_EPS:g}$"
LEGEND_HANDLE, LEGEND_HANDLETEXT = 2.4, 0.5
BAND_LEGEND_COLSPACE, BAND_LEGEND_Y = 2.2, 0.80      # row center within the gap row (0 = bottom, 1 = top)
RESERVE_LEGEND_COLSPACE, RESERVE_LEGEND_Y = 2.2, 0.24

# ---------------------------------------------------------------------- 8. Annotations (spread = P99 - P1, read from the saved reserves at eps = 0.01)
SHOW_ANNOTATIONS = True               # master switch
ANNOTATIONS = [dict(show=True, t_h=11.75, text="Maximum spread: {:.1f} kW", xytext=(14.9, 92), ha="left", va="center"),
               dict(show=True, t_h=3.75, text="Minimum spread: {:.1f} kW", xytext=(3.875, 46), ha="center", va="center")]
ARROW_STYLE = dict(arrowstyle="-|>", color=INK_PRIMARY, lw=1.0, shrinkA=1, shrinkB=1, mutation_scale=9)
NOTE_BOX = dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.8)


def build():
    """Create the figure from the released data and return it."""
    apply_style()
    # ---------------------------------------------------------------------- 9. Load saved data
    prof = read_result("results_profiles.csv")
    rv = read_result("results_reserve.csv")
    t = prof.t_h.values

    # ---------------------------------------------------------------------- 10. Deterministic reconstruction (generator, seed and draw order of the study)
    # Forecast-error samples of the reserve set (draw order of the study: PV, wind, AC demand, DC demand)
    def ar1(rng, n_steps, n_paths, phi):
        x = np.empty((n_paths, n_steps))
        x[:, 0] = rng.standard_normal(n_paths)
        s = np.sqrt(1.0 - phi ** 2)
        for k in range(1, n_steps):
            x[:, k] = phi * x[:, k - 1] + s * rng.standard_normal(n_paths)
        return x

    rng = np.random.default_rng(RESERVE_SEED)
    K = len(prof)
    x_pv, x_wt, x_ac, x_dc = (ar1(rng, K, N_SAMPLES_RESERVE, AR1_PHI) for _ in range(4))
    P_pv_hat, P_wt_hat, P_dc_hat = prof.P_pv_kW.values, prof.P_wt_kW.values, prof.P_dc_kW.values
    eps_pv = np.maximum(0.0, P_pv_hat[None, :] * (1.0 + SIGMA_PV_REL * x_pv)) - P_pv_hat[None, :]
    sw = SIGMA_WT_REL * P_wt_hat[None, :] + SIGMA_WT_ABS_PU * WT_RATED_KW
    eps_wt = np.clip(P_wt_hat[None, :] + sw * x_wt, 0.0, WT_RATED_KW) - P_wt_hat[None, :]
    eps_dc = SIGMA_LOAD_REL * x_dc * P_dc_hat[None, :]
    eps_net = eps_dc - eps_pv - eps_wt

    # ---------------------------------------------------------------------- 11. Integrity checks (stop here, before plotting and export, if any fails)
    for eps in (0.01, 0.05, 0.10, 0.20):
        assert np.allclose(np.quantile(np.maximum(eps_net, 0.0), 1.0 - eps, axis=0), rv[f"P_res_dis_eps{eps:g}"], rtol=0, atol=1e-9)
        assert np.allclose(np.quantile(np.maximum(-eps_net, 0.0), 1.0 - eps, axis=0), rv[f"P_res_ch_eps{eps:g}"], rtol=0, atol=1e-9)
    percentiles = {p: np.percentile(eps_net, p, axis=0) for band in BANDS for p in band[:2]}
    # The reserves are the band boundaries: P95 = discharge reserve and P5 = -charging reserve at eps = 0.05; likewise P99 and P1 at eps = 0.01
    for eps, upper, lower in ((0.05, 95, 5), (0.01, 99, 1)):
        assert np.allclose(percentiles[upper], rv[f"P_res_dis_eps{eps:g}"], rtol=0, atol=1e-9)
        assert np.allclose(percentiles[lower], -rv[f"P_res_ch_eps{eps:g}"], rtol=0, atol=1e-9)
    print("Redrawn forecast-error samples reproduce all saved reserves.")

    def stairs(y):
        """Step arrays covering the full last interval: its value is held until 24 h."""
        y = np.asarray(y, dtype=float)
        return np.r_[t, 24.0], np.r_[y, y[-1]]

    # ---------------------------------------------------------------------- 12. Create figure
    fig = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT))
    gs = fig.add_gridspec(2, 1, height_ratios=[GAP_LEGEND, 1.0], hspace=HSPACE, left=LEFT, right=RIGHT, top=TOP, bottom=BOTTOM)
    ax = fig.add_subplot(gs[1, 0])

    # ---------------------------------------------------------------------- 13. Bands, zero line and reserves
    for lower, upper, fill, alpha, edge, lw_edge in BANDS:
        x_step, y_low = stairs(percentiles[lower])
        ax.fill_between(x_step, y_low, stairs(percentiles[upper])[1], step="post", facecolor=fill, edgecolor=edge, linewidth=lw_edge, alpha=alpha)
    ax.axhline(0, color=C_ZERO, lw=LW_ZERO, ls=LS_ZERO, zorder=2)
    ax.step(*stairs(rv[f"P_res_dis_eps{RESERVE_EPS:g}"]), where="post", color=C_DIS, lw=LW_DIS, ls=LS_DIS, zorder=3)
    ax.step(*stairs(-rv[f"P_res_ch_eps{RESERVE_EPS:g}"]), where="post", color=C_CH, lw=LW_CH, ls=LS_CH, zorder=3)

    # ---------------------------------------------------------------------- 14. Formatting
    ax.set_xlim(*XLIM); ax.set_xticks(XTICKS); ax.set_xlabel(XLABEL, fontsize=FONT_AXIS, labelpad=2)
    ax.set_ylim(*YLIM); ax.set_yticks(YTICKS); ax.set_ylabel(YLABEL, fontsize=FONT_AXIS)
    ax.tick_params(labelsize=FONT_TICK)
    ax.grid(True, color=GRID_COLOR, alpha=GRID_ALPHA, linewidth=GRID_LW, linestyle=GRID_LS)

    # ---------------------------------------------------------------------- 15. Annotations (arrow to the upper envelope at the middle of the interval)
    spread = rv["P_res_dis_eps0.01"].values + rv["P_res_ch_eps0.01"].values
    if SHOW_ANNOTATIONS:
        for note in ANNOTATIONS:
            if note["show"]:
                k = int(np.flatnonzero(t == note["t_h"])[0])
                ax.annotate(note["text"].format(spread[k]), xy=(note["t_h"] + 0.5 * DT_H, rv["P_res_dis_eps0.01"].values[k]), xytext=note["xytext"],
                            ha=note["ha"], va=note["va"], fontsize=FONT_ANNOTATION, color=INK_PRIMARY, bbox=NOTE_BOX, arrowprops=ARROW_STYLE, zorder=4)

    # ---------------------------------------------------------------------- 16. Legend: percentile bands on the first row, reserves on the second
    x_center = 0.5 * (ax.get_position().x0 + ax.get_position().x1)
    legend_style = dict(frameon=False, handlelength=LEGEND_HANDLE, handletextpad=LEGEND_HANDLETEXT, borderaxespad=0, borderpad=0)

    def gap_y(fraction):
        box = gs[0, 0].get_position(fig)
        return box.y0 + fraction * (box.y1 - box.y0)

    band_handles = [Patch(facecolor=fill, edgecolor=edge, linewidth=lw_edge, alpha=alpha, label=f"P{lower}–P{upper}")
                    for lower, upper, fill, alpha, edge, lw_edge in BANDS]
    reserve_handles = [Line2D([], [], color=C_DIS, lw=LW_DIS, ls=LS_DIS, label=LABEL_DIS),
                       Line2D([], [], color=C_CH, lw=LW_CH, ls=LS_CH, label=LABEL_CH)]
    fig.legend(handles=band_handles, loc="center", ncol=len(band_handles), bbox_to_anchor=(x_center, gap_y(BAND_LEGEND_Y)),
               fontsize=FONT_LEGEND, columnspacing=BAND_LEGEND_COLSPACE, **legend_style)
    fig.legend(handles=reserve_handles, loc="center", ncol=len(reserve_handles), bbox_to_anchor=(x_center, gap_y(RESERVE_LEGEND_Y)),
               fontsize=FONT_LEGEND, columnspacing=RESERVE_LEGEND_COLSPACE, **legend_style)
    return fig
