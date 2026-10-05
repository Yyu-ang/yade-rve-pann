"""T02 gate self-test: Phase 0 G1c / G2a / G2b (DEM hyperelastic-compatibility gates).

Run from the worktree root:
    yadedaily -x rve/tests/test_gates.py

Gates (dispatch for_manager/T02/dispatch.md, DOD):
 G1c hyperelastic compatibility (FrictMat, compression/shear domain only;
     tensionless behavior is physical and NOT tested):
     - load-unload closure: compress to F=diag(0.9,1,1), unload to F=I,
       residual ||S||/E_soft < 1e-3
     - path independence: two paths to F*=[[0.9,0.05,0],[0,1,0],[0,0,1]],
       ||S_A - S_B||/||S_A|| < 5%
     - dissipation ratio: hysteresis-loop work / loading work < 10%
       (hysteresis measures TOTAL mechanical dissipation incl. damping,
       hence a conservative upper bound on frictional dissipation)
 G2a isotropy: uniaxial compression along x/y/z, secant-stiffness spread
     (max-min)/mean < 10%
 G2b representativeness: fixed u, >=5 seeds,
     Delta = std(||S||)/mean(||S||) <= 0.5%  (paper §1.2 definition)

Each gate prints its numbers; a summary table with GO/NO-GO is printed at
the end. Exit code is 0 after the table (per DOD-4); verdicts live in the
table and in for_manager/T02/w1/handoff.md. Thresholds are NOT relaxed:
any exceedance is reported as NO-GO with the measured numbers.

2-core budget: <=1500 spheres; total runtime target ~30 min.
"""

import sys
import os
import math

# worktree root on sys.path so `import rve...` works inside yadedaily
_WTROOT = os.getcwd()
if _WTROOT not in sys.path:
    sys.path.insert(0, _WTROOT)

from yade.minieigenHP import Matrix3

from rve.generate import make_rve_packing
from rve.homogenize import (
    get_reference_hsize, homogenized_stress, deformation_invariants,
)
from rve.convergence import (
    representativeness_test, frobenius_norm, CONVERGENCE_TOL, N_REP_SEEDS,
)

SEED = 42
N_SPHERES = 1000
U = {"vf": 0.2, "rMean": 0.04, "rRelFuzz": 0.3,
     "E_soft": 1e7, "E_stiff": 5e7}
E_REF = U["E_soft"]          # stress normalization scale (matrix modulus)
PROBE_KW = dict(n_increments=40, steps_per_increment=120, damping=0.7)
UNLOAD_KW = dict(n_increments=30, steps_per_increment=80, damping=0.7)

F_I = Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 1)
F_UNIAX = Matrix3(0.9, 0, 0, 0, 1, 0, 0, 0, 1)


def _probe_F_history(F_target, n_increments=40, steps_per_increment=120,
                     damping=0.7):
    """probe_F variant recording (F, S, sigma, J) after every increment.

    Same affine-carry quasi-static driving as rve.homogenize.probe_F
    (T01 fix), with one correction: the cell path is interpolated from the
    CURRENT hSize (not the reference hSize), so unloading / multi-stage
    paths do not jump. The pre-probe state is recorded as hist[0] so work
    integration includes the first increment.
    Returns list of dicts with Matrix3 entries.
    """
    from yade import O
    newton = None
    for e in O.engines:
        if e.__class__.__name__ == "NewtonIntegrator":
            newton = e
            break
    old_damping = newton.damping if newton else None
    if not isinstance(F_target, Matrix3):
        F_target = Matrix3(*[F_target[r][c] for r in range(3) for c in range(3)])
    h0 = Matrix3(get_reference_hsize())
    hT = F_target * h0
    h_start = Matrix3(O.cell.hSize)  # current cell (may differ from h0)
    S0, sigma0, F0, J0 = homogenized_stress()
    hist = [{"F": Matrix3(F0), "S": Matrix3(S0),
             "sigma": Matrix3(sigma0), "J": J0}]
    try:
        if newton:
            newton.damping = damping
        h_prev = Matrix3(h_start)
        for k in range(1, n_increments + 1):
            t = float(k) / n_increments
            h = h_start * (1.0 - t) + hT * t
            F_incr = h * h_prev.inverse()
            for b in O.bodies:
                b.state.pos = F_incr * b.state.pos
            O.cell.hSize = h
            h_prev = Matrix3(h)
            O.run(steps_per_increment, True)
            S, sigma, F, J = homogenized_stress()
            hist.append({"F": Matrix3(F), "S": Matrix3(S),
                         "sigma": Matrix3(sigma), "J": J})
    finally:
        if newton and old_damping is not None:
            newton.damping = old_damping
    return hist


