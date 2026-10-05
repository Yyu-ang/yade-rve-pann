"""Scratch 4: dense packing w/ bisection unload; verify conventions + homogenize.py."""
import sys, os
sys.path.insert(0, "/home/hatch/workspace/yade-rve-pann/.worktrees/T01/w1")
from yade import utils, pack, O
from yade.minieigenHP import Matrix3, Vector3
from yade.utils import PWaveTimeStep, unbalancedForce
from rve.homogenize import (set_reference_hsize, get_deformation_gradient,
                            deformation_invariants, cauchy_to_pk2,
                            homogenized_stress, s_voigt)

O.periodic = True
O.cell.hSize = Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 1)
mat = FrictMat(young=1e7, poisson=0.3, frictionAngle=0.5, density=2600)
O.materials.append(mat)
sp = pack.SpherePack()
sp.makeCloud(minCorner=(0, 0, 0), maxCorner=(1, 1, 1), rMean=0.04, rRelFuzz=0.3,
             periodic=True, num=1000, seed=42)
print("placed:", len(sp), flush=True)
O.engines = [
    ForceResetter(),
    InsertionSortCollider([Bo1_Sphere_Aabb()]),
    InteractionLoop([Ig2_Sphere_Sphere_ScGeom()],
                    [Ip2_FrictMat_FrictMat_FrictPhys()],
                    [Law2_ScGeom_FrictPhys_CundallStrack()]),
    NewtonIntegrator(damping=0.85, gravity=(0, 0, 0)),
]
sp.toSimulation()
O.dt = 0.5 * PWaveTimeStep()

def mean_stress():
    s = utils.getStress()
    return (s[0, 0] + s[1, 1] + s[2, 2]) / 3.0

def n_contacts():
    return sum(1 for i in O.interactions if i.isReal)

# densify
for k in range(6):
    h = O.cell.hSize
    O.cell.hSize = Matrix3(h[0,0]*0.95, 0, 0, 0, h[1,1]*0.95, 0, 0, 0, h[2,2]*0.95)
    O.run(1500, True)
    if mean_stress() < -2e4:
        break
print("after densify: contacts=%d meanStress=%.3e" % (n_contacts(), mean_stress()), flush=True)

# bisection unload to near-zero stress
h_dense = Matrix3(O.cell.hSize)
lo, hi = 1.0, 1.06
# verify hi gives ~zero stress first
O.cell.hSize = h_dense * hi
O.run(2000, True)
print("hi=%.2f -> meanStress=%.3e contacts=%d" % (hi, mean_stress(), n_contacts()), flush=True)
for it in range(14):
    mid = 0.5 * (lo + hi)
    O.cell.hSize = h_dense * mid
    O.run(2000, True)
    m = mean_stress()
    if m < -20.0:
        lo = mid
    else:
        hi = mid
    if abs(m) < 20.0:
        break
print("bisection done: scale=%.5f meanStress=%.3e contacts=%d" % (mid, mean_stress(), n_contacts()), flush=True)
O.run(3000, True)
print("relaxed: meanStress=%.3e contacts=%d unbalanced=%.3e" % (mean_stress(), n_contacts(), unbalancedForce()), flush=True)

set_reference_hsize(O.cell.hSize)
F = get_deformation_gradient()
print("F at reference (should be I):\n", F, flush=True)

print("== f convention ==")
n_ok = n_tot = 0
for i in O.interactions:
    if not i.isReal:
        continue
    n_tot += 1
    fphys = i.phys.normalForce + i.phys.shearForce
    if (fphys - O.forces.f(i.id2)).norm() < 1e-9 * max(1.0, O.forces.f(i.id2).norm()):
        n_ok += 1
    if n_tot >= 300:
        break
print("phys == forces.f(id2): %d/%d" % (n_ok, n_tot), flush=True)

print("== direct sigma vs getStress ==")
h = O.cell.hSize
V = O.cell.volume
sig = Matrix3.Zero
for i in O.interactions:
    if not i.isReal:
        continue
    b1, b2 = O.bodies[i.id1], O.bodies[i.id2]
    f = i.phys.normalForce + i.phys.shearForce
    cd = i.cellDist
    p2a = b2.state.pos + h * Vector3(cd[0], cd[1], cd[2])
    p2b = b2.state.pos - h * Vector3(cd[0], cd[1], cd[2])
    p2 = p2a if (p2a - b1.state.pos).norm() < (p2b - b1.state.pos).norm() else p2b
    l = p2 - b1.state.pos
    sig += Matrix3(f[0]*l[0], f[0]*l[1], f[0]*l[2],
                   f[1]*l[0], f[1]*l[1], f[1]*l[2],
                   f[2]*l[0], f[2]*l[1], f[2]*l[2])
sig = sig * (1.0 / V)
s = utils.getStress()
d = sig - s
md = max(abs(d[r, c]) for r in range(3) for c in range(3))
ms = max(abs(s[r, c]) for r in range(3) for c in range(3))
print("max|direct-getStress| = %.3e, max|getStress| = %.3e" % (md, ms), flush=True)
print("getStress:\n", s, flush=True)

print("== homogenize.py ==")
S, sigma, F2, J = homogenized_stress()
print("S:\n", S, flush=True)
print("J:", J, flush=True)
I1, I2, I3 = deformation_invariants(F2)
print("invariants at I: %.6f %.6f %.6f (expect 3,3,1)" % (I1, I2, I3), flush=True)
print("S/E:", max(abs(S[r, c]) for r in range(3) for c in range(3)) / 1e7, flush=True)
print("SCRATCH4_DONE")
