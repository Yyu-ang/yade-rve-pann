"""Periodic homogenization: prescribe F, measure homogenized S.

Paper §2.4: periodic BCs (Eq. 10), Hill-Mandel condition (Eq. 9).
Macroscopic 2nd Piola-Kirchhoff stress from the volume-averaged Cauchy stress:

    S = J * F^-1 . sigma . F^-T      (Eq. 3)

with sigma from yade's getStress() (volume average over the periodic cell).
Invariants I(C), C = F^T F, feed the PANN (§2.5, Eq. 11).
"""


def deformation_invariants(F):
    """Return (I1, I2, I3) of C = F^T F for a 3x3 deformation gradient."""
    raise NotImplementedError


def homogenized_stress():
    """Volume-averaged Cauchy stress -> 2nd Piola-Kirchhoff S via Eq. (3)."""
    raise NotImplementedError


def probe_F(F_target, dt_scale=0.5):
    """Drive the periodic cell to deformation gradient F_target quasi-statically,
    return (I1, I2, I3, S_voigt)."""
    raise NotImplementedError
