"""T02b cohesion sweep: smallest cohesion with zero breakage in 10% domain.

Small packing (400 spheres) for speed; same u otherwise.
For each cohesion: build (with anneal) -> probe F=diag(0.9,1,1) ->
count broken bonds. Prints a table.
"""
import sys, os
_WTROOT = "/home/hatch/workspace/yade-rve-pann/.worktrees/T02b/w1"
if _WTROOT not in sys.path:
    sys.path.insert(0, _WTROOT)

from yade import O
from yade.minieigenHP import Matrix3
from rve.generate import make_rve_packing, count_broken_bonds
from rve.homogenize import homogenized_stress, get_reference_hsize

F_UNIAX = Matrix3(0.9, 0, 0, 0, 1, 0, 0, 0, 1)


def probe(F_target, n_increments=20, steps_per_increment=60, damping=0.7):
    h0 = Matrix3(get_reference_hsize())
    hT = F_target * h0
    h_start = Matrix3(O.cell.hSize)
    newton = next(e for e in O.engines
                  if e.__class__.__name__ == "NewtonIntegrator")
    old = newton.damping
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
    finally:
        newton.damping = old
    S, _, _, _ = homogenized_stress()
    return S


print("cohesion(N)   broken@build  broken@load   S11(Pa)", flush=True)
for coh in [1e6, 3e6, 1e7, 3e7, 1e8]:
    U = {"vf": 0.2, "rMean": 0.05, "rRelFuzz": 0.3,
         "E_soft": 1e7, "E_stiff": 5e7, "cohesion": coh}
    info = make_rve_packing(u=U, seed=42, n_spheres=400, verbose=False)
    b0 = info["n_broken_bonds"]
    S = probe(F_UNIAX)
    b1 = count_broken_bonds()
    print("%.1e   %d   %d   %.3e" % (coh, b0, b1, S[0, 0]), flush=True)
print("SWEEP DONE", flush=True)
