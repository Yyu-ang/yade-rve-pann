import sys
sys.path.insert(0, "/home/hatch/workspace/yade-rve-pann/.worktrees/T05/w1")
import numpy as np
from scipy.optimize import differential_evolution
from uq.material_uq import (load_model, pann_s11_batch,
                            E_LO, E_HI, NU_LO, NU_HI)

model = load_model()


def neg_s11(xn):
    E = E_LO + xn[0] * (E_HI - E_LO)
    nu = NU_LO + xn[1] * (NU_HI - NU_LO)
    v = pann_s11_batch(model, np.array([E]), np.array([nu]))
    return -float(v[0])


r = differential_evolution(neg_s11, [(0, 1), (0, 1)], seed=0,
                           tol=1e-9, maxiter=200)
Eo = E_LO + r.x[0] * (E_HI - E_LO)
nuo = NU_LO + r.x[1] * (NU_HI - NU_LO)
print("PANN global max: %.4f at E=%.1f nu=%.4f" % (-r.fun, Eo, nuo))
