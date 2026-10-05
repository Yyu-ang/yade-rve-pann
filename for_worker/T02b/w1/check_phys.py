from yade.wrapper import CohFrictPhys
p = CohFrictPhys()
names = [n for n in dir(p) if not n.startswith('_')]
print(names)
print("cohesionBroken:", p.cohesionBroken)
