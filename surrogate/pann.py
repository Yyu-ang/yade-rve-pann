"""PANN surrogate — paper §2.5, §4.2.1.

Network: Psi(I, u) -> strain energy density (Eq. 27).
Stress reconstructed by autodiff (Eq. 6):  S = 2 dPsi/dC.
Loss on data tuples D_q = ((I_q, u_q), S_q) (Eq. 12):

    L = (1/Q) sum_q || S_NN(I_q, u_q) - S_RVE_q ||^2

Requirements (Eq. 13 needs the tangent C): network twice differentiable,
unbounded activations -> softplus hidden layers, linear output.
Paper architecture (Table 4): 5 -> 170 -> 55 -> 1.
"""
INVARIANT_DIM = 3  # I1, I2, I3 (isotropic)


class PANN:
    """Psi(I, u) with stress/tangent via autograd."""

    def __init__(self, u_dim, hidden=(170, 55)):
        raise NotImplementedError

    def energy(self, I, u):
        raise NotImplementedError

    def stress(self, I, u):
        """S = 2 dPsi/dC via autograd (Eq. 6)."""
        raise NotImplementedError

    def tangent(self, I, u):
        """C = 4 d2Psi/dCdC (Eq. 13) for FE incorporation."""
        raise NotImplementedError
