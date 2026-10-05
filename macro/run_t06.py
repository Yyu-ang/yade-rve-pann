"""T06 self-test: 5 DOD checks for the 2D plane-stress macro BVP solver.

Run:  python -m macro.run_t06   (from the worktree root)
Prints ALL CHECKS PASSED on success.

Seeds: mesh 20261005 (fixed in macro.mesh); no other randomness.
"""

import os
import sys

import numpy as np
from scipy.optimize import root

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from macro import mesh as mm
from macro import solver as sv
from macro import plane_stress as ps

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "examples", "ex1_neohooke"))
import neohooke as nh

E_EX = 3.0e4      # MPa, example realization
NU_EX = 0.3
SEED = 20261005

NEWTON_MAX = []   # track all Newton iteration counts globally


def _record_iters(res):
    NEWTON_MAX.extend(res["newton_iters"])


# ---------------------------------------------------------------- DOD 1
def dod1_uniaxial_patch():
    """1x1 hole-free plate, uniaxial tension along x (small strain).

    S11 (PK2) from the solver vs independent high-precision solution of
    Eq.(33) with S22 = S33 = 0 (scipy root on T03 pk2_stress).
    """
    print("[DOD1] uniaxial patch test ...")
    coords = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]])
    tris = np.array([[0, 1, 2], [0, 2, 3]])
    mesh = {"coords": coords, "tris": tris}
    delta = 1e-3
    left = np.where(coords[:, 0] == 0.0)[0]
    right = np.where(coords[:, 0] == 1.0)[0]
    fix = np.concatenate([2 * left, [1]])          # left ux=0, node0 uz=0
    ramp = 2 * right                              # right ux -> +delta
    res = sv.solve(mesh, E_EX, NU_EX, n_steps=2, fix_dofs=fix,
                   ramp_dofs=ramp, ramp_final=np.full(2, delta))
    _record_iters(res)
    S11_fe = float(res["S2"][:, 0, 0].mean())
    nonuni = float(np.abs(res["S2"][:, 0, 0] - S11_fe).max())

    # independent analytical reference: solve S22=S33=0 for (f22, lam3)
    lam11 = 1.0 + delta

    def eqs(x):
        f22, lam3 = x
        F = np.diag([lam11, f22, lam3])
        S = nh.pk2_stress(F, E_EX, NU_EX)
        return [S[1, 1], S[2, 2]]

    sol = root(eqs, [1.0 - NU_EX * delta, 1.0 - NU_EX * delta], tol=1e-12)
    res_norm = float(np.linalg.norm(eqs(sol.x)))
    assert res_norm < 1e-9 * E_EX, \
        f"analytical root solve failed (res={res_norm:.2e})"
    F = np.diag([lam11, sol.x[0], sol.x[1]])
    S11_ref = float(nh.pk2_stress(F, E_EX, NU_EX)[0, 0])
    err = abs(S11_fe - S11_ref) / abs(S11_ref)
    print(f"  S11_fe={S11_fe:.6f} MPa, S11_ref={S11_ref:.6f} MPa, "
          f"rel err={err:.2e}, nonuniformity={nonuni:.2e}")
    assert err < 0.01, "DOD1 FAILED: rel err >= 1%"
    print("  DOD1 PASS")


# ---------------------------------------------------------------- DOD 2
def dod2_scf():
    """Linear-elastic limit: v=1e-4 m, SCF = max|sig_zz|/sigma_nom.

    NOTE (documented deviation): the dispatch cites Kirsch 3.0, which is the
    infinite-plate value (d/W -> 0). The paper geometry has d/W = 4/8 = 0.5,
    for which the finite-width theory (Howland/Heywood, Peterson) gives
    K_net ~= 2.16. The solver is independently verified at d/W = 0.1:
    SCF = 2.75 vs Heywood 2.72 (1.3%). Here we check against 2.16.
    """
    print("[DOD2] linear-elastic SCF ...")
    mesh = mm.plate_with_hole(n_points=1100, n_hole_edge=140, seed=SEED)
    res = sv.solve(mesh, E_EX, NU_EX, v_target=1e-4, n_steps=2)
    _record_iters(res)
    scf = res["scf"]
    print(f"  tris={mesh['tris'].shape[0]}, SCF={scf:.4f} "
          f"(finite-width theory 2.16; Kirsch inf-plate 3.0 N/A at d/W=0.5)")

    # independent verification at small hole ratio
    m2 = mm.plate_with_hole(n_points=1500, n_hole_edge=120, seed=SEED,
                            L=20.0, r_hole=1.0)
    r2 = sv.solve(m2, E_EX, NU_EX, v_target=2.5e-4, n_steps=2)
    _record_iters(r2)
    print(f"  d/W=0.1 check: SCF={r2['scf']:.4f} (Heywood ~2.72)")
    assert abs(r2["scf"] - 2.72) / 2.72 < 0.05, "d/W=0.1 verification failed"
    assert abs(scf - 2.16) / 2.16 < 0.10, "DOD2 FAILED: SCF far from 2.16"
    print("  DOD2 PASS (against applicable finite-width theory; "
          "dispatch 3.0 deviation documented)")


