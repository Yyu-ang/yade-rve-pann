"""3D finite-strain FE solver (hex8, total Lagrangian) for T09.

Mirrors ``macro/solver.py`` (2D): adaptive load stepping on the scalar
load factor t in [0, 1], Newton with backtracking line search, element
inversion guard. Differences:

- 8-node trilinear hexahedra, 2x2x2 Gauss (``macro3d.mesh3d``);
- full 3D Eq.(33) via ``S_fn(F, E, nu) -> S`` (default: analytic ref);
- material tangent A_ijkl = dP_ij/dF_kl by batched forward FD
  (``macro3d.constitutive3d.fd_tangent``), shared by ref and PANN paths;
- ``need_tangent=False`` in ``state_at`` skips the tangent for line-search
  trials (the tangent dominates PANN cost).

E, nu: scalar or (M_elem,) per-element arrays [E in MPa].
"""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

from .mesh3d import hex_geom, GAUSS_W
from . import constitutive3d as c3


class _InvalidState(Exception):
    """Trial displacement inverts an element or breaks the constitutive."""


def _b_matrix(dNdx):
    """B (G,9,24): F_ab = delta_ab + sum_I u_{I,a} dN_I/dX_b.

    Row r = 3*a+b, column c = 3*I+a: B[g, 3a+b, 3I+a] = dNdx[g, I, b].
    """
    G = dNdx.shape[0]
    B = np.zeros((G, 9, 24))
    for a in range(3):
        for b in range(3):
            B[:, 3 * a + b, a::3] = dNdx[:, :, b]
    return B


def _deformation_gradient(u, hexes, dNdx_e):
    """u (N,3) -> F (Me*8,3,3) at all Gauss points. dNdx_e: (Me,8,8,3)."""
    uh = u[hexes]                                  # (Me,8,3)
    Me = hexes.shape[0]
    # F[m,g,a,b] = delta_ab + sum_I uh[m,I,a] * dNdx_e[m,g,I,b]
    F = np.zeros((Me, 8, 3, 3))
    for a in range(3):
        F[:, :, a, a] = 1.0
    # dNdx_e is (m,g,e,b): dN_e/dX_b at Gauss point g of element m
    F += np.einsum("mea,mgeb->mgab", uh, dNdx_e)
    return F.reshape(Me * 8, 3, 3)


def plate_bcs_3d(mesh, v_target):
    """Bottom face (y=-L/2) clamped; top face (y=+L/2) uy ramped to -v."""
    b = np.where(mesh["bnd_bottom"])[0]
    t = np.where(mesh["bnd_top"])[0]
    fix = np.concatenate([3 * b, 3 * b + 1, 3 * b + 2])
    ramp = 3 * t + 1
    return fix, ramp, np.full(ramp.shape[0], -v_target), ramp