def _incremental_work(hist):
    """External work W = sum_k V0 * (P_k : dF_k) over a probe history.

    P_k = J_k * sigma_k * F_k^-T (1st Piola-Kirchhoff), V0 = reference volume.
    """
    V0 = get_reference_hsize().determinant()
    W = 0.0
    F_prev = None
    for rec in hist:
        F, sigma, J = rec["F"], rec["sigma"], rec["J"]
        if F_prev is not None:
            dF = F - F_prev
            P = J * sigma * F.inverse().transpose()
            W += V0 * sum(P[r, c] * dF[r, c]
                          for r in range(3) for c in range(3))
        F_prev = Matrix3(F)
    return W


def gate_g1c():
    """G1c: load-unload closure, dissipation ratio, path independence."""
    print("=" * 64, flush=True)
    print("G1c: hyperelastic compatibility (FrictMat, compression/shear)",
          flush=True)
    res = {}

    # --- 1. load-unload closure + hysteresis dissipation ---
    make_rve_packing(u=U, seed=SEED, n_spheres=N_SPHERES, verbose=False)
    h_load = _probe_F_history(F_UNIAX, **PROBE_KW)
    S_loaded = h_load[-1]["S"]
    h_unload = _probe_F_history(F_I, **UNLOAD_KW)
    S_res = h_unload[-1]["S"]
    res["residual_rel"] = frobenius_norm(S_res) / E_REF
    res["loaded_S11"] = S_loaded[0, 0]
    W_load = _incremental_work(h_load)
    W_unload = _incremental_work(h_unload)
    W_diss = W_load + W_unload   # net work over the closed cycle
    res["W_load"] = W_load
    res["W_diss"] = W_diss
    res["dissipation_ratio"] = W_diss / W_load if W_load > 0 else float("nan")
    res["closure_go"] = res["residual_rel"] < 1e-3
    res["dissipation_go"] = res["dissipation_ratio"] < 0.10
    print("[G1c-1] load S11=%.3e Pa | unload residual ||S||/E=%.3e "
          "(DOD <1e-3) -> %s"
          % (res["loaded_S11"], res["residual_rel"],
             "GO" if res["closure_go"] else "NO-GO"), flush=True)
    print("[G1c-1] W_load=%.4e J W_diss(hysteresis)=%.4e J ratio=%.3f "
          "(DOD <0.10) -> %s"
          % (W_load, W_diss, res["dissipation_ratio"],
             "GO" if res["dissipation_go"] else "NO-GO"), flush=True)

    # --- 2. path independence to a combined compression+shear state ---
    F_star = Matrix3(0.9, 0.05, 0, 0, 1, 0, 0, 0, 1)
    F_mid = Matrix3(0.95, 0, 0, 0, 1, 0, 0, 0, 1)
    make_rve_packing(u=U, seed=SEED, n_spheres=N_SPHERES, verbose=False)
    S_A = _probe_F_history(F_star, **PROBE_KW)[-1]["S"]
    make_rve_packing(u=U, seed=SEED, n_spheres=N_SPHERES, verbose=False)
    _probe_F_history(F_mid, n_increments=20, steps_per_increment=80,
                     damping=0.7)
    S_B = _probe_F_history(F_star, n_increments=30, steps_per_increment=120,
                           damping=0.7)[-1]["S"]
    dS = S_A - S_B
    res["path_rel"] = frobenius_norm(dS) / max(frobenius_norm(S_A), 1e-30)
    res["path_go"] = res["path_rel"] < 0.05
    print("[G1c-2] path A vs B: ||S_A-S_B||/||S_A||=%.4f (DOD <0.05) -> %s"
          % (res["path_rel"], "GO" if res["path_go"] else "NO-GO"),
          flush=True)

    res["go"] = res["closure_go"] and res["dissipation_go"] and res["path_go"]
    return res