# ---------------------------------------------------------------- DOD 3
def dod3_mesh_convergence():
    """v=0.5 m: coarse vs fine mesh sigma_char relative difference < 5%."""
    print("[DOD3] mesh convergence at v=0.5 m ...")
    out = []
    for np_pts, tag in [(550, "coarse"), (1100, "fine")]:
        mesh = mm.plate_with_hole(n_points=np_pts, seed=SEED)
        res = sv.solve(mesh, E_EX, NU_EX, v_target=0.5, n_steps=8)
        _record_iters(res)
        out.append((tag, mesh["tris"].shape[0], res["sigma_char"]))
        print(f"  {tag}: tris={mesh['tris'].shape[0]}, "
              f"sigma_char={res['sigma_char']:.4f} MPa, "
              f"iters={res['newton_iters']}")
    rel = abs(out[1][2] - out[0][2]) / out[1][2]
    print(f"  relative difference = {rel:.4f}")
    assert rel < 0.05, "DOD3 FAILED: rel diff >= 5%"
    print("  DOD3 PASS")
    return out


# ---------------------------------------------------------------- DOD 4
def dod4_newton_iters():
    print("[DOD4] Newton iterations per load step ...")
    mx = max(NEWTON_MAX)
    print(f"  max over all solves/steps: {mx} (limit 12)")
    assert mx <= 12, "DOD4 FAILED"
    print("  DOD4 PASS")


# ---------------------------------------------------------------- DOD 5
def dod5_fig6():
    """Fig. 6 analogue: geometry + |principal stress| for the example
    realization (E=3.0e4 MPa, nu=0.3, v=0.69 m). PNG + CSV -> figures/T06/."""
    print("[DOD5] Fig.6 analogue (E=3.0e4 MPa, nu=0.3, v=0.69 m) ...")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri

    mesh = mm.plate_with_hole(n_points=1100, n_hole_edge=140, seed=SEED)
    res = sv.solve(mesh, E_EX, NU_EX, v_target=0.69, n_steps=10)
    _record_iters(res)
    coords, tris = mesh["coords"], mesh["tris"]
    val = res["absmax"]          # nodal max |principal stress| [MPa]
    print(f"  tris={tris.shape[0]}, sigma_char={res['sigma_char']:.2f} MPa, "
          f"iters={res['newton_iters']}")

    outdir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "figures", "T06")
    os.makedirs(outdir, exist_ok=True)

    fig, ax = plt.subplots(1, 2, figsize=(13, 5.2))
    # (a) geometry
    ax[0].triplot(coords[:, 0], coords[:, 1], tris, color="0.55", lw=0.25)
    ax[0].set_aspect("equal")
    ax[0].set_title("(a) mesh (2D plane-stress analogue)")
    ax[0].set_xlabel("x [m]")
    ax[0].set_ylabel("z [m]")
    # (b) |principal stress|
    triang = mtri.Triangulation(coords[:, 0], coords[:, 1], tris)
    cf = ax[1].tricontourf(triang, val, levels=24, cmap="inferno")
    ax[1].set_aspect("equal")
    ax[1].set_title(r"(b) $\max_i\,|\sigma_i|$ [MPa]  (2D plane-stress analogue)")
    ax[1].set_xlabel("x [m]")
    ax[1].set_ylabel("z [m]")
    fig.colorbar(cf, ax=ax[1], label="MPa")
    fig.suptitle("Plate with hole \u2014 2D plane-stress analogue of paper Fig. 6\n"
                 "(Harazin et al., CMAME 452 (2026) 118726), "
                 f"E={E_EX:.1e} MPa, nu={NU_EX}, v=0.69 m (example realization)",
                 fontsize=11)
    fig.subplots_adjust(top=0.82)
    png = os.path.join(outdir, "fig6_analog.png")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    csv = os.path.join(outdir, "fig6_analog_nodal.csv")
    data = np.column_stack([coords, val, res["princ"]])
    np.savetxt(csv, data, delimiter=",",
               header="x[m],z[m],max_abs_principal[MPa],princ1,princ2,princ3",
               comments="")
    print(f"  wrote {png}")
    print(f"  wrote {csv}")
    assert os.path.getsize(png) > 0 and os.path.getsize(csv) > 0
    print("  DOD5 PASS")


def main():
    dod1_uniaxial_patch()
    dod2_scf()
    dod3_mesh_convergence()
    dod5_fig6()
    dod4_newton_iters()   # after all solves so the global max is complete
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
