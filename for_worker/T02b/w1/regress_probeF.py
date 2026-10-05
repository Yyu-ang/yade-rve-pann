"""Regression for the probe_F interpolation fix (T02b DOD-1).

Builds a small packing, probes F=I -> F=diag(0.9,1,1) -> F=I with
rve.homogenize.probe_F, recording the cell hSize after every increment.
The buggy version interpolated from the REFERENCE hSize, teleporting the
cell on the first increment of the unload stage; the fix interpolates from
the CURRENT hSize, so the path is continuous.

Pass criterion: max single-increment cell jump <= 1.5x the mean increment
size on the unload leg (smooth linear interpolation).
"""
import sys, os
_WTROOT = "/home/hatch/workspace/yade-rve-pann/.worktrees/T02b/w1"
if _WTROOT not in sys.path:
    sys.path.insert(0, _WTROOT)

from yade import O
from yade.minieigenHP import Matrix3
from rve.generate import make_rve_packing
from rve import homogenize as H

U = {"vf": 0.2, "rMean": 0.05, "rRelFuzz": 0.3, "E_soft": 1e7, "E_stiff": 5e7}
F_UNIAX = Matrix3(0.9, 0, 0, 0, 1, 0, 0, 0, 1)
F_I = Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 1)

make_rve_packing(u=U, seed=7, n_spheres=400, verbose=False)


def trace_probe(F_target, n_increments):
    """probe_F but recording hSize after every increment."""
    from yade import O as _O
    h0 = Matrix3(H.get_reference_hsize())
    hT = F_target * h0
    h_start = Matrix3(_O.cell.hSize)
    trace = [Matrix3(_O.cell.hSize)]
    # replicate probe_F stepping exactly (import the fixed function logic)
    import rve.homogenize as _H
    newton = None
    for e in _O.engines:
        if e.__class__.__name__ == "NewtonIntegrator":
            newton = e
            break
    old = newton.damping if newton else None
    try:
        if newton:
            newton.damping = 0.7
        h_prev = Matrix3(h_start)
        for k in range(1, n_increments + 1):
            t = float(k) / n_increments
            h = h_start * (1.0 - t) + hT * t
            F_incr = h * h_prev.inverse()
            for b in _O.bodies:
                b.state.pos = F_incr * b.state.pos
            _O.cell.hSize = h
            h_prev = Matrix3(h)
            _O.run(60, True)
            trace.append(Matrix3(_O.cell.hSize))
    finally:
        if newton and old is not None:
            newton.damping = old
    return trace


# stage 1: load (from reference) using the REAL probe_F
H.probe_F(F_UNIAX, n_increments=10, steps_per_increment=60, damping=0.7)
h_loaded = Matrix3(O.cell.hSize)
# stage 2: unload back to F=I using the REAL probe_F; trace cell motion
h0 = Matrix3(H.get_reference_hsize())
import types
trace = []
orig_run = O.run
def counting_run(n, wait):
    trace.append(Matrix3(O.cell.hSize))
    return orig_run(n, wait)
O.run = counting_run
try:
    H.probe_F(F_I, n_increments=10, steps_per_increment=60, damping=0.7)
finally:
    O.run = orig_run

# trace[k] = hSize BEFORE increment k+1 was applied... actually recorded
# before each O.run; approximate jump analysis on consecutive records:
jumps = []
for a, b in zip(trace, trace[1:]):
    jumps.append(max(abs((b - a)[r, c]) for r in range(3) for c in range(3)))
mean_jump = sum(jumps) / len(jumps)
max_jump = max(jumps)
print("[regress] unload leg: n_steps=%d mean_jump=%.4e max_jump=%.4e ratio=%.2f"
      % (len(jumps), mean_jump, max_jump, max_jump / mean_jump))
ratio = max_jump / mean_jump
assert ratio <= 1.5, "TELEPORT DETECTED: max/mean increment jump = %.2f" % ratio
# and the final cell must be back at the reference
herr = max(abs((Matrix3(O.cell.hSize) - h0)[r, c]) for r in range(3) for c in range(3))
print("[regress] final |h-h0|_max = %.4e (expect ~0)" % herr)
assert herr < 1e-9
print("PROBE_F REGRESSION PASSED")
