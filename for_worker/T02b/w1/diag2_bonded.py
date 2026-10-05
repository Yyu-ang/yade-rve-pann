"""T02b diagnostic 2: annealed bonded packing load-unload.

- snapshots bonded interaction ids after anneal (true bond set)
- S11(F11) hysteresis curves
- sum of frictDissip (frictional sliding dissipation)
- O.energy keys
Distinguishes true bond breakage from new (frictional) contacts,
and separates dissipation sources.
"""
import sys, os
_WTROOT = "/home/hatch/workspace/yade-rve-pann/.worktrees/T02b/w1"
if _WTROOT not in sys.path:
    sys.path.insert(0, _WTROOT)

from yade import O
from yade.minieigenHP import Matrix3
from rve import generate as G
from rve.generate import make_rve_packing
from rve.homogenize import homogenized_stress, get_reference_hsize
from rve.convergence import frobenius_norm

U = {"vf": 0.2, "rMean": 0.04, "rRelFuzz": 0.3,
     "E_soft": 1e7, "E_stiff": 5e7, "cohesion": 1e6}
E_REF = U["E_soft"]
F_UNIAX = Matrix3(0.9, 0, 0, 0, 1, 0, 0, 0, 1)
F_I = Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 1)


def bonded_ids():
    return set((i.id1, i.id2) for i in O.interactions if i.isReal
               and i.phys.__class__.__name__ == "CohFrictPhys"
               and not bool(i.phys.cohesionBroken))


def true_broken(ref_ids):
    n = 0
    for i in O.interactions:
        if (i.id1, i.id2) in ref_ids and i.isReal \
                and bool(i.phys.cohesionBroken):
            n += 1
    return n


def frict_dissip():
    return sum(i.phys.frictDissip for i in O.interactions if i.isReal
               and i.phys.__class__.__name__ == "CohFrictPhys")


def probe(F_target, n_increments=40, steps_per_increment=120, damping=0.7):
    h0 = Matrix3(get_reference_hsize())
    hT = F_target * h0
    h_start = Matrix3(O.cell.hSize)
    newton = next(e for e in O.engines
                  if e.__class__.__name__ == "NewtonIntegrator")
    old = newton.damping
    pts = []
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
            S, _, F, _ = homogenized_stress()
            pts.append((F[0, 0], S[0, 0]))
    finally:
        newton.damping = old
    return pts


info = make_rve_packing(u=U, seed=42, n_spheres=1000, verbose=False)
ref = bonded_ids()
print("[diag2] bonded ids at build: %d" % len(ref), flush=True)
print("[diag2] O.energy keys:", sorted(O.energy.keys()), flush=True)

load = probe(F_UNIAX)
S_loaded = load[-1][1]
print("[diag2] loaded: S11=%.3e true_broken=%d frictDissip=%.4e"
      % (S_loaded, true_broken(ref), frict_dissip()), flush=True)

unload = probe(F_I, n_increments=30, steps_per_increment=80)
S_res = unload[-1][1]
E = O.energy
print("[diag2] unloaded: S11=%.3e true_broken=%d frictDissip=%.4e"
      % (S_res, true_broken(ref), frict_dissip()), flush=True)
print("[diag2] O.energy:", dict(E), flush=True)

print(" F11      S11_load    S11_unload")
for (f1, s1), (f2, s2) in zip(load[::4], unload[::3]):
    print(" %.4f  %+.3e  %+.3e" % (f1, s1, s2))
