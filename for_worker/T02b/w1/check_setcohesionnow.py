"""Check setCohesionNow semantics: enable cohesion on EXISTING contacts."""
from yade import O
from yade.minieigenHP import Vector3
from yade import utils
from yade.wrapper import (CohFrictMat, ForceResetter, InsertionSortCollider,
                          Bo1_Sphere_Aabb, InteractionLoop,
                          Ig2_Sphere_Sphere_ScGeom6D,
                          Ip2_CohFrictMat_CohFrictMat_CohFrictPhys,
                          Law2_ScGeom6D_CohFrictPhys_CohesionMoment,
                          NewtonIntegrator)

O.reset()
mat = CohFrictMat(young=1e7, poisson=0.3, frictionAngle=0.5, density=2600,
                  normalCohesion=1e6, shearCohesion=1e6, fragile=False)
O.materials.append(mat)
O.bodies.append([utils.sphere((0, 0, 0), 0.05, material=mat),
                 utils.sphere((0.095, 0, 0), 0.05, material=mat)])
ip2 = Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(setCohesionOnNewContacts=False)
O.engines = [ForceResetter(),
             InsertionSortCollider([Bo1_Sphere_Aabb()]),
             InteractionLoop([Ig2_Sphere_Sphere_ScGeom6D()], [ip2],
                             [Law2_ScGeom6D_CohFrictPhys_CohesionMoment()]),
             NewtonIntegrator(damping=0.9, gravity=(0, 0, 0))]
from yade.utils import PWaveTimeStep
O.dt = 0.5 * PWaveTimeStep()
O.run(5, True)
for i in O.interactions:
    if i.isReal:
        print("before: cohesionBroken =", bool(i.phys.cohesionBroken))
# now enable cohesion on existing contacts
ip2.setCohesionNow = True
O.run(5, True)
ip2.setCohesionNow = False
for i in O.interactions:
    if i.isReal:
        p = i.phys
        print("after: cohesionBroken =", bool(p.cohesionBroken),
              "normalAdhesion =", p.normalAdhesion)
print("CHECK DONE")
