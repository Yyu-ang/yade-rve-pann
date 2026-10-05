"""T02b pilot: bonded (CohFrictMat) packing + 10% compression cycle.

Checks:
 1. make_rve_packing works with CohFrictMat/ScGeom6D/CohesionMoment engines
    (densify servo behavior, prestress level, broken-bond count at build)
 2. cohesion=1e6 N: zero bond breakage over a 10% uniaxial compression
    load-unload cycle
 3. early read of the G1c dissipation ratio with bonded contacts

Pass: build OK, broken bonds == 0 after load and after unload.
"""
import sys, os
_WTROOT = "/home/hatch/workspace/yade-rve-pann/.worktrees/T02b/w1"
if _WTROOT not in sys.path:
    sys.path.insert(0, _WTROOT)

from yade.minieigenHP import Matrix3
from rve.generate import make_rve_packing, count_broken_bonds
from rve.homogenize import homogenized_stress, get_reference_hsize
from rve.convergence import frobenius_norm

U = {"vf": 0.2, "rMean": 0.04, "rRelFuzz": 0.3,
     "E_soft": 1e7, "E_stiff": 5e7, "cohesion": 1e6}
E_REF = U["E_soft"]
F_UNIAX = Matrix3(0.9, 0, 0, 0, 1, 0, 0, 0, 1)
F_I = Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 1)

info = make_rve_packing(u=U, seed=42, n_spheres=1000, verbose=True)
print("[pilot] built: contacts=%d meanStress=%.3e broken@build=%d"
      % (info["n_contacts"], info["mean_stress"], info["n_broken_bonds"]),
      flush=True)
assert info["n_broken_bonds"] == 0, "bonds broken during densify!"

# local copy of the (fixed) quasi-static probe with history, mirroring
# test_gates._probe_F_history
from yade import O


def probe_hist(F_target, n_increments=40, steps_per_increment=120, damping=0.7):
    h0 = Matrix3(get_reference_hsize())
    hT = F_target * h0
    h_start = Matrix3(O.cell.hSize)
    newton = next(e for e in O.engines
                  if e.__class__.__name__ == "NewtonIntegrator")
    old = newton.damping
    S0, sig0, F0, J0 = homogenized_stress()
    hist = [{"F": Matrix3(F0), "S": Matrix3(S0), "sigma": Matrix3(sig0),
             "J": J0}]
    try:
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
            S, sig, F, J = homogenized_stress()
            hist.append({"F": Matrix3(F), "S": Matrix3(S),
                         "sigma": Matrix3(sig), "J": J})
    finally:
        newton.damping = old
    return hist


def work(hist):
    V0 = get_reference_hsize().determinant()
    W, Fp = 0.0, None
    for rec in hist:
        F, sig, J = rec["F"], rec["sigma"], rec["J"]
        if Fp is not None:
            dF = F - Fp
            P = J * sig * F.inverse().transpose()
            W += V0 * sum(P[r, c] * dF[r, c]
                          for r in range(3) for c in range(3))
        Fp = Matrix3(F)
    return W


h_load = probe_hist(F_UNIAX)
S_loaded = h_load[-1]["S"]
b_load = count_broken_bonds()
print("[pilot] loaded: S11=%.3e Pa broken_bonds=%d"
      % (S_loaded[0, 0], b_load), flush=True)

h_unload = probe_hist(F_I, n_increments=30, steps_per_increment=80)
S_res = h_unload[-1]["S"]
b_unload = count_broken_bonds()
print("[pilot] unloaded: residual ||S||/E=%.3e broken_bonds=%d"
      % (frobenius_norm(S_res) / E_REF, b_unload), flush=True)

W_load = work(h_load)
W_diss = W_load + work(h_unload)
print("[pilot] W_load=%.4e J W_diss=%.4e J dissipation_ratio=%.4f"
      % (W_load, W_diss, W_diss / W_load), flush=True)

assert b_load == 0 and b_unload == 0, "BOND BREAKAGE in 10% domain!"
print("PILOT PASSED: cohesion=1e6 N -> zero breakage in 10% compression cycle")
