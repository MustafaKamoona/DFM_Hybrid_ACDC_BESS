"""Parallel execution of many closed-loop days (Monte Carlo trials, ablation, sensitivity).

Every worker process builds its own Study (own PyDAE model instance) and loads the cached
forecast-only precomputation, so results are identical to a serial run. Uncertainty
realizations are regenerated deterministically from (seed, n_trials) in every worker, and the
same realization index is used for every strategy (common random numbers).
"""
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import time

import numpy as np
import pandas as pd

_STUDY = None
_SCEN = None
_RES_CACHE = {}


def _init(pre_path, mc_seed, n_trials, sp_overrides):
    global _STUDY, _SCEN
    from .simulate import Study, default_params
    from .uncertainty import sample_scenarios
    sp = default_params()
    for grp, kv in (sp_overrides or {}).items():
        setattr(sp, grp, replace(getattr(sp, grp), **kv))
    _STUDY = Study(sp)
    _STUDY.pre = pd.read_csv(pre_path)
    _SCEN = sample_scenarios(_STUDY.day, sp.unc, sp.ren.wt_rated_kw, n_trials, mc_seed)


def _reserve(eps_risk):
    if eps_risk not in _RES_CACHE:
        _RES_CACHE[eps_risk] = _STUDY.reserve(eps_risk=eps_risk)
    return _RES_CACHE[eps_risk]


def _task(job):
    """job: dict(strategy, trial (None = nominal), dfm overrides, bess overrides, tag)"""
    from .ems import strategies
    from .simulate import summarize
    st = strategies()[job["strategy"]]
    sp = _STUDY.sp
    dfm0, b0 = sp.dfm, sp.b
    if job.get("dfm"):
        sp.dfm = replace(dfm0, **job["dfm"])
    if job.get("bess"):
        sp.b = replace(b0, **job["bess"])
    try:
        P_res = _reserve(sp.dfm.eps_risk)
        tr = job.get("trial")
        real = None
        if tr is not None:
            real = {"P_pv": _SCEN.P_pv[tr], "P_wt": _SCEN.P_wt[tr], "mult_ac": _SCEN.mult_ac[tr],
                    "mult_dc": _SCEN.mult_dc[tr], "eps_net": _SCEN.eps_net[tr]}
        t0 = time.perf_counter()
        log = _STUDY.run(st, real=real, P_res=P_res, record_envelope=job.get("record_envelope", True))
        s = summarize(log, _STUDY, soh0=sp.b.soh_0)
        s.update({"trial": -1 if tr is None else tr, "tag": job.get("tag", ""), "wall_s": time.perf_counter() - t0,
                  "eps_risk": sp.dfm.eps_risk, "H_f_h": sp.dfm.H_f_h, "soh_0": sp.b.soh_0,
                  "N_ref": sp.dfm.N_ref_cycles_per_day})
        out = {"summary": s}
        if job.get("return_log"):
            out["log"] = log
        return out
    finally:
        sp.dfm, sp.b = dfm0, b0


def run_jobs(jobs, pre_path, mc_seed, n_trials, n_workers=None, sp_overrides=None, verbose=True):
    if n_workers is None:
        # bounded by cores and by free memory (~0.45 GB per worker incl. solver peaks)
        try:
            import psutil
            mem_workers = int(psutil.virtual_memory().available / 0.45e9)
        except Exception:
            mem_workers = 4
        n_workers = max(1, min((os.cpu_count() or 2) - 2, mem_workers, 10))
    # single-threaded BLAS in every worker (parallelism is across processes); this also avoids
    # the ~1 GB per-process memory commit of multi-threaded BLAS buffers on Windows
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[var] = "1"
    out = []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=n_workers, initializer=_init,
                             initargs=(pre_path, mc_seed, n_trials, sp_overrides)) as ex:
        futs = [ex.submit(_task, j) for j in jobs]
        for i, f in enumerate(as_completed(futs)):
            out.append(f.result())
            if verbose and (i + 1) % max(1, len(jobs) // 10) == 0:
                print(f"  {i + 1}/{len(jobs)} jobs done ({time.perf_counter() - t0:.0f} s)")
    return out
