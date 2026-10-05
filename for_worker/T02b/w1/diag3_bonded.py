"""T02b diagnostic 3: contact topology during annealed load-unload.

Tracks per increment: n_real contacts, n_bonded (cohesion unbroken),
n_frictional (new, never bonded), max overlap, S11.
"""
import sys, os
_WTROOT = "/home/hatch/workspace/yade-rve-pann/.worktrees/T02b/w1"
if _WTROOT not in sys.path:
    sys.path.insert(0, _WTROOT)

from yade import O
from yade.minieigenHP import Matrix3
from rve.generate import make_rve_packing
from rve.homogenize import homogenized_stress, get_reference_hsize

U = {"vf": 0.2, "rMean": 0.04, "rRelFuzz": 0.3,
     "E_soft": 1e7, "E_stiff": 5e7, "cohesion": 1e6}
F_UNIAX = Matrix3(0.9, 0, 0, 0, 1, 0, 0, 0, 1)
F_I = Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 1)


def topo():
    n_real = n_bond = n_fric = 0
    max_pen = 0.0
    for i in O.interactions:
        if not i.isReal:
            continue
        n_real += 1
        if i.phys.__class__.__name__ == "CohFrictPhys":
            if bool(i.phys.cohesionBroken):
                n_fric += 1
            else:
                n_bond += 1
        try:
            max_pen = max(max_pen, -i.geom.penetrationDepth)
        except Exception:
            pass
    return n_real, n_bond, n_fric, max_pen


def probe(F_target, n_increments=20, steps_per_increment=80, damping=0.7,
          tag=""):
    h0 = Matrix3(get_reference_hsize())
    hT = F_target * h0
    h_start = Matrix3(O.cell.hSize)
    newton = next(e for e in O.engines
                  if e.__class__.__name__ == "NewtonIntegrator")
    old = newton.damping
    print(" F11      S11        nReal  nBond  nFric  maxPen", flush=True)
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
            nr, nb, nf, mp = topo()
            print(" %.4f  %+.3e  %5d  %5d  %5d  %.3e  [%s]"
                  % (F[0, 0], S[0, 0], nr, nb, nf, mp, tag), flush=True)
    finally:
        newton.damping = old


info = make_rve_packing(u=U, seed=42, n_spheres=1000, verbose=False)
nr, nb, nf, mp = topo()
print("[diag3] after build: nReal=%d nBond=%d nFric=%d" % (nr, nb, nf),
      flush=True)
probe(F_UNIAX, tag="load")
probe(F_I, tag="unload")
print("DIAG3 DONE", flush=True)
