"""2D plane-stress finite-strain FE solver (linear triangles, total Lagrangian).

Physics: paper Eq.(33) Neo-Hookean via :mod:`macro.plane_stress` condensation.
This is a 2D plane-stress *analogue* of the paper's 3D plate-with-hole macro
BVP (paper used FEAP + 8335 tetrahedra); adaptation scope per dispatch T06.

Interface note (for T07/T08): ``E`` and ``nu`` may be scalars or (M,)
per-element arrays, so random-field values can be injected per Gauss point
without changing the solver.
"""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

from .mesh import tri_areas_and_grads
from . import plane_stress as ps

# Voigt ordering for the in-plane gradient/stress (4 components: 11, 22, 12, 21)
_VOIGT = [(0, 0), (1, 1), (0, 1), (1, 0)]


class _InvalidState(Exception):
    """Raised when a trial displacement inverts an element or breaks condensation."""


def _b_matrices(dNdx, dNdz):
    """B (M,4,6): rows [F11, F22, F12, F21], cols [ux1,uz1,ux2,uz2,ux3,uz3]."""
    M = dNdx.shape[0]
    B = np.zeros((M, 4, 6))
    B[:, 0, 0::2] = dNdx     # F11 = d(ux)/dx
    B[:, 1, 1::2] = dNdz     # F22 = d(uz)/dz
    B[:, 2, 0::2] = dNdz     # F12 = d(ux)/dz
    B[:, 3, 1::2] = dNdx     # F21 = d(uz)/dx
    return B


def _deformation_gradient(u, tris, dNdx, dNdz):
    """u: (N,2) -> F2: (M,2,2), F2 = I + sum_I u_I (x) grad N_I."""
    ut = u[tris]                               # (M,3,2)
    M = ut.shape[0]
    F2 = np.empty((M, 2, 2))
    F2[:, 0, 0] = 1.0 + (ut[:, :, 0] * dNdx).sum(axis=1)
    F2[:, 0, 1] = (ut[:, :, 0] * dNdz).sum(axis=1)
    F2[:, 1, 0] = (ut[:, :, 1] * dNdx).sum(axis=1)
    F2[:, 1, 1] = 1.0 + (ut[:, :, 1] * dNdz).sum(axis=1)
    return F2


def plate_bcs(mesh, v_target):
    """Default plate-with-hole BCs: bottom clamped, top uz ramped to -v_target.

    Returns (fix_dofs, ramp_dofs, ramp_final, top_uz_dofs).
    """
    N = mesh["coords"].shape[0]
    bot = np.where(mesh["bnd_bottom"])[0]
    top_uz = 2 * np.where(mesh["bnd_top"])[0] + 1
    fix = np.concatenate([2 * bot, 2 * bot + 1, top_uz])
    return fix, top_uz, np.full(top_uz.shape[0], -v_target), top_uz


