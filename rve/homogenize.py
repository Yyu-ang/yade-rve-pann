"""Periodic homogenization: prescribe F, measure homogenized S.

Paper §2.4: periodic BCs (Eq. 10), Hill-Mandel condition (Eq. 9).
Macroscopic 2nd Piola-Kirchhoff stress from the volume-averaged Cauchy stress:

    S = J * F^-1 . sigma . F^-T      (Eq. 3)

with sigma from yade's getStress() (volume average over the periodic cell).
Invariants I(C), C = F^T F, feed the PANN (§2.5, Eq. 11).

YADE sign convention (verified in T01): compression negative, tension positive.
getStress() returns the volume-averaged Cauchy stress over the *current* cell.
Deformation gradient F is measured against the reference cell stored via
set_reference_hsize() (F = hSize * hSize0^-1).
"""

from yade.minieigenHP import Matrix3

# Reference cell shape (hSize at F = I). Set via set_reference_hsize().
_reference_hsize = None


def set_reference_hsize(hSize):
    """Store the reference periodic cell shape (the F = I state)."""
    global _reference_hsize
    _reference_hsize = Matrix3(hSize)


def get_reference_hsize():
    """Return the stored reference hSize (or None if unset)."""
    return _reference_hsize


def get_deformation_gradient():
    """F = hSize * hSize0^-1 from the periodic cell (paper §2.1, Eq. 2)."""
    from yade import O
    if _reference_hsize is None:
        raise RuntimeError("reference hSize not set; call set_reference_hsize() first")
    if not O.periodic:
        raise RuntimeError("O.periodic is not True")
    return O.cell.hSize * _reference_hsize.inverse()


def deformation_invariants(F):
    """Return (I1, I2, I3) of C = F^T F for a 3x3 deformation gradient.

    I1 = tr(C), I2 = 1/2[(tr C)^2 - tr(C^2)], I3 = det(C).
    F may be a Matrix3 or a nested 3x3 list.
    """
    if not isinstance(F, Matrix3):
        F = Matrix3(*[F[r][c] for r in range(3) for c in range(3)])
    C = F.transpose() * F
    trC = C[0, 0] + C[1, 1] + C[2, 2]
    C2 = C * C
    trC2 = C2[0, 0] + C2[1, 1] + C2[2, 2]
    I1 = trC
    I2 = 0.5 * (trC * trC - trC2)
    I3 = C.determinant()
    return (I1, I2, I3)


def cauchy_to_pk2(sigma, F):
    """Second Piola-Kirchhoff stress from Cauchy stress (paper Eq. 3).

        S = J * F^-1 . sigma . F^-T,   J = det(F)

    sigma, F are Matrix3 (or nested lists, converted).
    """
    if not isinstance(sigma, Matrix3):
        sigma = Matrix3(*[sigma[r][c] for r in range(3) for c in range(3)])
    if not isinstance(F, Matrix3):
        F = Matrix3(*[F[r][c] for r in range(3) for c in range(3)])
    J = F.determinant()
    Finv = F.inverse()
    return J * Finv * sigma * Finv.transpose()


def homogenized_stress():
    """Volume-averaged Cauchy stress -> 2nd Piola-Kirchhoff S via Eq. (3).

    Returns (S, sigma, F, J) as (Matrix3, Matrix3, Matrix3, float).
    sigma = utils.getStress() (Cauchy, current volume average).
    """
    from yade import O  # noqa: F401  (ensures yade context)
    from yade.utils import getStress
    sigma = getStress()
    F = get_deformation_gradient()
    J = F.determinant()
    S = cauchy_to_pk2(sigma, F)
    return (S, sigma, F, J)


def s_voigt(S):
    """Flatten symmetric Matrix3 to Voigt [S11, S22, S33, S23, S13, S12]."""
    if not isinstance(S, Matrix3):
        S = Matrix3(*[S[r][c] for r in range(3) for c in range(3)])
    return [S[0, 0], S[1, 1], S[2, 2], S[1, 2], S[0, 2], S[0, 1]]


def probe_F(F_target, n_increments=50, steps_per_increment=100, damping=0.5):
    """Drive the periodic cell to deformation gradient F_target quasi-statically.

    hSize is interpolated linearly from the reference to
    hSize_target = F_target * hSize0; the packing relaxes `steps_per_increment`
    steps (with NewtonIntegrator damping set to `damping`, restored afterwards)
    per increment.

    Returns (I1, I2, I3, S_voigt) at F_target. Requires a periodic packing in O
    and a stored reference hSize.
    """
    from yade import O
    if _reference_hsize is None:
        raise RuntimeError("reference hSize not set; call set_reference_hsize() first")
    if not isinstance(F_target, Matrix3):
        F_target = Matrix3(*[F_target[r][c] for r in range(3) for c in range(3)])
    # NewtonIntegrator damping handling
    newton = None
    for e in O.engines:
        if e.__class__.__name__ == "NewtonIntegrator":
            newton = e
            break
    old_damping = newton.damping if newton else None
    try:
        if newton:
            newton.damping = damping
        h0 = Matrix3(_reference_hsize)
        hT = F_target * h0
        h_prev = Matrix3(O.cell.hSize)
        for k in range(1, n_increments + 1):
            t = float(k) / n_increments
            h = h0 * (1.0 - t) + hT * t
            # affine carry of particles with the cell (avoids teleporting
            # across periodic boundaries when hSize is reset directly)
            F_incr = h * h_prev.inverse()
            for b in O.bodies:
                b.state.pos = F_incr * b.state.pos
            O.cell.hSize = h
            h_prev = Matrix3(h)
            O.run(steps_per_increment, True)
    finally:
        if newton and old_damping is not None:
            newton.damping = old_damping
    S, sigma, F, J = homogenized_stress()
    I1, I2, I3 = deformation_invariants(F)
    return (I1, I2, I3, s_voigt(S))
