"""Rolling-horizon EMS (one MILP formulation for every BESS strategy; HiGHS via SciPy).

Shrinking horizon from the current interval k to the end of the day, with move blocking:
15-min stages over the first n_fine_steps (always including the executed stage), then
blocks of block_steps intervals (block averages of price/import/curtailment data, block
minima of P_net and block maxima of P_res, i.e. conservative envelope bounds).
Decision variables per step: P_dis, P_ch >= 0, mode binaries zd, zc (no simultaneous charge
and discharge), grid import/export P+/P-, renewable curtailment P_curt (network-aware
strategies only), cycle-depth segment flows/energies (degradation-aware strategies).

    min  sum_j [ c_j P+_j - c_exp P-_j ] dt + lambda_curt sum_j P_curt_j dt
         + lambda_deg * L'(F_k) * sum_j sum_i 0.5 kappa_i (P_dis_ji/eta_dis + eta_ch P_ch_ji) dt / E
         + c_term * terminal SOC shortfall
    s.t. P+_j - P-_j = P_grid0_j - (P_dis_j - P_ch_j) + P_curt_j            (power balance)
         E_{j+1} = E_j + eta_ch P_ch_j dt - P_dis_j dt / eta_dis           (energy)
         0 <= E_j <= (SOC_max - SOC_min) E_model
         P_dis_j <= P_rated zd_j,  P_ch_j <= P_rated zc_j,  zd_j + zc_j <= 1
  DFM envelope (Eq. final_dispatch_constraint), each limiter imposed separately:
         j = 0     : P_dis_0 <= P_safe_dis_k,   P_ch_0 <= P_safe_ch_k          (exact envelope)
         j >= 1    : P_dis_j <= max(0, min(P_rated, P_net_dis_j) - P_res_dis_j)
                     P_dis_j + P_res_dis_j zd_j <= E_j eta_dis / H_f            (energy, SOC-dependent)
                     P_ch_j  <= max(0, min(P_rated, P_net_ch_j) - P_res_ch_j)
                     P_ch_j  + P_res_ch_j zc_j  <= (E_max - E_j)/(eta_ch H_f)
         (zd/zc = discharge/charge mode binaries, zd + zc <= 1; idle always admissible)
                     sum_j dD_j <= D_allow_k                                   (degradation allowance)
                     sum_{i<j} dD_i + (H_f/tau_j) dD_j <= D_allow_k             (sustained deg. limit)
         network-required curtailment: P_curt_j >= C0_j + g_dis P_dis_j - g_ch P_ch_j
"""
from dataclasses import dataclass, field
import time

import numpy as np
import scipy.sparse as sp
from scipy.optimize import milp, LinearConstraint, Bounds


@dataclass
class Strategy:
    name: str
    use_bess: bool = True
    health_aware: bool = True     # E_model = SOH * E_rated (else nameplate E_rated)
    deg_cost: bool = False        # lambda_deg * J_deg in the objective
    envelope: bool = False        # dynamic envelope active (F_en with H_f, safe box)
    deg_limit: bool = False       # F_deg + cumulative allowance
    reserve: bool = False         # uncertainty reserve
    network: bool = False         # F_net + network-required curtailment model


def strategies():
    return {
        "B0": Strategy("B0", use_bess=False),
        "B1": Strategy("B1", health_aware=False),
        "B2": Strategy("B2", health_aware=True, deg_cost=True),
        "DFM": Strategy("DFM", deg_cost=True, envelope=True, deg_limit=True, reserve=True, network=True),
        # ablation (M0 == DFM)
        "M1": Strategy("M1", health_aware=False, deg_cost=True, envelope=True, deg_limit=False, reserve=True, network=True),
        "M2": Strategy("M2", deg_cost=True, envelope=True, deg_limit=True, reserve=False, network=True),
        "M3": Strategy("M3", deg_cost=True, envelope=True, deg_limit=True, reserve=True, network=False),
    }


class _Builder:
    def __init__(self):
        self.n = 0
        self.lb, self.ub, self.c, self.integ = [], [], [], []
        self.rows, self.cols, self.vals, self.rlb, self.rub = [], [], [], [], []
        self.m = 0

    def var(self, size, lb=0.0, ub=np.inf, cost=0.0, integer=False):
        idx = np.arange(self.n, self.n + size)
        self.n += size
        self.lb += list(np.broadcast_to(lb, size)); self.ub += list(np.broadcast_to(ub, size))
        self.c += list(np.broadcast_to(cost, size)); self.integ += [1 if integer else 0] * size
        return idx

    def row(self, idx_coef, lo, hi):
        for i, a in idx_coef:
            self.rows.append(self.m); self.cols.append(int(i)); self.vals.append(float(a))
        self.rlb.append(lo); self.rub.append(hi)
        self.m += 1

    def solve(self, rel_gap, time_limit):
        A = sp.csr_matrix((self.vals, (self.rows, self.cols)), shape=(self.m, self.n))
        res = milp(c=np.array(self.c), integrality=np.array(self.integ),
                   bounds=Bounds(np.array(self.lb), np.array(self.ub)),
                   constraints=LinearConstraint(A, np.array(self.rlb), np.array(self.rub)),
                   options={"mip_rel_gap": rel_gap, "time_limit": time_limit, "disp": False})
        return res