def solve(mesh, E, nu, v_target=0.0, n_steps=8, tol=1e-8, maxit=12,
          verbose=False, fix_dofs=None, ramp_dofs=None, ramp_final=None,
          condense_fn=None):
    """Solve the 2D plane-stress problem.

    BCs: bottom edge u=(0,0); top edge uz=-v (ramped), ux free -- unless
    overridden by fix_dofs / ramp_dofs / ramp_final (for patch tests).
    E, nu: scalar or (M,) per-element arrays [E in MPa].
    condense_fn: optional plane-stress constitutive with the same signature
        as ``plane_stress.condense`` ``(F2, E, nu, lam0) -> (S2, C2, lam)``
        (T08: PANN coupling replaces the constitutive at this single point).

    Returns dict with U (N,2), per-element/nodal stresses, QoI, Newton counts.
    """
    coords, tris = mesh["coords"], mesh["tris"]
    N, M = coords.shape[0], tris.shape[0]
    area, dNdx, dNdz = tri_areas_and_grads(coords, tris)
    B = _b_matrices(dNdx, dNdz)
    if condense_fn is None:
        condense_fn = ps.condense

    E_arr = np.full(M, E) if np.ndim(E) == 0 else np.asarray(E, float)
    nu_arr = np.full(M, nu) if np.ndim(nu) == 0 else np.asarray(nu, float)

    # element dof map (M,6)
    edof = np.empty((M, 6), dtype=int)
    edof[:, 0::2] = 2 * tris
    edof[:, 1::2] = 2 * tris + 1

    # Dirichlet BCs
    if fix_dofs is None:
        fix_dofs, ramp_dofs, ramp_final, top_uz = plate_bcs(mesh, v_target)
    else:
        top_uz = None
    fixed = np.zeros(2 * N, dtype=bool)
    fixed[np.asarray(fix_dofs, dtype=int)] = True
    ramp_dofs = np.asarray(ramp_dofs, dtype=int)
    ramp_final = np.asarray(ramp_final, dtype=float)
    fixed[ramp_dofs] = True      # ramped DOFs are Dirichlet within each Newton solve
    free = ~fixed

    U = np.zeros(2 * N)
    lam = np.ones(M)          # warm start for the condensation solve
    iters = []
    A_total = area.sum()
    f_scale = np.max(E_arr) * A_total   # characteristic force [MPa*m^2]

    # COO assembly pattern (fixed sparsity)
    rows = np.repeat(edof, 6, axis=1).ravel()
    cols = np.tile(edof, (1, 6)).ravel()

    def state_at(Uv):
        """Return (fint, Rf, nR, F2, S2, C2, lam_new, J2min) at displacement Uv.

        Raises _InvalidState if any element inverts (J2 <= 0) or the
        plane-stress condensation fails.
        """
        u = Uv.reshape(N, 2)
        F2 = _deformation_gradient(u, tris, dNdx, dNdz)
        J2 = F2[:, 0, 0] * F2[:, 1, 1] - F2[:, 0, 1] * F2[:, 1, 0]
        if np.any(J2 <= 1e-12):
            raise _InvalidState("element inversion")
        S2, C2, lam_new = condense_fn(F2, E_arr, nu_arr, lam0=lam)
        P2 = ps.first_piola_2d(F2, S2)                 # (M,2,2)
        Pv = np.stack([P2[:, a, b] for (a, b) in _VOIGT], axis=1)  # (M,4)
        D = ps.tangent_P(F2, S2, C2)                   # (M,2,2,2,2)
        D44 = np.empty((M, 4, 4))
        for I, (a, b) in enumerate(_VOIGT):
            for J, (c, d) in enumerate(_VOIGT):
                D44[:, I, J] = D[:, a, b, c, d]
        Ke = np.einsum("mij,mjk,mkl->mil", B.transpose(0, 2, 1), D44, B)
        Ke = Ke * area[:, None, None]
        fe = np.einsum("mij,mj->mi", B.transpose(0, 2, 1), Pv) * area[:, None]
        K = coo_matrix((Ke.ravel(), (rows, cols)),
                       shape=(2 * N, 2 * N)).tocsr()
        fint = np.zeros(2 * N)
        np.add.at(fint, edof.ravel(), fe.ravel())
        Rf = fint[free]
        return fint, Rf, float(np.linalg.norm(Rf)), F2, S2, C2, lam_new, K

    # ---- adaptive load stepping on the scalar load factor t in [0,1] ----
    t = 0.0
    dt = 1.0 / n_steps
    U_conv = U.copy()
    lam_conv = lam.copy()
    U_prev = None          # for linear-extrapolation warm start (T08)
    step_count = 0
    while t < 1.0 - 1e-12:
        t_try = min(t + dt, 1.0)
        U_try = U_conv.copy()
        if U_prev is not None:
            # linear extrapolation of the free-DOF increment (T08)
            U_try[free] = U_conv[free] + (U_conv[free] - U_prev[free])
        U_try[ramp_dofs] = ramp_final * t_try
        try:
            st = state_at(U_try)
        except _InvalidState:
            dt *= 0.5
            if dt < 1e-8:
                raise RuntimeError("adaptive stepping: dt underflow")
            continue
        fint, Rf, nR, F2, S2, C2, lam_w, K = st
        lam = lam_w
        U = U_try
        R0 = nR
        ok = False
        for it in range(maxit):
            if verbose:
                print(f"  t={t_try:.3f} it {it}: |R|={nR:.3e} "
                      f"(rel {nR / max(R0, f_scale * 1e-16):.2e})")
            if nR <= tol * max(R0, f_scale * 1e-16):
                ok = True
                break
            dU = np.zeros(2 * N)
            dU[free] = spsolve(K[free, :][:, free], -Rf)
            # backtracking line search: keep J2>0 and decrease |R|
            alpha, accepted = 1.0, False
            for _ls in range(12):
                Utr = U.copy()
                Utr[free] = U[free] + alpha * dU[free]
                try:
                    st2 = state_at(Utr)
                except _InvalidState:
                    alpha *= 0.5
                    continue
                if st2[2] < nR:
                    accepted = True
                    break
                alpha *= 0.5
            if not accepted:
                break  # -> halve dt and retry the step
            U = Utr
            fint, Rf, nR, F2, S2, C2, lam_w, K = st2
            lam = lam_w
        if not ok:
            dt *= 0.5
            if dt < 1e-8:
                raise RuntimeError("adaptive stepping: dt underflow")
            U = U_conv.copy()
            lam = lam_conv.copy()
            continue
        # step accepted
        t = t_try
        U_prev = U_conv.copy()
        U_conv = U.copy()
        lam_conv = lam.copy()
        step_count += 1
        iters.append(it + 1)
        dt = min(dt * 1.5, 1.0 / n_steps)
        if verbose:
            ramped = float(np.max(np.abs(U[ramp_dofs]))) if ramp_dofs.size else 0.0
            print(f"  accepted t={t:.3f}: |ramp|={ramped:.4f} m, "
                  f"{it + 1} iters, next dt={dt:.3f}")

    # ---- post-processing (F2, S2, lam, fint cached from last Newton state) ----
    u = U.reshape(N, 2)
    sig3 = ps.cauchy_stress(F2, lam, E_arr, nu_arr)   # (M,3,3) MPa

    # plate-specific QoI helpers (only for the default plate BCs)
    react_top_z, sigma_nom, scf = np.nan, np.nan, np.nan
    if top_uz is not None:
        react_top_z = -fint[top_uz].sum()      # total vertical force [MPa*m^2]
        Lplate = float(mesh.get("L", 8.0))
        rhole = float(mesh.get("r_hole", 2.0))
        net_width = Lplate - 2.0 * rhole        # plate width minus hole diameter
        sigma_nom = abs(react_top_z) / (net_width * 1.0)

    # nodal averaging of Cauchy stress (element centroid -> nodes)
    signode = np.zeros((N, 3, 3))
    cnt = np.zeros(N)
    for m in range(M):
        for a in tris[m]:
            signode[a] += sig3[m]
            cnt[a] += 1
    signode /= cnt[:, None, None]

    princ = np.linalg.eigvalsh(signode)        # (N,3) ascending
    absmax = np.max(np.abs(princ), axis=1)     # max |principal| per node
    sigma_char = float(np.max(absmax))
    if not np.isnan(sigma_nom) and sigma_nom > 0:
        scf = float(np.max(np.abs(signode[:, 1, 1])) / sigma_nom)

    return {
        "U": u,
        "F2": F2,
        "S2": S2,
        "lam": lam,
        "sig_elem": sig3,
        "sig_node": signode,
        "princ": princ,
        "absmax": absmax,
        "sigma_char": sigma_char,
        "scf": scf,
        "sigma_nom": float(sigma_nom),
        "react_top": float(react_top_z),
        "newton_iters": iters,
        "n_steps": step_count,
        "mesh": mesh,
        "area": area,
    }
