"""Self-test for the Eq.(33) modified Neo-Hookean implementation.

DOD checks (dispatch T03 §4):
  1. F = I  =>  S = 0                      (tol 1e-12)
  2. S symmetric: ||S - S^T|| / ||S|| < 1e-12
  3. Consistency: S =?= 2*dPsi/dC via central differences on C
     (20 random F, H_ij in [-0.2, 0.2]); max rel. err < 1e-6
  4. Uniaxial stretch F = diag(1.2, 1, 1): S11 > 0 and O(E*0.2)

Run:  python3 examples/ex1_neohooke/test_neohooke.py
Exit code 0  <=>  all checks pass.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from neohooke import pk2_stress, psi, material_params

TOL_ZERO = 1e-12
TOL_SYM = 1e-12
TOL_CONSISTENCY = 1e-6


def psi_of_C(C, E, nu):
    """Psi as a function of the (symmetric) right Cauchy-Green tensor C."""
    C = np.asarray(C, dtype=float).reshape(3, 3)
    detC = float(np.linalg.det(C))
    if detC <= 0.0:
        raise ValueError("det(C) must be positive")
    kappa, eta = material_params(E, nu)
    I1bar = detC ** (-1.0 / 3.0) * np.trace(C)
    return 0.5 * kappa * (0.5 * np.log(detC)) ** 2 + 0.5 * eta * (I1bar - 3.0)


def pk2_numerical(F, E, nu, h=1e-7):
    """S_num = 2*dPsi/dC via central differences on the 6 independent
    components of the symmetric tensor C.

    Perturbation basis E^(ij) (1 at (i,j) and (j,i)):
      dPsi/dh|_0 = G_ii            (i == j)
      dPsi/dh|_0 = 2*G_ij         (i != j),  G = dPsi/dC
    hence S_ii = 2*slope_ii,  S_ij = slope_ij (i != j).
    """
    C = np.asarray(F, dtype=float).reshape(3, 3)
    C = C.T @ C
    S = np.zeros((3, 3))
    for i in range(3):
        for j in range(i, 3):
            Eij = np.zeros((3, 3))
            Eij[i, j] = 1.0
            Eij[j, i] = 1.0
            slope = (psi_of_C(C + h * Eij, E, nu)
                     - psi_of_C(C - h * Eij, E, nu)) / (2.0 * h)
            if i == j:
                S[i, j] = 2.0 * slope
            else:
                S[i, j] = slope
                S[j, i] = slope
    return S


def check_identity_zero():
    S = pk2_stress(np.eye(3), 30000.0, 0.3)
    err = np.max(np.abs(S))
    ok = err < TOL_ZERO
    print("[1] F=I -> S=0: max|S_ij| = %.3e  %s" % (err, "PASS" if ok else "FAIL"))
    return ok


def check_symmetry(rng):
    worst = 0.0
    for _ in range(20):
        F = np.eye(3) + rng.uniform(-0.2, 0.2, size=(3, 3))
        assert np.linalg.det(F) > 0.0
        S = pk2_stress(F, 30000.0, 0.3)
        rel = np.linalg.norm(S - S.T) / np.linalg.norm(S)
        worst = max(worst, rel)
    ok = worst < TOL_SYM
    print("[2] symmetry: max ||S-S^T||/||S|| = %.3e  %s"
          % (worst, "PASS" if ok else "FAIL"))
    return ok


def check_consistency(rng):
    worst = 0.0
    for _ in range(20):
        F = np.eye(3) + rng.uniform(-0.2, 0.2, size=(3, 3))
        assert np.linalg.det(F) > 0.0
        E = float(rng.uniform(2.5e4, 3.5e4))   # paper Table 1 range
        nu = float(rng.uniform(0.21, 0.39))    # paper Table 1 range
        S_ref = pk2_stress(F, E, nu)
        S_num = pk2_numerical(F, E, nu)
        rel = np.linalg.norm(S_num - S_ref) / np.linalg.norm(S_ref)
        worst = max(worst, rel)
    ok = worst < TOL_CONSISTENCY
    print("[3] S =?= 2*dPsi/dC: max rel. err over 20 random F = %.3e  %s"
          % (worst, "PASS" if ok else "FAIL"))
    return ok


def check_uniaxial():
    E, nu = 30000.0, 0.3
    F = np.diag([1.2, 1.0, 1.0])
    S = pk2_stress(F, E, nu)
    ok_sign = S[0, 0] > 0.0
    ok_order = (E * 0.02) < S[0, 0] < (E * 2.0)  # O(E*0.2), decade-wide band
    ok = ok_sign and ok_order
    print("[4] uniaxial F=diag(1.2,1,1): S11 = %.1f MPa (E*0.2 = %.0f), "
          "S11>0: %s, order ok: %s  %s"
          % (S[0, 0], E * 0.2, ok_sign, ok_order, "PASS" if ok else "FAIL"))
    return ok


def main():
    rng = np.random.default_rng(42)
    results = [
        check_identity_zero(),
        check_symmetry(rng),
        check_consistency(rng),
        check_uniaxial(),
    ]
    if all(results):
        print("ALL CHECKS PASSED")
        return 0
    print("SOME CHECKS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
