"""Scratch: verify YADE API details needed for T01."""
import sys
print("== numpy ==")
try:
    import numpy as np
    print("numpy", np.__version__)
except Exception as e:
    print("NO NUMPY:", e)

from yade import utils, pack
from yade.minieigenHP import Matrix3, Vector3
print("== getStress ==")
print("has getStress:", hasattr(utils, 'getStress'))
import inspect
try:
    print(inspect.signature(utils.getStress))
except Exception as e:
    print("sig err", e)

print("== periodic cell basics ==")
O.periodic = True
O.cell.hSize = Matrix3(2, 0, 0, 0, 3, 0, 0, 0, 4)
print("hSize diag:", O.cell.hSize[0, 0], O.cell.hSize[1, 1], O.cell.hSize[2, 2])
print("volume:", O.cell.volume)
try:
    print("trsf:", O.cell.trsf)
except Exception as e:
    print("trsf err:", e)

print("== tiny periodic packing ==")
mat = FrictMat(young=1e7, poisson=0.3, frictionAngle=0.5, density=2600)
O.materials.append(mat)
sp = pack.SpherePack()
sp.makeCloud(minCorner=(0, 0, 0), maxCorner=(2, 3, 4), rMean=0.15, rRelFuzz=0.2,
             periodic=True, num=60, seed=1)
print("packed:", len(sp))
O.engines = [
    ForceResetter(),
    InsertionSortCollider([Bo1_Sphere_Aabb()]),
    InteractionLoop([Ig2_Sphere_Sphere_ScGeom()],
                    [Ip2_FrictMat_FrictMat_FrictPhys()],
                    [Law2_ScGeom_FrictPhys_CundallStrack()]),
    NewtonIntegrator(damping=0.5, gravity=(0, 0, 0)),
]
from yade.utils import PWaveTimeStep
O.dt = 0.5 * PWaveTimeStep()
sp.toSimulation()
O.run(200, True)
print("bodies:", len(O.bodies))
nI = sum(1 for i in O.interactions if i.isReal)
print("real interactions:", nI)
s = utils.getStress()
print("getStress type:", type(s))
print("getStress:\n", s)

print("== interaction conventions ==")
for i in O.interactions:
    if i.isReal:
        b1 = O.bodies[i.id1]
        b2 = O.bodies[i.id2]
        fphys = i.phys.normalForce + i.phys.shearForce
        f2 = O.forces.f(i.id2)
        print("id1,id2:", i.id1, i.id2)
        print("  phys force :", fphys)
        print("  O.forces.f(id2):", f2)
        print("  match:", (fphys - f2).norm() < 1e-9 * max(1.0, f2.norm()))
        print("  cellDist:", tuple(i.cellDist))
        # unwrapping test
        h = O.cell.hSize
        off = h * Vector3(i.cellDist[0], i.cellDist[1], i.cellDist[2])
        d1 = (b2.state.pos + off - b1.state.pos).norm()
        d2 = (b2.state.pos - off - b1.state.pos).norm()
        print("  dist with +off: %.4f, with -off: %.4f" % (d1, d2))
        print("  contactPoint:", i.geom.contactPoint)
        break

print("== energy tracking ==")
O.trackEnergy = True
O.run(10, True)
print("energy keys:", sorted(O.energy.keys()))
print("SCRATCH_DONE")
