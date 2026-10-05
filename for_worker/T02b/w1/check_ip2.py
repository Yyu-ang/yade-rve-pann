from yade.wrapper import Ip2_CohFrictMat_CohFrictMat_CohFrictPhys
f = Ip2_CohFrictMat_CohFrictMat_CohFrictPhys()
print("setCohesionOnNewContacts =", f.setCohesionOnNewContacts)
print("setCohesionNow =", f.setCohesionNow)
print("normalCohesion =", f.normalCohesion, "shearCohesion =", f.shearCohesion)