def gate_g2a():
    """G2a: isotropy via uniaxial compression along x/y/z.

    Each direction uses a FRESH packing built with the same seed, hence an
    identical initial microstructure: any response difference is pure
    (an)isotropy, uncontaminated by prior loading history.
    """
    print("=" * 64, flush=True)
    print("G2a: isotropy (x/y/z uniaxial compression, identical packings)",
          flush=True)
    res = {}
    dirs = {
        "x": (Matrix3(0.9, 0, 0, 0, 1, 0, 0, 0, 1), (0, 0)),
        "y": (Matrix3(1, 0, 0, 0, 0.9, 0, 0, 0, 1), (1, 1)),
        "z": (Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 0.9), (2, 2)),
    }
    k = {}
    for d, (F_d, (r, c)) in dirs.items():
        make_rve_packing(u=U, seed=SEED, n_spheres=N_SPHERES, verbose=False)
        S = _probe_F_history(F_d, **PROBE_KW)[-1]["S"]
        k[d] = abs(S[r, c]) / 0.1   # secant stiffness |dS|/|dF|
        print("[G2a] dir %s: S_%d%d=%.3e Pa  k=%.3e Pa"
              % (d, r + 1, c + 1, S[r, c], k[d]), flush=True)
    vals = list(k.values())
    res["k"] = k
    res["spread"] = (max(vals) - min(vals)) / (sum(vals) / len(vals))
    res["go"] = res["spread"] < 0.10
    print("[G2a] stiffness spread (max-min)/mean = %.4f (DOD <0.10) -> %s"
          % (res["spread"], "GO" if res["go"] else "NO-GO"), flush=True)
    return res


def gate_g2b():
    """G2b: representativeness over >=5 seeds, Delta <= 0.5%."""
    print("=" * 64, flush=True)
    print("G2b: representativeness (fixed u, %d seeds)" % N_REP_SEEDS,
          flush=True)
    out = representativeness_test(
        U, n_seeds=N_REP_SEEDS, seed0=100, n_spheres=N_SPHERES,
        verbose=False,
        probe_kwargs=dict(n_increments=40, steps_per_increment=120,
                          damping=0.7))
    for i, nrm in enumerate(out["norms"]):
        print("[G2b] seed=%d ||S||=%.6e Pa" % (100 + i, nrm), flush=True)
    out["go"] = out["converged"]
    print("[G2b] Delta=%.4f%% (DOD <=0.5%%) -> %s"
          % (100.0 * out["delta"], "GO" if out["go"] else "NO-GO"), flush=True)
    return out


if __name__ == "__main__":
    r1c = gate_g1c()
    r2a = gate_g2a()
    r2b = gate_g2b()
    print("=" * 64, flush=True)
    print("T02 GATE SUMMARY (thresholds NOT relaxed)", flush=True)
    print("  G1c closure      ||S||/E=%.2e  (<1e-3)  -> %s"
          % (r1c["residual_rel"], "GO" if r1c["closure_go"] else "NO-GO"),
          flush=True)
    print("  G1c dissipation  ratio=%.3f    (<0.10)  -> %s"
          % (r1c["dissipation_ratio"],
             "GO" if r1c["dissipation_go"] else "NO-GO"), flush=True)
    print("  G1c path-indep.  rel=%.4f   (<0.05)  -> %s"
          % (r1c["path_rel"], "GO" if r1c["path_go"] else "NO-GO"), flush=True)
    print("  G1c OVERALL ................................ -> %s"
          % ("GO" if r1c["go"] else "NO-GO"), flush=True)
    print("  G2a isotropy     spread=%.4f (<0.10)  -> %s"
          % (r2a["spread"], "GO" if r2a["go"] else "NO-GO"), flush=True)
    print("  G2b represent.   Delta=%.4f%% (<=0.5%%) -> %s"
          % (100.0 * r2b["delta"], "GO" if r2b["go"] else "NO-GO"), flush=True)
    print("GATES DONE", flush=True)
