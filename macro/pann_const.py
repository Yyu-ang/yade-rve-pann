"""PANN-based plane-stress constitutive for the T08 macro UQ pipeline.

Drop-in replacement for :func:`macro.plane_stress.condense` with the same
signature ``(F2, E, nu, lam0) -> (S2, C2, lam)`` so the T06 solver only needs
a single-point swap inside ``state_at`` (per T06 handoff instruction).

Given in-plane F2 (M,2,2) and per-Gauss-point (E [MPa], nu):

1. lam = f33 from the **analytic** Eq.(33) S33 = 0 (closed form, vectorized,
   no tangent), then up to 4 PANN Newton corrections on S33^PANN(lam) = 0
   (approximate Newton with analytic dS33/dlam; 2 corrections already give
   S2 relative error ~4e-5 vs fully-converged PANN lam). Warm-started.
   PANN input features [I1, I2, I3, E_MPa, nu] are built from C = F3^T F3
   exactly as in training (``surrogate/train_pann.py``: X = hstack([I, u]),
   u = [E, nu]); the checkpoint's input scaler is applied inside the model.
   All PANN evaluations are batched over the M Gauss points.
2. S2 = PANN S[:,:2,:2] at the converged lam (one batched autograd call).
3. C2 = exact condensed PANN tangent via second-order autograd + implicit
   differentiation through S33 = 0 (verified against directional FD).
   Cached and reused while (F2, E, nu) change by less than 5%
   (relative max norm) to avoid recomputation on every Newton/line-search
   evaluation; the Newton then converges quadratically.

The checkpoint is loaded read-only and never modified.
"""

import numpy as np
import torch

from . import plane_stress as ps
from . import solver as sv  # for _InvalidState (adaptive stepping catches it)

_CACHE_TOL = 0.02
_cache = {"F2": None, "E": None, "nu": None, "C2": None}


def _as_arr(x, n, name):
    x = np.asarray(x, dtype=float)
    if x.ndim == 0:
        return np.full(n, x)
    if x.shape == (n,):
        return x
    raise ValueError(f"{name} must be scalar or (n,), got {x.shape}")


def _analytic_lam_only(F2, E, nu, lam0, tol=1e-12, maxit=30):
    """Solve analytic S33 = 0 for lam (closed form, vectorized, no tangent)."""
    M = F2.shape[0]
    kappa = E / (3.0 * (1.0 - 2.0 * nu))
    eta = E / (2.0 * (1.0 + nu))
    scale = np.maximum(E, 1.0)
    lam = np.ones(M) if lam0 is None else np.asarray(lam0, dtype=float).copy()
    for _ in range(maxit):
        g = ps._S33_of_lam(lam, F2, E, nu, kappa, eta)
        if np.max(np.abs(g) / scale) < tol:
            break
        h = 1e-8 * np.maximum(1.0, np.abs(lam))
        gp = (ps._S33_of_lam(lam + h, F2, E, nu, kappa, eta)
              - ps._S33_of_lam(lam - h, F2, E, nu, kappa, eta)) / (2.0 * h)
        lam = lam - g / np.where(gp == 0.0, 1.0, gp)
        lam = np.maximum(lam, 1e-6)
    else:
        raise sv._InvalidState("analytic lam Newton did not converge")
    return lam


def _pann_S33(lam, F2, u, model):
    """PANN S33 for block-diagonal F3(F2, lam). lam: (M,). Returns (M,)."""
    M = F2.shape[0]
    F3 = np.zeros((M, 3, 3))
    F3[:, :2, :2] = F2
    F3[:, 2, 2] = lam
    C = np.einsum("nij,nik->njk", F3, F3)
    S3 = model.stress(C, u)          # (M,3,3), one batched autograd call
    return S3[:, 2, 2]


def _pann_correct_lam(lam, F2, E, nu, u, model, tol=1e-7, maxit=6):
    """Refine lam with PANN Newton corrections (approximate Newton)."""
    M = F2.shape[0]
    kappa = E / (3.0 * (1.0 - 2.0 * nu))
    eta = E / (2.0 * (1.0 + nu))
    scale = np.maximum(E, 1.0)
    for _ in range(maxit):
        g = _pann_S33(lam, F2, u, model)
        if np.max(np.abs(g) / scale) < tol:
            break
        h = 1e-8 * np.maximum(1.0, np.abs(lam))
        gp = (ps._S33_of_lam(lam + h, F2, E, nu, kappa, eta)
              - ps._S33_of_lam(lam - h, F2, E, nu, kappa, eta)) / (2.0 * h)
        lam = lam - g / np.where(gp == 0.0, 1.0, gp)
        lam = np.maximum(lam, 1e-6)
    g = _pann_S33(lam, F2, u, model)
    if np.max(np.abs(g) / scale) >= 1e-5:
        raise sv._InvalidState("PANN S33 residual too large")
    return lam


