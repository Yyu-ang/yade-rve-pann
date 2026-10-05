"""Scratch 3: dense periodic packing via cell-shrink densification + unload."""
from yade import utils, pack
from yade.minieigenHP import Matrix3, Vector3
from yade.utils import PWaveTimeStep, unbalancedForce

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

def stats(tag):
    nI = sum(1 for i in O.interactions if i.isReal)
    s = utils.getStress()
    mean_s = (s[0, 0] + s[1, 1] + s[2, 2]) / 3.0
    # solid fraction
    vol = sum((4.0/3.0)*3.14159265358979*b.shape.radius**3 for b in O.bodies)
    phi = vol / O.cell.volume
    print("%s: contacts=%d phi=%.3f meanStress=%.3e" % (tag, nI, phi, mean_s), flush=True)

def scale_cell(f):
    h = O.cell.hSize
    O.cell.hSize = Matrix3(h[0, 0]*f, 0, 0, 0, h[1, 1]*f, 0, 0, 0, h[2, 2]*f)

stats("initial")
# densify in steps
for k in range(6):
    scale_cell(0.95)
    O.run(1500, True)
    stats("densify %d" % k)
    s = utils.getStress()
    mean_s = (s[0, 0] + s[1, 1] + s[2, 2]) / 3.0
    if mean_s < -2e4:  # enough prestress
        break
# unload a bit to near-zero stress
for k in range(4):
    s = utils.getStress()
    mean_s = (s[0, 0] + s[1, 1] + s[2, 2]) / 3.0
    print("unload check %d: meanStress=%.3e" % (k, mean_s), flush=True)
    if abs(mean_s) < 2e3:
        break
    scale_cell(1.015)
    O.run(2000, True)
stats("final")
print("unbalanced:", unbalancedForce())
print("SCRATCH3_DONE")
