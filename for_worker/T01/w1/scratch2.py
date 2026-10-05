"""Scratch 2: dense periodic packing; verify force/branch conventions."""
from yade import utils, pack
from yade.minieigenHP import Matrix3, Vector3
from yade.utils import PWaveTimeStep, unbalancedForce

O.periodic = True
O.cell.hSize = Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 1)
mat = FrictMat(young=1e7, poisson=0.3, frictionAngle=0.5, density=2600)
O.materials.append(mat)
sp = pack.SpherePack()
sp.makeCloud(minCorner=(0, 0, 0), maxCorner=(1, 1, 1), rMean=0.045, rRelFuzz=0.3,
             periodic=True, num=1200, seed=42)
print("packed:", len(sp))
O.engines = [
    ForceResetter(),
    InsertionSortCollider([Bo1_Sphere_Aabb()]),
    InteractionLoop([Ig2_Sphere_Sphere_ScGeom()],
                    [Ip2_FrictMat_FrictMat_FrictPhys()],
                    [Law2_ScGeom_FrictPhys_CundallStrack()]),
    NewtonIntegrator(damping=0.7, gravity=(0, 0, 0)),
]
sp.toSimulation()
O.dt = 0.5 * PWaveTimeStep()
print("dt:", O.dt)
# relax
for k in range(20):
    O.run(500, True)
    uf = unbalancedForce()
    if k % 5 == 0:
        print("relax step", k * 500, "unbalanced:", uf)
    if uf < 5e-3:
        break
nI = sum(1 for i in O.interactions if i.isReal)
print("real interactions:", nI)
s = utils.getStress()
print("getStress:\n", s)

print("== force convention ==")
ok = 0
for i in O.interactions:
    if i.isReal:
        fphys = i.phys.normalForce + i.phys.shearForce
        f2 = O.forces.f(i.id2)
        if (fphys - f2).norm() < 1e-9 * max(1.0, f2.norm()):
            ok += 1
        if ok == 1:
            print("  phys==forces.f(id2) OK, e.g. f =", fphys)
        if ok > 200:
            break
print("  matched:", ok)

print("== branch vector convention ==")
h = O.cell.hSize
V = O.cell.volume
sig = Matrix3.Zero
n = 0
for i in O.interactions:
    if not i.isReal:
        continue
    b1 = O.bodies[i.id1]
    b2 = O.bodies[i.id2]
    f = i.phys.normalForce + i.phys.shearForce
    cd = i.cellDist
    # candidate unwrappings
    p2a = b2.state.pos + h * Vector3(cd[0], cd[1], cd[2])
    p2b = b2.state.pos - h * Vector3(cd[0], cd[1], cd[2])
    d1 = (p2a - b1.state.pos).norm()
    d2 = (p2b - b1.state.pos).norm()
    p2 = p2a if d1 < d2 else p2b
    if n == 0:
        print("  cellDist:", tuple(cd), " d(+off)=%.4f d(-off)=%.4f -> use %s" % (d1, d2, "+off" if d1 < d2 else "-off"))
    l = p2 - b1.state.pos
    sig += Matrix3(f[0]*l[0], f[0]*l[1], f[0]*l[2],
                   f[1]*l[0], f[1]*l[1], f[1]*l[2],
                   f[2]*l[0], f[2]*l[1], f[2]*l[2])
    n += 1
sig = sig * (1.0 / V)
print("direct sigma:\n", sig)
print("getStress:\n", s)
diff = sig - s
print("max abs diff:", max(abs(diff[r, c]) for r in range(3) for c in range(3)))
print("SCRATCH2_DONE")
