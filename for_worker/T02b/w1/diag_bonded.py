"""T02b diagnostic: why is bonded dissipation so large?

Records S11(F11) hysteresis loop + per-contact frictDissip sum +
max particle rotation, to separate frictional sliding dissipation
from moment/plasticity/viscous sources.
"""
import sys, os
_WTROOT = "/home/hatch/workspace/yade-rve-pann/.worktrees/T02b/w1"
if _WTROOT not in sys.path:
    sys.path.insert(0, _WTROOT)

from yade import O
from yade.minieigenHP import Matrix3, Vector3
from rve.generate import make_rve_packing
from rve.homogenize import homogenized_stress, get_reference_hsize

U = {"vf": 0.2, "rMean": 0.04, "rRelFuzz": 0.3,
     "E_soft": 1e7, "E_stiff": 5e7, "cohesion": 1e6}
F_UNIAX = Matrix3(0.9, 0, 0, 0, 1, 0, 0, 0, 1)
F_I = Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 1)


def total_frict_dissip():
    tot = 0.0
    for i in O.interactions:
        if i.isReal and i.phys.__class__.__name__ == "CohFrictPhys":
            tot += i.phys.frictDissip
    return tot


def max_rotation():
    mx = 0.0
    for b in O.bodies:
        q = b.state.ori
        # angle of quaternion from identity
        import math
        w = min(1.0, abs(q[3]))
        ang = 2.0 * math.acos(w)
        mx = max(mx, ang)
    return mx


def probe_trace(F_target, n_increments=20, steps_per_increment=80, damping=0.7):
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
            S, sig, F, J = homogenized_stress()
            pts.append((F[0, 0], S[0, 0]))
    finally:
        newton.damping = old
    return pts


info = make_rve_packing(u=U, seed=42, n_spheres=1000, verbose=False)
print("[diag] built. frictDissip@build=%.4e maxRot@build=%.4f" %
      (total_frict_dissip(), max_rotation()), flush=True)

load = probe_trace(F_UNIAX)
print("[diag] after load: frictDissip=%.4e maxRot=%.4f" %
      (total_frict_dissip(), max_rotation()), flush=True)
unload = probe_trace(F_I)
print("[diag] after unload: frictDissip=%.4e maxRot=%.4f" %
      (total_frict_dissip(), max_rotation()), flush=True)

print(" F11        S11_load      S11_unload")
for (f1, s1), (f2, s2) in zip(load, unload):
    print(" %.4f  %+.4e  %+.4e" % (f1, s1, s2))
