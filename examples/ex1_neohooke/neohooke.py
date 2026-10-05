"""Modified Neo-Hookean law — paper Eq.(33), Example I reference constitutive law.

Source: Harazin et al., CMAME 452 (2026) 118726, Eq.(33), §5.1.
Formula transcribed by visual verification of the publisher PDF, p.11
(see docs/reproduction_plan_review_2026-10-05.md §1.1).

The paper defines, with κ = E/(3(1−2ν)) and η = E/(2(1+ν))::

    S = F⁻¹ · ( κ·ln[J]·F⁻ᵀ + η·( J^(−2/3)·F − tr(J^(−2/3)·C)/3 · F⁻ᵀ ) )   (33)

i.e. the bracket is the 1st Piola–Kirchhoff stress P = ∂Ψ/∂F for the
strain energy Ψ = κ/2·(ln J)² + η/2·(Ī₁ − 3), Ī₁ = tr(J^(−2/3)·C),
and S = F⁻¹·P is the 2nd Piola–Kirchhoff stress.

Units: E in MPa → S in MPa. F must satisfy det(F) > 0.
"""

import numpy as np


def material_params(E, nu):
    """Return (kappa, eta) with kappa = E/(3(1-2*nu)), eta = E/(2(1+nu))."""
    kappa = E / (3.0 * (1.0 - 2.0 * nu))
    eta = E / (2.0 * (1.0 + nu))
    return kappa, eta


def psi(F, E, nu):
    """Strain energy density Ψ(F) = κ/2·(lnJ)² + η/2·(Ī₁−3), Ī₁ = tr(J^(−2/3) C).

    Used for the cross-check S =?= 2·∂Ψ/∂C (paper Eq.(6)).
    """
    F = np.asarray(F, dtype=float).reshape(3, 3)
    J = float(np.linalg.det(F))
    if J <= 0.0:
        raise ValueError("det(F) must be positive, got %r" % J)
    kappa, eta = material_params(E, nu)
    C = F.T @ F
    I1bar = J ** (-2.0 / 3.0) * np.trace(C)
    return 0.5 * kappa * np.log(J) ** 2 + 0.5 * eta * (I1bar - 3.0)


def pk2_stress(F, E, nu):
    """2nd Piola–Kirchhoff stress S(F) per paper Eq.(33).

    Parameters
    ----------
    F : (3,3) array_like
        Deformation gradient, det(F) > 0.
    E : float
        Young's modulus in MPa.
    nu : float
        Poisson's ratio.

    Returns
    -------
    S : (3,3) ndarray
        Symmetric 2nd Piola–Kirchhoff stress in MPa.
    """
    F = np.asarray(F, dtype=float).reshape(3, 3)
    J = float(np.linalg.det(F))
    if J <= 0.0:
        raise ValueError("det(F) must be positive, got %r" % J)
    kappa, eta = material_params(E, nu)
    C = F.T @ F
    Finv = np.linalg.inv(F)
    FinvT = Finv.T
    Jm23 = J ** (-2.0 / 3.0)
    Cbar_tr = Jm23 * np.trace(C)
    P = kappa * np.log(J) * FinvT + eta * (Jm23 * F - (Cbar_tr / 3.0) * FinvT)
    S = Finv @ P
    return S
