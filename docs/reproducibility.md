# Reproducibility

## Levels

| Level | Scope | Status in this release |
|---|---|---|
| 1 | Regenerate the nine data-driven figures (seven figures of the paper, two supporting figures) from `data/` | Supported; tested |
| 2 | Inspect and re-analyze the released results | Supported (all result files are included) |
| 3 | Re-run the network simulations | Supported with the external Topology-3 model (`external/README.md`); executed only on Windows x64 |
| 4 | Re-run the EMS, Monte Carlo, ablation and sensitivity experiments | Supported with level 3; the 2,117 closed-loop runs took about 16 h of single-process time in total (executed in parallel) |

## Tested environment

| Purpose | Environment |
|---|---|
| Figure reproduction (level 1) | Python 3.10, NumPy 2.2, pandas 2.3, Matplotlib 3.10.9 (fresh environment from `requirements.txt`), Times New Roman installed. All nine regenerated PDFs are identical at pixel level to the files in `figures/`, with identical text and fonts. |
| Full study (levels 3-4) | Windows x64, Python 3.10, PyDAE 1.5.1 with Intel MKL, SciPy 1.15 (HiGHS MILP solver) |

Other Matplotlib versions or fonts may introduce small typographic differences without changing the
plotted values.

## Determinism

- Forecast-error samples for the reserves: 20,000 AR(1) trajectories, seed 12345. `Fig_uncertainty_reserve`
  redraws them from the released nominal profiles to plot the percentile bands and verifies that they
  reproduce every released reserve value before plotting.
- Monte Carlo realizations: 100 trajectories, seed 2026; the same realization index is used for every
  strategy (paired comparison).
- The network operating point of each interval is solved from the same stored initial guess, so that
  results do not depend on the evaluation order.
- The MILP is solved with a relative optimality gap of 1e-4 and a 20-s time limit (no time-limit hit
  was recorded).

## Not stored in this release

- The forecast-error sample ensembles (regenerated deterministically from the seeds).
- The per-interval logs of the Monte Carlo, ablation and sensitivity runs; only realization 0 of DFM
  is stored per interval. Per-trial indicators are stored for all runs.
- The compiled network solver (platform-specific; built from the external model).

## Implementation notes

- **Exact battery state update.** After each interval the linearized degradation is advanced with the
  realized cycle stress $`\tfrac{1}{2}\lvert G(\delta_{k+1}) - G(\delta_k)\rvert`$ and the calendar stress (evaluated
  at the mean SOC of the interval), and the state of health follows the full nonlinear capacity-fade
  function, $`SOH_{k+1} = 1 - L(F_{k+1})`$ (`code/dfm_acdc/bess.py`). Reported health consumption uses
  rainflow counting of the realized SOC trajectory.
- **Linearized degradation limit of the envelope.** The degradation limit uses a local linearization of
  the cycle-induced degradation only: $`\Delta D_k(P) = L'(F_k)\,\tfrac{1}{2}\lvert G(\delta_{\mathrm{end}}(P)) - G(\delta_k)\rvert`$.
  The day's used cycle stress $`F^{\mathrm{cyc}}_k`$ is accumulated in stress units, and both the budget and
  the used part are converted with the slope of the current interval,
  $`D^{\max} = L'(F_k)\,N_{\mathrm{ref}}\,G(DoD_{\mathrm{ref}})`$ and $`D^{\mathrm{cyc}}_k = L'(F_k)\,F^{\mathrm{cyc}}_k`$
  (`code/dfm_acdc/envelope.py`); the slope is re-evaluated at every interval. $`L'(F_k)`$ therefore cancels
  exactly in this feasibility condition, which reduces to
  $`\tfrac{1}{2}\lvert G(\delta_{\mathrm{end}}(P)) - G(\delta_k)\rvert \le N_{\mathrm{ref}}\,G(DoD_{\mathrm{ref}}) - F^{\mathrm{cyc}}_k`$.
  The cancellation does not apply to the nonlinear increment $`L(F_k+\Delta F) - L(F_k)`$. The EMS applies
  the same slope over its planning horizon, with the convex-hull representation of $`G`$
  (`code/dfm_acdc/ems.py`).
- **Degradation-model figure.** `Fig_degradation_model` (supporting figure) keeps the typography of the
  study's working figures (Matplotlib default fonts and panel letters).

## Adopted network limits

Feeder-head current limits: 724.6 / 231.9 / 434.8 A (R01/I01/C01); Industrial (I01): 160-kVA current basis.
AC voltage 0.95-1.05 pu of 231 V (phase-to-neutral); DC voltage 0.95-1.05 pu of 800 V.

## Figure conventions

Step plots hold the value of the last interval (23:45-24:00) until 24 h; no additional data
point is created.

## Re-running the study

```bash
pip install -r requirements-full.txt
# provide the external model in external/topology3/ (see external/README.md)
jupyter lab code/experiments/
```

Run notebooks 01-11 in order. Results are written to `output/results/` and diagnostic figures to
`output/experiment_figures/`; the released `data/` and `figures/` folders are not modified.
