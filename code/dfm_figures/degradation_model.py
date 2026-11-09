"""Battery degradation model used by the study (supporting figure).

Panels: (a) cycle-depth stress Phi(delta) and the stress G(delta) of a full cycle starting at SOC_max
(including the SOC stress at its mean SOC); (b) marginal stress of the ten equal cycle-depth segments,
exact and as represented in the EMS by the lower convex envelope; (c) state of health as a function of
the linearized degradation F (capacity fade with SEI-film formation), with the initial health values
of the sensitivity analysis and the end-of-life threshold.

The curves are evaluated from the closed-form aging model of Xu et al. (IEEE Trans. Smart Grid 9(2),
2018) with its published LMO-cell parameters; no simulation is involved. Before plotting, the
linearized degradation F_0 and the slope dL/dF are checked against the released parameter file.
This figure keeps the typography of the study's working figures (Matplotlib default sans-serif fonts
and panel letters).

Data: data/validation/results_degradation_parameters.csv.
"""
from .common import *  # noqa: F401,F403  (style, palette, study constants, read_result)

# ----------------------------------------------------------------------- aging model (Xu et al., 2018)
K_D1, K_D2, K_D3, K_SIGMA, SIGMA_REF = 1.4e5, -0.501, -1.23e5, 1.04, 0.5   # cycle-depth and SOC stress
ALPHA_SEI, BETA_SEI = 5.75e-2, 121.0                                       # SEI-film capacity fade
SOH_EOL, J_SEGMENTS = 0.80, 10                                            # end of life; EMS depth segments


def phi_stress(delta):
    """Cycle-depth stress Phi(delta) = 1 / (k_d1 delta^k_d2 + k_d3)."""
    d = np.maximum(np.asarray(delta, dtype=float), 0.0)
    out = np.zeros_like(d)
    nz = d > 1e-12
    out[nz] = 1.0 / (K_D1 * d[nz] ** K_D2 + K_D3)
    return out if out.ndim else float(out)


def s_sigma(soc):
    """State-of-charge stress S_sigma(sigma) = exp(k_sigma (sigma - sigma_ref))."""
    return np.exp(K_SIGMA * (np.asarray(soc, dtype=float) - SIGMA_REF))


def G_stress(delta):
    """Stress of a full cycle of depth delta starting at SOC_max (mean SOC = SOC_max - delta/2)."""
    delta = np.asarray(delta, dtype=float)
    return phi_stress(delta) * s_sigma(SOC_MAX - 0.5 * delta)


def L_fade(F):
    """Accumulated degradation D = L(F), including the initial SEI-film formation."""
    return 1.0 - ALPHA_SEI * np.exp(-BETA_SEI * F) - (1.0 - ALPHA_SEI) * np.exp(-F)


def dL_fade(F):
    """Slope dL/dF of the capacity-fade function."""
    return ALPHA_SEI * BETA_SEI * np.exp(-BETA_SEI * F) + (1.0 - ALPHA_SEI) * np.exp(-F)


def F_from_soh(soh):
    """Linearized degradation F corresponding to a state of health (inverse of L by bisection)."""
    D = 1.0 - soh
    if D <= 0.0:
        return 0.0
    lo, hi = 0.0, 5.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if L_fade(mid) < D:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ----------------------------------------------------------------------- presentation settings
FIG_NAME = "Fig_degradation_model"
FIG_WIDTH, FIG_HEIGHT = 7.16, 2.4
C_PHI, C_G, C_EXACT, C_HULL, C_FADE, C_POINT, C_EOL = CAT["blue"], CAT["orange"], INK_MUTED, CAT["aqua"], CAT["violet"], INK_PRIMARY, LIMIT_RED
LW_MAIN, LW_EOL, MS_POINT, BAR_WIDTH = 1.3, 0.8, 4, 0.4
FONT_AXIS, FONT_TICK, FONT_LEGEND, FONT_PANEL = 9, 7.5, 6.5, 8
LABELS = {"phi": r"$\Phi(\delta)$", "G": r"$G(\delta)$", "exact": "exact", "hull": "convex hull (EMS)", "eol": "EOL"}
XLABELS = (r"Cycle depth $\delta$", "Depth segment", "Linearized degradation $F$")
YLABELS = (r"Stress per cycle [$10^{-5}$]", r"Marginal stress [$10^{-5}$/SOC]", "SOH")
SOH_POINTS, F_MAX = (1.0, 0.95, 0.90, 0.85), 0.25
PANEL_XY = (-0.32, 1.04)


def build():
    """Create the figure and return it."""
    apply_style(serif=False)

    # The model must reproduce the released degradation parameters of each initial SOH
    saved = read_result("results_degradation_parameters.csv")
    for soh, f_saved, dl_saved in zip(saved.SOH_0, saved.F_0, saved.dL_dF):
        assert np.isclose(F_from_soh(soh), f_saved, atol=1e-12) and np.isclose(dL_fade(F_from_soh(soh)), dl_saved)

    # EMS cycle-depth segments: exact slopes and their lower convex envelope (pool-adjacent-violators)
    w = (SOC_MAX - SOC_MIN) / J_SEGMENTS
    slopes = np.diff(G_stress(np.arange(J_SEGMENTS + 1) * w)) / w
    merged = []
    for s in slopes:
        merged.append([s, 1])
        while len(merged) > 1 and merged[-2][0] > merged[-1][0]:
            s2, n2 = merged.pop()
            s1, n1 = merged.pop()
            merged.append([(s1 * n1 + s2 * n2) / (n1 + n2), n1 + n2])
    kappa = np.concatenate([[s] * n for s, n in merged])

    fig, axs = plt.subplots(1, 3, figsize=(FIG_WIDTH, FIG_HEIGHT))
    d = np.linspace(0.005, SOC_MAX - SOC_MIN, 200)
    axs[0].plot(d, phi_stress(d) * 1e5, color=C_PHI, lw=LW_MAIN, label=LABELS["phi"])
    axs[0].plot(d, G_stress(d) * 1e5, color=C_G, lw=LW_MAIN, label=LABELS["G"])
    x = np.arange(len(kappa))
    axs[1].bar(x - 0.2, slopes * 1e5, width=BAR_WIDTH, color=C_EXACT, label=LABELS["exact"])
    axs[1].bar(x + 0.2, kappa * 1e5, width=BAR_WIDTH, color=C_HULL, label=LABELS["hull"])
    axs[1].set_xticks(x); axs[1].set_xticklabels([str(i + 1) for i in x])
    F = np.linspace(0, F_MAX, 300)
    axs[2].plot(F, 1 - L_fade(F), color=C_FADE, lw=LW_MAIN)
    for soh in SOH_POINTS:
        axs[2].plot(F_from_soh(soh), soh, "o", ms=MS_POINT, color=C_POINT)
    axs[2].axhline(SOH_EOL, color=C_EOL, lw=LW_EOL, ls="--", label=LABELS["eol"])
    for a, xlab, ylab, lab in zip(axs, XLABELS, YLABELS, "abc"):
        a.set_xlabel(xlab, fontsize=FONT_AXIS); a.set_ylabel(ylab, fontsize=FONT_AXIS)
        a.tick_params(labelsize=FONT_TICK)
        a.legend(frameon=False, fontsize=FONT_LEGEND)
        a.text(*PANEL_XY, f"({lab})", transform=a.transAxes, fontsize=FONT_PANEL, va="top")
    fig.tight_layout()
    return fig
