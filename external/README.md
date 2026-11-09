# External dependency: hybrid CIGRE LV Topology-3 model

The DFM study uses the validated PyDAE model of the hybrid AC/DC CIGRE European low-voltage benchmark
(Topology-3) without modification. The model is published with its own article and repository and is
not duplicated here:

- Article: M. A. Kamoona and J. M. Mauricio, "Hybrid AC/DC Topologies for the CIGRE Low-Voltage
  Benchmark Performance Evaluation", *Eng* 7(4):147, 2026, https://doi.org/10.3390/eng7040147
- Repository: https://github.com/MustafaKamoona/New_Topologies_CIGRE
- Archive: https://zenodo.org/records/18325627

It is needed only to re-run the network simulations and the numerical study (reproducibility levels
3-4); the figures and results can be reproduced and inspected from `../data/` alone.

## Files

Create the folder `external/topology3/` (or set the environment variable `DFM_TOPOLOGY3_DIR` to another
folder) with the following files of the Topology-3 repository:

| File in this folder | Source in the Topology-3 repository |
|---|---|
| `cigre_eu_lv_acdc_6w.hjson` | `acdc/acdc_6w/droops/cigre_eu_lv_acdc_6w.hjson` (network data) |
| `cigre_eu_lv_acdc_6w.py` | `acdc/acdc_6w/droops/cigre_eu_lv_acdc_6w.py` (generated model) |
| `cigre_eu_lv_acdc_tools.py` | `acdc/acdc_6w/droops/cigre_eu_lv_acdc_tools.py` (load-profile tool) |
| `xy_0.json` | `acdc/acdc_6w/droops/xy_0.json` (initial guess) |
| `cigre_lv.xlsx` | `acdc/common/cigre_lv.xlsx` (load cases and profiles) |
| `reference_outputs/voltage_*_T3_case{1,3}.csv`, `reference_outputs/current_*_T3_case{1,3}.csv` | `acdc/acdc_6w/droops/` (eight files; used only by the regression test in notebook 01) |

These are the versions used in the study (identical file contents).

## Compiled solver

The generated model loads a compiled solver extension. Build it in `external/topology3/` with the
builder of the Topology-3 repository (`acdc/acdc_6w/droops/cigre_eu_lv_acdc_6w_builder.ipynb`):

```python
from pydae.urisi.urisi_builder import urisi
grid = urisi("cigre_eu_lv_acdc_6w.hjson")
grid.uz_jacs = False
grid.construct("cigre_eu_lv_acdc_6w")
grid.compile_mkl("cigre_eu_lv_acdc_6w")
```

The study was executed with PyDAE 1.5.1, Python 3.10 and Windows x64 (Intel MKL). The compiled
extension is platform-specific; other platforms have not been tested.

Notebook `code/experiments/01_topology3_regression.ipynb` re-runs the original Topology-3 experiments
and checks that the model reproduces the original outputs before it is used.