def solve(mesh, E, nu, v_target=0.0, n_steps=8, tol=1e-8, maxit=12,
          verbose=False, fix_dofs=None, ramp_dofs=None, ramp_final=None,
          S_fn=None, fixed_values=None):
    """Solve the 3D plate-with-hole problem. Returns dict (see 2D solver).

    fixed_values: optional (3N,) array of prescribed values on fixed DOFs
    (patch test with non-zero Dirichlet data); default 0.
    """
    coords, hexes = mesh["coords"], mesh["hexes"]
    N, Me = coords.shape[0], hexes.shape[0]
    detJ, dNdx, _ = hex_geom(coords, hexes)      # (Me,8), (Me,8,8,3)
    G = Me * 8
    dNdx_g = dNdx.reshape(G, 8, 3)
    detJ_g = detJ.reshape(G)
    B = _b_matrix(dNdx_g)                        # (G,9,24)
    wdet = (detJ_g * np.tile(GAUSS_W, Me))       # (G,)

    if S_fn is None:
        S_fn = c3.ref_S
    E_arr = np.full(Me, E) if np.ndim(E) == 0 else np.asarray(E, float)
    nu_arr = np.full(Me, nu) if np.ndim(nu) == 0 else np.asarray(nu, float)
    E_g = np.repeat(E_arr, 8)
    nu_g = np.repeat(nu_arr, 8)

    edof = np.empty((Me, 24), dtype=int)
    for I in range(8):
        edof[:, 3 * I:3 * I + 3] = 3 * hexes[:, I, None] + np.arange(3)

    if fix_dofs is None:
        fix_dofs, ramp_dofs, ramp_final, top_uy = plate_bcs_3d(mesh, v_target)
    else:
        top_uy = None
    fixed = np.zeros(3 * N, dtype=bool)
    fixed[np.asarray(fix_dofs, dtype=int)] = True
    ramp_dofs = np.asarray(ramp_dofs, dtype=int)
    ramp_final = np.asarray(ramp_final, dtype=float)
    fixed[ramp_dofs] = True
    free = ~fixed

    U = np.zeros(3 * N)
    if fixed_values is not None:
        fv = np.asarray(fixed_values, dtype=float)
        assert fv.shape == (3 * N,)
        U[fixed] = fv[fixed]
    iters = []
    vol = float(wdet.sum())
    f_scale = np.max(E_arr) * vol

    rows = np.repeat(edof, 24, axis=1).ravel()
    cols = np.tile(edof, (1, 24)).ravel()

    def state_at(Uv, need_tangent=True):
        u = Uv.reshape(N, 3)
        F = _deformation_gradient(u, hexes, dNdx)          # (G,3,3)
        J = np.linalg.det(F)
        if np.any(J <= 1e-12):
            raise _InvalidState("element inversion")
        S = S_fn(F, E_g, nu_g)                             # (M->G,3,3)
        P = c3.first_piola_3d(F, S)
        Pv = P.reshape(G, 9)
        if need_tangent:
            A = c3.fd_tangent(S_fn, F, E_g, nu_g)           # (G,9,9)
            Ke = np.einsum("gij,gjk,gkl->gil", B.transpose(0, 2, 1), A, B)
            Ke = Ke * wdet[:, None, None]
            Ke = Ke.reshape(Me, 8, 24, 24).sum(axis=1)     # (Me,24,24)
            K = coo_matrix((Ke.ravel(), (rows, cols)),
                           shape=(3 * N, 3 * N)).tocsr()
        else:
            K = None
        fe = np.einsum("gij,gj->gi", B.transpose(0, 2, 1), Pv) * wdet[:, None]
        fe = fe.reshape(Me, 8, 24).sum(axis=1)
        fint = np.zeros(3 * N)
        np.add.at(fint, edof.ravel(), fe.ravel())
        Rf = fint[free]
        return fint, Rf, float(np.linalg.norm(Rf)), F, S, K

    t = 0.0
    dt = 1.0 / n_steps
    U_conv = U.copy()
    U_prev = None
    step_count = 0
    while t < 1.0 - 1e-12:
        t_try = min(t + dt, 1.0)
        U_try = U_conv.copy()
        if U_prev is not None:
            U_try[free] = U_conv[free] + (U_conv[free] - U_prev[free])
        U_try[ramp_dofs] = ramp_final * t_try
        try:
            st = state_at(U_try)
        except _InvalidState:
            dt *= 0.5
            if dt < 1e-8:
                raise RuntimeError("adaptive stepping: dt underflow")
            continue
        fint, Rf, nR, F, S, K = st
        U = U_try
        R0 = nR
        ok = False
        for it in range(maxit):
            if verbose:
                print(f"  t={t_try:.3f} it {it}: |R|={nR:.3e}")
            if nR <= tol * max(R0, f_scale * 1e-16):
                ok = True
                break
            dU = np.zeros(3 * N)
            dU[free] = spsolve(K[free, :][:, free], -Rf)
            alpha, accepted = 1.0, False
            for _ls in range(12):
                Utr = U.copy()
                Utr[free] = U[free] + alpha * dU[free]
                try:
                    st2 = state_at(Utr, need_tangent=False)
                except (_InvalidState, ValueError):
                    alpha *= 0.5
                    continue
                if st2[2] < nR:
                    accepted = True
                    break
                alpha *= 0.5
            if not accepted:
                break
            U = Utr
            fint, Rf, nR, F, S, K = state_at(Utr)
        if not ok:
            dt *= 0.5
            if dt < 1e-8:
                raise RuntimeError("adaptive stepping: dt underflow")
            U = U_conv.copy()
            continue
        t = t_try
        U_prev = U_conv.copy()
        U_conv = U.copy()
        step_count += 1
        iters.append(it + 1)
        dt = min(dt * 1.5, 1.0 / n_steps)

    # ---- post-processing ----
    u = U.reshape(N, 3)
    sig_g = c3.cauchy_stress_3d(F, S)                       # (G,3,3)
    sig_elem = sig_g.reshape(Me, 8, 3, 3).mean(axis=1)      # (Me,3,3)
    signode = np.zeros((N, 3, 3))
    cnt = np.zeros(N)
    for e in range(Me):
        for a in hexes[e]:
            signode[a] += sig_elem[e]
            cnt[a] += 1
    signode /= cnt[:, None, None]
    princ = np.linalg.eigvalsh(signode)
    absmax = np.max(np.abs(princ), axis=1)
    sigma_char = float(np.max(absmax))

    react_top = np.nan
    sigma_nom = np.nan
    scf = np.nan
    if top_uy is not None:
        react_top = -fint[top_uy].sum()
        Lplate = float(mesh.get("L", 8.0))
        rhole = float(mesh.get("r_hole", 2.0))
        thick = float(mesh.get("t", 1.0))
        net_area = (Lplate - 2.0 * rhole) * thick
        sigma_nom = abs(react_top) / net_area if net_area > 0 else np.nan
        if sigma_nom > 0:
            scf = float(np.max(np.abs(signode[:, 1, 1])) / sigma_nom)

    return {
        "U": u,
        "F": F,
        "S": S,
        "sig_elem": sig_elem,
        "sig_node": signode,
        "princ": princ,
        "absmax": absmax,
        "sigma_char": sigma_char,
        "scf": scf,
        "sigma_nom": float(sigma_nom),
        "react_top": float(react_top),
        "newton_iters": iters,
        "n_steps": step_count,
        "mesh": mesh,
    }
