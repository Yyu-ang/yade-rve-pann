"""3D constitutive interface for the T09 macro pipeline.

Reference law: paper Eq.(33) Neo-Hookean in full 3D form, via
``macro.plane_stress.pk2_stress_vec`` (vectorized: F (M,3,3) -> S (M,3,3)).

PANN law: ``PANN.stress(C, u)`` with C = F^T F (M,3,3), u = [E_MPa, nu]
(M,2) -- the PANN is invariant-based, hence dimension-independent, exactly
as in training (``surrogate/train_pann.py``).

Material tangent A_ijkl = dP_ij/dF_kl (P = F S, first Piola-Kirchhoff)
is obtained by forward finite differences on the batched stress function:
one stacked call per Newton iteration for both laws, so ref and PANN share
a single code path. The FD tangent is verified against central differences
in ``validate_3d.py`` (V0).

Caveats (analogue framing, see 3d/README.md):
- full-integration hex8 with nu -> 0.39 can show mild volumetric locking;
- the PANN was trained on (near) plane-stress states; 3D states with
  significant out-of-plane shear are mild extrapolation.
"""

import numpy as np


def ref_S(F, E, nu):
    """Paper Eq.(33), 3D: F (M,3,3) -> S (M,3,3) [MPa]."""
    from macro.plane_stress import pk2_stress_vec
    return pk2_stress_vec(np.asarray(F, dtype=float), E, nu)


def make_pann_S(model):
    """Return S(F, E, nu) closing over a loaded PANN (read-only)."""
    def S_fn(F, E, nu):
        F = np.asarray(F, dtype=float)
        M = F.shape[0]
        C = np.einsum("nij,nik->njk", F, F)
        E_a = np.broadcast_to(np.asarray(E, dtype=float), (M,))
        nu_a = np.broadcast_to(np.asarray(nu, dtype=float), (M,))
        if np.any(nu_a >= 0.5) or np.any(nu_a <= 0.0):
            raise ValueError("nu out of (0, 0.5)")
        u = np.column_stack([E_a, nu_a])
        return model.stress(C, u)
    return S_fn


def first_piola_3d(F, S):
    """P = F S, (M,3,3)."""
    return np.einsum("nij,njk->nik", F, S)


def cauchy_stress_3d(F, S):
    """sigma = (1/J) P F^T, (M,3,3) [MPa]."""
    P = first_piola_3d(F, S)
    J = np.linalg.det(F)
    return np.einsum("nij,nkj->nik", P, F) / J[:, None, None]


def fd_tangent(S_fn, F, E, nu, h_rel=1e-7):
    """A[m,i,j,k,l] = dP_ij/dF_kl via forward FD, P = F S(F).

    Perturbations are stacked into a single batched S_fn call
    ((9*M,3,3) input) so the PANN path costs one batched autograd call.
    Returns A (M,9,9) with Voigt-ish ordering r = 3*a+b.
    """
    F = np.asarray(F, dtype=float)
    M = F.shape[0]
    E_a = np.broadcast_to(np.asarray(E, dtype=float), (M,))
    nu_a = np.broadcast_to(np.asarray(nu, dtype=float), (M,))
    S0 = S_fn(F, E_a, nu_a)
    P0 = first_piola_3d(F, S0)                     # (M,3,3)
    h = h_rel * np.maximum(1.0, np.abs(F))        # (M,3,3)
    F_pert = np.zeros((9, M, 3, 3))
    for q in range(9):
        k, l = divmod(q, 3)
        dF = np.zeros((M, 3, 3))
        dF[:, k, l] = h[:, k, l]
        F_pert[q] = F + dF
    S_pert = S_fn(F_pert.reshape(9 * M, 3, 3),
                  np.tile(E_a, 9), np.tile(nu_a, 9)).reshape(9, M, 3, 3)
    P_pert = np.einsum("qmij,qmjk->qmik", F_pert, S_pert)   # (9,M,3,3)
    # h is (M,3,3); need hq[q,m] = h[m,k,l] with q = 3*k+l
    hq = h.transpose(1, 2, 0).reshape(9, M)
    dP = (P_pert - P0[None]) / hq[:, :, None, None]
    # dP[q, m, i, j], q = 3*k+l  ->  A[m, 3*i+j, 3*k+l]
    A = np.empty((M, 9, 9))
    for q in range(9):
        A[:, :, q] = dP[q].reshape(M, 9)
    return A