def solve_ems(st: Strategy, k, soc, E_model, F_k, F_cyc_day, data, env0=None):
    """data: dict with keys
       b (BESSParams), ems (EMSParams), dfm (DFMParams), deg (XuDegradation),
       price, P_grid0, P_res_avail, C0, g_dis, g_ch, P_net_dis, P_net_ch, P_res_dis, P_res_ch,
       lambda_deg, soc_target
    env0: Envelope at step k (DFM-type strategies) -> exact first-step box.
    Returns dict with first-step decision and diagnostics."""
    b, ems, dfm, deg = data["b"], data["ems"], data["dfm"], data["deg"]
    K = ems.n_steps_day
    dt = ems.dt_h
    # ------------------------------------------------------------ planning stages (move blocking)
    # exact 15-min stages over the first n_fine_steps, then blocks of block_steps intervals
    steps = np.arange(k, K)
    nf = min(len(steps), ems.n_fine_steps)
    stages = [steps[i:i + 1] for i in range(nf)]
    rest = steps[nf:]
    stages += [rest[i:i + ems.block_steps] for i in range(0, len(rest), ems.block_steps)]
    H = len(stages)
    tau = np.array([len(sg) * dt for sg in stages])
    mean = lambda a: np.array([np.mean(a[sg]) for sg in stages])
    smin = lambda a: np.array([np.min(a[sg]) for sg in stages])
    smax = lambda a: np.array([np.max(a[sg]) for sg in stages])
    price, grid0 = mean(data["price"]), mean(data["P_grid0"])
    Emax = (b.soc_max - b.soc_min) * E_model
    E0 = min(max((soc - b.soc_min) * E_model, 0.0), Emax)
    P = b.P_rated_kw
    bl = _Builder()

    # ------------------------------------------------------------ variables
    d_ub = np.full(H, P)
    c_ub = np.full(H, P)
    if st.envelope:
        Pres_d = smax(data["P_res_dis"]) if st.reserve else np.zeros(H)
        Pres_c = smax(data["P_res_ch"]) if st.reserve else np.zeros(H)
        Pnet_d = smin(data["P_net_dis"]) if st.network else np.full(H, P)
        Pnet_c = smin(data["P_net_ch"]) if st.network else np.full(H, P)
        d_ub = np.minimum(d_ub, np.maximum(0.0, np.minimum(Pnet_d, P) - Pres_d))
        c_ub = np.minimum(c_ub, np.maximum(0.0, np.minimum(Pnet_c, P) - Pres_c))
        if env0 is not None:
            d_ub[0] = min(d_ub[0], env0.P_safe_dis)
            c_ub[0] = min(c_ub[0], env0.P_safe_ch)
    d = bl.var(H, 0.0, d_ub)
    c = bl.var(H, 0.0, c_ub)
    # operating-mode binaries: zd = discharge mode, zc = charge mode, idle when both are 0
    zd = bl.var(H, 0.0, 1.0, integer=True)
    zc = bl.var(H, 0.0, 1.0, integer=True)
    E = bl.var(H + 1, 0.0, Emax)
    pp = bl.var(H, 0.0, np.inf, cost=price * tau)
    pm = bl.var(H, 0.0, np.inf, cost=-ems.price_export * tau)
    term = bl.var(1, 0.0, np.inf, cost=2.0 * max(data["price"]) / max(b.eta_dis, 1e-9))
    if st.network:
        C0, gd, gc = mean(data["C0"]), mean(data["g_dis"]), mean(data["g_ch"])
        curt = bl.var(H, 0.0, mean(data["P_res_avail"]), cost=ems.lambda_curt * tau)
    # tiny throughput regularization (tie-breaking only)
    for idx in (d, c):
        for i in idx:
            bl.c[i] += 1e-6

    # degradation segments
    use_seg = st.deg_cost or (st.envelope and st.deg_limit)
    if use_seg:
        kappa, w, _ = deg.segment_costs()
        J = len(kappa)
        Eseg = w * E_model
        dseg = bl.var(H * J, 0.0, np.inf)
        cseg = bl.var(H * J, 0.0, np.inf)
        eseg = bl.var((H + 1) * J, 0.0, Eseg)
        dL = float(deg.dL(F_k))
        # degradation (SOH units) per kW of segment flow during a stage of duration tau_j
        unit_d = dL * 0.5 * kappa[None, :] * tau[:, None] / (b.eta_dis * E_model)
        unit_c = dL * 0.5 * kappa[None, :] * tau[:, None] * b.eta_ch / E_model
        if st.deg_cost:
            lam = data["lambda_deg"]
            for j in range(H):
                for i in range(J):
                    bl.c[dseg[j * J + i]] += lam * unit_d[j, i]
                    bl.c[cseg[j * J + i]] += lam * unit_c[j, i]

    # ------------------------------------------------------------ constraints
    bl.row([(E[0], 1.0)], E0, E0)
    for j in range(H):
        bl.row([(E[j + 1], 1.0), (E[j], -1.0), (c[j], -b.eta_ch * tau[j]), (d[j], tau[j] / b.eta_dis)], 0.0, 0.0)
        bl.row([(d[j], 1.0), (zd[j], -P)], -np.inf, 0.0)
        bl.row([(c[j], 1.0), (zc[j], -P)], -np.inf, 0.0)
        bl.row([(zd[j], 1.0), (zc[j], 1.0)], -np.inf, 1.0)
        coefs = [(pp[j], 1.0), (pm[j], -1.0), (d[j], 1.0), (c[j], -1.0)]
        if st.network:
            coefs.append((curt[j], -1.0))
        bl.row(coefs, grid0[j], grid0[j])
        if st.network:
            # P_curt >= C0 + g_dis P_dis - g_ch P_ch
            bl.row([(curt[j], 1.0), (d[j], -gd[j]), (c[j], gc[j])], C0[j], np.inf)
        if st.envelope and j >= 1:
            # Energy limiter with reserve in each operating mode (exact max{0, .} semantics of
            # Eqs. safe_dis_flex / safe_ch_flex; the idle point is always admissible):
            #   discharge mode: P_dis_j + P_res_dis_j <= E_j eta_dis / H_f
            #   charge mode   : P_ch_j  + P_res_ch_j  <= (E_max - E_j) / (eta_ch H_f)
            bl.row([(d[j], 1.0), (zd[j], Pres_d[j]), (E[j], -b.eta_dis / dfm.H_f_h)], -np.inf, 0.0)
            bl.row([(c[j], 1.0), (zc[j], Pres_c[j]), (E[j], 1.0 / (b.eta_ch * dfm.H_f_h))],
                   -np.inf, Emax / (b.eta_ch * dfm.H_f_h))
    # terminal energy (soft)
    E_target = (data["soc_target"] - b.soc_min) * E_model
    bl.row([(E[H], 1.0), (term[0], 1.0)], E_target, np.inf)

    if use_seg:
        # initial segment energies: deepest segments full first
        e_init = np.zeros(J)
        rem = E0
        for i in range(J - 1, -1, -1):
            e_init[i] = min(Eseg, rem)
            rem -= e_init[i]
        for i in range(J):
            bl.row([(eseg[i], 1.0)], e_init[i], e_init[i])
        for j in range(H):
            bl.row([(d[j], 1.0)] + [(dseg[j * J + i], -1.0) for i in range(J)], 0.0, 0.0)
            bl.row([(c[j], 1.0)] + [(cseg[j * J + i], -1.0) for i in range(J)], 0.0, 0.0)
            for i in range(J):
                bl.row([(eseg[(j + 1) * J + i], 1.0), (eseg[j * J + i], -1.0),
                        (cseg[j * J + i], -b.eta_ch * tau[j]), (dseg[j * J + i], tau[j] / b.eta_dis)], 0.0, 0.0)
        if st.envelope and st.deg_limit:
            from .envelope import degradation_allowance
            D_allow, _, _ = degradation_allowance(deg, F_k, F_cyc_day, dfm)
            # cumulative allowance over the plan, and the planning analogue of the sustained
            # degradation limit (Eqs. deg_dis_limit / deg_ch_limit): the degradation already
            # planned before stage j plus that of sustaining stage j's power over H_f must not
            # exceed D_allow.
            coefs = []
            for j in range(H):
                stage = []
                for i in range(J):
                    stage += [(dseg[j * J + i], unit_d[j, i]), (cseg[j * J + i], unit_c[j, i])]
                sus = dfm.H_f_h / tau[j]
                bl.row(coefs + [(v, a * sus) for v, a in stage], -np.inf, D_allow + 1e-12)
                coefs = coefs + stage
            bl.row(coefs, -np.inf, D_allow + 1e-12)

    t0 = time.perf_counter()
    res = bl.solve(ems.mip_rel_gap, ems.time_limit_s)
    t_solve = time.perf_counter() - t0
    if res.x is None:
        return {"ok": False, "P_B": 0.0, "t_solve": t_solve, "status": res.status, "msg": res.message}
    x = res.x
    out = {"ok": True, "status": res.status, "t_solve": t_solve, "obj": res.fun,
           "P_B": float(x[d[0]] - x[c[0]]), "P_dis": float(x[d[0]]), "P_ch": float(x[c[0]]),
           "plan_P_B": x[d] - x[c], "plan_E": x[E], "n_var": bl.n, "n_con": bl.m}
    if st.network:
        out["plan_curt"] = x[curt]
    return out