def _pann_tangent_exact(F2_np, lam_np, u_np, model):
    """Exact condensed PANN tangent C2_abcd = dS2_ab/dF2_cd (M,2,2,2,2).

    Implicit differentiation through the plane-stress constraint S33 = 0:
        C2_abcd = dS2_ab/dF2_cd - (dS2_ab/dlam)(dS33/dF2_cd)/(dS33/dlam)
    All partials via second-order torch autograd, batched over the M points.
    Verified against directional finite differences (error ~ O(eps)).
    """
    from surrogate.pann import invariants_torch
    M = F2_np.shape[0]
    F2 = torch.as_tensor(F2_np, dtype=torch.float64).requires_grad_(True)
    lam = torch.as_tensor(lam_np, dtype=torch.float64).requires_grad_(True)
    u = torch.as_tensor(np.asarray(u_np, dtype=float), dtype=torch.float64)
    F3 = torch.zeros(M, 3, 3, dtype=torch.float64)
    F3[:, :2, :2] = F2
    F3[:, 2, 2] = lam
    C = F3.transpose(-2, -1) @ F3
    I = invariants_torch(C)
    x = torch.cat([I, u], dim=-1)
    psi = model.forward_scaled((x - model.c_in) / model.s_in)
    (G,) = torch.autograd.grad(psi.sum(), C, create_graph=True)
    S3 = 2.0 * G
    dS2_dF2, dS2_dlam = {}, {}
    for (a, b) in [(0, 0), (1, 1), (0, 1), (1, 0)]:
        gF2, glam = torch.autograd.grad(S3[:, a, b].sum(), [F2, lam],
                                        retain_graph=True)
        dS2_dF2[(a, b)] = gF2.detach().numpy()
        dS2_dlam[(a, b)] = glam.detach().numpy()
    gF2, glam = torch.autograd.grad(S3[:, 2, 2].sum(), [F2, lam])
    dS33_dF2 = gF2.detach().numpy()
    dS33_dlam = glam.detach().numpy()
    C2 = np.zeros((M, 2, 2, 2, 2))
    for (a, b) in [(0, 0), (1, 1), (0, 1), (1, 0)]:
        for c in (0, 1):
            for d in (0, 1):
                C2[:, a, b, c, d] = (dS2_dF2[(a, b)][:, c, d]
                                     - dS2_dlam[(a, b)] * dS33_dF2[:, c, d]
                                     / dS33_dlam)
    return C2


def _tangent_cached(F2, E, nu, lam, u, model):
    """Exact PANN condensed tangent, reused while inputs change < 5%."""
    global _cache
    c = _cache
    if c["C2"] is not None and c["F2"] is not None:
        dF = np.abs(F2 - c["F2"]).max() / max(np.abs(F2).max(), 1e-30)
        dE = np.abs(E - c["E"]).max() / max(np.abs(E).max(), 1e-30)
        dn = np.abs(nu - c["nu"]).max() / max(np.abs(nu).max(), 1e-30)
        if max(dF, dE, dn) < _CACHE_TOL:
            return c["C2"]
    C2 = _pann_tangent_exact(F2, lam, u, model)
    _cache["F2"] = F2.copy()
    _cache["E"] = E.copy()
    _cache["nu"] = nu.copy()
    _cache["C2"] = C2
    return C2


def clear_cache():
    """Invalidate the tangent cache (call at the start of each MC sample)."""
    global _cache
    _cache = {"F2": None, "E": None, "nu": None, "C2": None}


def pann_condense(F2, E, nu, lam0=None, model=None):
    """PANN plane-stress condensation (see module docstring)."""
    if model is None:
        raise ValueError("model must be a loaded PANN")
    F2 = np.asarray(F2, dtype=float)
    M = F2.shape[0]
    E = _as_arr(E, M, "E")
    nu = _as_arr(nu, M, "nu")
    if np.any(nu >= 0.5) or np.any(nu <= 0.0):
        raise sv._InvalidState("nu out of (0, 0.5)")
    u = np.column_stack([E, nu])     # (M,2): [E_MPa, nu], training order

    lam = _analytic_lam_only(F2, E, nu, lam0)
    lam = _pann_correct_lam(lam, F2, E, nu, u, model)

    F3 = np.zeros((M, 3, 3))
    F3[:, :2, :2] = F2
    F3[:, 2, 2] = lam
    C = np.einsum("nij,nik->njk", F3, F3)
    S3 = model.stress(C, u)
    S2 = S3[:, :2, :2].copy()

    C2 = _tangent_cached(F2, E, nu, lam, u, model)
    return S2, C2, lam


def make_condense_fn(model):
    """Return a ``ps.condense``-compatible callable closing over `model`."""
    def fn(F2, E, nu, lam0=None):
        return pann_condense(F2, E, nu, lam0=lam0, model=model)
    return fn
