"""Plane-stress condensation of the paper's Eq.(33) Neo-Hookean law.

Given an in-plane deformation gradient F_2d (n,2,2), solve the scalar
lambda = f33 at every Gauss point such that S33(F) = 0 with ::

    F = [[F11, F12, 0],
         [F21, F22, 0],
         [ 0 ,  0 , lam]]

fully vectorized over the n points. The 3D stress kernel below is an exact
vectorized transcription of paper Eq.(33); it is cross-checked against the
T03-accepted scalar ``pk2_stress`` in the self-test.

Condensed tangent (consistent, for the global Newton):
    C2_abcd = C_abcd - C_ab33 * C_33cd / C_3333,   a,b,c,d in {0,1}
with C = dS/dF the finite-difference 3D tangent at the converged state.

E, nu may be scalars or (n,) arrays (per-Gauss-point fields; interface
reserved for T07 random fields).
"""

import numpy as np

_FD_H = 1e-7


def _as_arr(x, n, name):
    x = np.asarray(x, dtype=float)
    if x.ndim == 0:
        return np.full(n, x)
    if x.shape == (n,):
        return x
    raise ValueError(f"{name} must be scalar or (n,), got {x.shape}")


def pk2_stress_vec(F, E, nu):
    """Vectorized paper Eq.(33): F (n,3,3) -> S (n,3,3), S in MPa for E in MPa."""
    F = np.asarray(F, dtype=float)
    n = F.shape[0]
    E = _as_arr(E, n, "E")
    nu = _as_arr(nu, n, "nu")
    J = np.linalg.det(F)
    if np.any(J <= 0.0):
        raise ValueError("det(F) must be positive")
    kappa = E / (3.0 * (1.0 - 2.0 * nu))
    eta = E / (2.0 * (1.0 + nu))
    C = np.matmul(F.transpose(0, 2, 1), F)
    Finv = np.linalg.inv(F)
    FinvT = Finv.transpose(0, 2, 1)
    Jm23 = J ** (-2.0 / 3.0)
    trC = np.trace(C, axis1=1, axis2=2)
    Cbar_tr = Jm23 * trC
    P = (kappa * np.log(J))[:, None, None] * FinvT \
        + eta[:, None, None] * (Jm23[:, None, None] * F
                               - (Cbar_tr / 3.0)[:, None, None] * FinvT)
    return np.matmul(Finv, P)


def _S33_of_lam(lam, A, E, nu, kappa, eta):
    """S33 for block-diagonal F with out-of-plane stretch lam.

    A   : (n,2,2) in-plane deformation gradient
    lam : (n,) out-of-plane stretch
    """
    J2 = A[:, 0, 0] * A[:, 1, 1] - A[:, 0, 1] * A[:, 1, 0]
    J = lam * J2
    trA = (A ** 2).sum(axis=(1, 2))          # tr(A^T A)
    Jm23 = J ** (-2.0 / 3.0)
    # S33 = k lnJ/lam^2 + eta*J^{-2/3}*(1 - (trA+lam^2)/(3 lam^2))
    return kappa * np.log(J) / lam ** 2 \
        + eta * Jm23 * (1.0 - (trA + lam ** 2) / (3.0 * lam ** 2))


