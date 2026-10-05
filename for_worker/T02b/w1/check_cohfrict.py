from yade.wrapper import CohFrictMat
import yade.wrapper as w
names = [n for n in dir(w) if 'CohFrict' in n]
print("CohFrict classes:", names)
m = CohFrictMat()
print("fragile default:", m.fragile)
print("normalCohesion default:", m.normalCohesion)
print("shearCohesion default:", m.shearCohesion)
print("frictionAngle default:", m.frictionAngle)
