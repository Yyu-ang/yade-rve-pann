"""Probe CohFrictPhys breakage semantics: two spheres pressed together."""
from yade import O
from yade.minieigenHP import Vector3
from yade.wrapper import (CohFrictMat, ForceResetter, InsertionSortCollider,
                          Bo1_Sphere_Aabb, InteractionLoop,
                          Ig2_Sphere_Sphere_ScGeom6D,
                          Ip2_CohFrictMat_CohFrictMat_CohFrictPhys,
                          Law2_ScGeom6D_CohFrictPhys_CohesionMoment,
                          NewtonIntegrator)

O.reset()
mat = CohFrictMat(young=1e7, poisson=0.3, frictionAngle=0.5, density=2600,
                  normalCohesion=1e6, shearCohesion=1e6, fragile=False)
print("mat.normalCohesion =", mat.normalCohesion)
O.materials.append(mat)
from yade import utils
s1 = utils.sphere((0, 0, 0), 0.05, material=mat)
s2 = utils.sphere((0.095, 0, 0), 0.05, material=mat)  # overlap 0.005
O.bodies.append([s1, s2])
O.engines = [ForceResetter(),
             InsertionSortCollider([Bo1_Sphere_Aabb()]),
             InteractionLoop([Ig2_Sphere_Sphere_ScGeom6D()],
                             [Ip2_CohFrictMat_CohFrictMat_CohFrictPhys(
                                 setCohesionOnNewContacts=True)],
                             [Law2_ScGeom6D_CohFrictPhys_CohesionMoment()]),
             NewtonIntegrator(damping=0.9, gravity=(0, 0, 0))]
from yade.utils import PWaveTimeStep
O.dt = 0.5 * PWaveTimeStep()
O.run(3, True)
print("n_interactions =", len([i for i in O.interactions]))
for i in O.interactions:
    p = i.phys
    print("isReal =", i.isReal,
          "| cohesionBroken =", p.cohesionBroken,
          "| initCohesion =", p.initCohesion,
          "| normalAdhesion =", p.normalAdhesion,
          "| shearAdhesion =", p.shearAdhesion,
          "| Fn =", p.normalForce,
          "| Fs =", p.shearForce)
    print("geom type:", i.geom.__class__.__name__)