def condense(F2, E, nu, lam0=None, tol=1e-11, maxit=40):
    """Plane-stress condensation, vectorized over Gauss points.

    Parameters
    ----------
    F2 : (n,2,2) in-plane deformation gradient
    E, nu : scalar or (n,) Young's modulus [MPa], Poisson's ratio

    Returns
    -------
    S2  : (n,2,2) condensed 2nd Piola-Kirchhoff stress [MPa]
    C2  : (n,2,2,2,2) condensed tangent dS2/dF2 [MPa]
    lam : (n,) converged out-of-plane stretch
    """
    F2 = np.asarray(F2, dtype=float)
    n = F2.shape[0]
    E = _as_arr(E, n, "E")
    nu = _as_arr(nu, n, "nu")
    kappa = E / (3.0 * (1.0 - 2.0 * nu))
    eta = E / (2.0 * (1.0 + nu))

    lam = np.ones(n) if lam0 is None else np.asarray(lam0, dtype=float).copy()
    scale = np.maximum(E, 1.0)
    for _ in range(maxit):
        g = _S33_of_lam(lam, F2, E, nu, kappa, eta)
        if np.max(np.abs(g) / scale) < tol:
            break
        h = 1e-8 * np.maximum(1.0, np.abs(lam))
        gp = (_S33_of_lam(lam + h, F2, E, nu, kappa, eta)
              - _S33_of_lam(lam - h, F2, E, nu, kappa, eta)) / (2.0 * h)
        lam = lam - g / gp
    else:
        raise RuntimeError("plane-stress scalar Newton did not converge")
    g = _S33_of_lam(lam, F2, E, nu, kappa, eta)
    if np.max(np.abs(g) / scale) >= 1e-8:
        raise RuntimeError("plane-stress S33 residual too large: %g"
                           % np.max(np.abs(g) / scale))

    # full 3D state at the converged lambda
    F3 = np.zeros((n, 3, 3))
    F3[:, :2, :2] = F2
    F3[:, 2, 2] = lam
    S3 = pk2_stress_vec(F3, E, nu)
    S2 = S3[:, :2, :2].copy()

    # 3D finite-difference tangent at converged state (central differences)
    # needed: C_abcd (a,b,c,d in {0,1}), C_ab33, C_33cd, C_3333
    dirs = ([(a, b, c, d) for a in (0, 1) for b in (0, 1)
             for c in (0, 1) for d in (0, 1)]
            + [(a, b, 2, 2) for a in (0, 1) for b in (0, 1)]
            + [(2, 2, c, d) for c in (0, 1) for d in (0, 1)]
            + [(2, 2, 2, 2)])
    C = {}
    for (a, b, c, d) in dirs:
        D = np.zeros((n, 3, 3))
        hh = _FD_H * np.maximum(1.0, np.abs(F3[:, c, d]))
        D[:, c, d] = hh
        Sp = pk2_stress_vec(F3 + D, E, nu)
        Sm = pk2_stress_vec(F3 - D, E, nu)
        C[(a, b, c, d)] = (Sp[:, a, b] - Sm[:, a, b]) / (2.0 * hh)

    C2 = np.zeros((n, 2, 2, 2, 2))
    C3333 = C[(2, 2, 2, 2)]
    for a in (0, 1):
        for b in (0, 1):
            Cab33 = C[(a, b, 2, 2)]
            for c in (0, 1):
                for d in (0, 1):
                    C2[:, a, b, c, d] = (C[(a, b, c, d)]
                                         - Cab33 * C[(2, 2, c, d)] / C3333)
    return S2, C2, lam


def cauchy_stress(F2, lam, E, nu):
    """Cauchy stress (n,3,3) [MPa] at the plane-stress state.

    sigma = (1/J) F S F^T with the condensed 3D F and S (S33 = 0).
    """
    F2 = np.asarray(F2, dtype=float)
    n = F2.shape[0]
    E = _as_arr(E, n, "E")
    nu = _as_arr(nu, n, "nu")
    F3 = np.zeros((n, 3, 3))
    F3[:, :2, :2] = F2
    F3[:, 2, 2] = lam
    S3 = pk2_stress_vec(F3, E, nu)
    J = lam * (F2[:, 0, 0] * F2[:, 1, 1] - F2[:, 0, 1] * F2[:, 1, 0])
    return np.matmul(F3, np.matmul(S3, F3.transpose(0, 2, 1))) / J[:, None, None]


def first_piola_2d(F2, S2):
    """In-plane 1st Piola-Kirchhoff stress P_2d = F_2d @ S_2d, (n,2,2)."""
    return np.matmul(F2, S2)


def tangent_P(F2, S2, C2):
    """dP_ab/dF_cd for the in-plane PK1: D_abcd = d_ac S_db + F_am C2_mbcd.

    Returns D with shape (n,2,2,2,2).
    """
    n = F2.shape[0]
    D = np.zeros((n, 2, 2, 2, 2))
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                for d in (0, 1):
                    D[:, a, b, c, d] = ((a == c) * S2[:, d, b]
                                        + np.einsum("nm,nm->n",
                                                    F2[:, a, :], C2[:, :, b, c, d]))
    return D
