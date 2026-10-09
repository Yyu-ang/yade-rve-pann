"""T09 validation (lightweight; must not disturb the 2D T08 full run).

V0: FD material tangent vs central differences (ref law).
V1: 3D patch test on a box mesh -- affine Dirichlet on all faces;
    numerical S vs analytic Eq.(33), rel err < 1e-8.
V2: single plate-with-hole solve, constant E/nu -- Newton converges,
    sigma_char finite, SCF plausible; ref-vs-PANN single-sample agreement.
V3: 3D KL smoke -- 10 realizations, no crash, shapes finite.
V4: mini MC (N0=50) kill/resume continuity via run_3d.py.

Run:  nice -n 19 <venv>/bin/python 3d/validate_3d.py | tee 3d/validation.log
"""

import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import torch
torch.set_num_threads(1)

from macro3d import mesh3d, constitutive3d as c3, solver3d as sv3, kl3d, uq3d
from macro3d.mesh3d import element_centroids

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append(cond)
    print(f"[{PASS if cond else FAIL}] {name} {detail}", flush=True)
    return cond


def v0_tangent():
    print("== V0: FD tangent vs central differences ==")
    # physically relevant states for our BVP: J in [0.85, 1.15], mild shear
    # (extreme compression J~0.1 makes forward FD rounding-dominated;
    #  the solver never sees such states -- guarded by _InvalidState)
    F = np.array([
        [[1.06, 0.03, 0.00], [0.00, 0.94, 0.02], [0.00, 0.00, 1.01]],
        [[0.97, -0.02, 0.01], [0.02, 1.03, 0.00], [0.00, -0.01, 0.99]],
        [[1.10, 0.00, 0.02], [0.00, 0.92, -0.03], [0.01, 0.00, 1.04]],
        [[0.95, 0.04, 0.00], [-0.03, 1.02, 0.01], [0.00, 0.02, 0.97]],
        [[1.02, 0.00, -0.02], [0.01, 0.98, 0.00], [0.03, 0.00, 1.00]],
        [[0.99, -0.04, 0.01], [0.00, 1.05, 0.02], [-0.01, 0.00, 0.96]],
    ])
    M = F.shape[0]
    J = np.linalg.det(F)
    assert (J > 0.85).all() and (J < 1.15).all(), J
    E = np.full(M, 3.0e4)
    nu = np.full(M, 0.3)
    A_fd = c3.fd_tangent(c3.ref_S, F, E, nu)
    # central-difference reference
    h = 1e-7 * np.maximum(1.0, np.abs(F))
    A_cd = np.zeros((M, 9, 9))
    S0 = c3.ref_S(F, E, nu)
    P0 = c3.first_piola_3d(F, S0)
    for q in range(9):
        k, l = divmod(q, 3)
        dF = np.zeros((M, 3, 3))
        dF[:, k, l] = h[:, k, l] / 2
        Sp = c3.ref_S(F + dF, E, nu)
        Sm = c3.ref_S(F - dF, E, nu)
        Pp = c3.first_piola_3d(F + dF, Sp)
        Pm = c3.first_piola_3d(F - dF, Sm)
        A_cd[:, :, q] = ((Pp - Pm) / h[:, k, l][:, None, None]).reshape(M, 9)
    err = np.abs(A_fd - A_cd).max() / np.abs(A_cd).max()
    return check("V0 fd-tangent rel err < 1e-6", err < 1e-6, f"err={err:.2e}")


def v1_patch():
    print("== V1: patch test (box, affine Dirichlet) ==")
    mesh = mesh3d.box_mesh(2, 2, 2, 1.0, 1.0, 1.0)
    Fbar = np.array([[1.08, 0.05, 0.0],
                     [0.00, 0.94, 0.02],
                     [0.00, 0.00, 1.02]])
    X = mesh["coords"]
    U_aff = ((Fbar - np.eye(3)) @ X.T).T          # (N,3)
    N = X.shape[0]
    all_dofs = np.arange(3 * N)
    res = sv3.solve(mesh, 3.0e4, 0.3, v_target=0.0, n_steps=1,
                    fix_dofs=all_dofs, ramp_dofs=np.array([], dtype=int),
                    ramp_final=np.array([]),
                    fixed_values=U_aff.reshape(-1))
    S_num = res["S"].reshape(-1, 8, 3, 3)[:, 0]   # one Gauss pt per elem
    S_ref = c3.ref_S(np.broadcast_to(Fbar, S_num.shape), 3.0e4, 0.3)
    err = np.abs(S_num - S_ref).max() / np.abs(S_ref).max()
    ok = check("V1 patch S rel err < 1e-8", err < 1e-8, f"err={err:.2e}")
    res0 = sv3.solve(mesh, 3.0e4, 0.3, v_target=0.0, n_steps=1,
                     fix_dofs=all_dofs, ramp_dofs=np.array([], dtype=int),
                     ramp_final=np.array([]),
                     fixed_values=U_aff.reshape(-1))
    ok &= check("V1 newton iters small", max(res0["newton_iters"]) <= 3,
                f"iters={res0['newton_iters']}")
    return ok


def v2_single_sample():
    print("== V2: plate-with-hole single sample (const E/nu) ==")
    mesh = mesh3d.plate_with_hole_3d(n_theta=16, n_r=3, n_z=2, t=1.0)
    t0 = time.time()
    res = sv3.solve(mesh, 3.0e4, 0.3, v_target=0.3, n_steps=8, tol=1e-8)
    dt = time.time() - t0
    print(f"    single-sample wall time: {dt:.1f} s "
          f"(hex={mesh['n_hex']}, dofs={3*mesh['n_nodes']})")
    ok = check("V2 newton converged", all(i <= 12 for i in res["newton_iters"]),
               f"iters={res['newton_iters']}")
    ok &= check("V2 sigma_char finite & positive",
                np.isfinite(res["sigma_char"]) and res["sigma_char"] > 0,
                f"sigma_char={res['sigma_char']:.1f} MPa")
    ok &= check("V2 SCF plausible (1.2..2.6 on coarse mesh)", 1.2 < res["scf"] < 2.6,
                f"scf={res['scf']:.3f} (rises to 1.91 at 1152 hex -> ~2.16 Heywood)")
    # PANN single-sample agreement (informational sanity)
    ckpt = os.path.expanduser(
        "~/workspace/yade-rve-pann/for_worker/T04b/w1/pann_v2.pt")
    if os.path.exists(ckpt):
        from surrogate.pann import PANN
        model = PANN.load(ckpt)
        model.eval()
        t1 = time.time()
        resp = sv3.solve(mesh, 3.0e4, 0.3, v_target=0.3, n_steps=8,
                         tol=1e-6, S_fn=c3.make_pann_S(model))
        dtp = time.time() - t1
        rel = abs(resp["sigma_char"] - res["sigma_char"]) / res["sigma_char"]
        print(f"    PANN single-sample wall time: {dtp:.1f} s")
        ok &= check("V2 PANN sigma_char within 8% of ref", rel < 0.08,
                    f"rel={rel:.3%}")
    else:
        print("    [skip] PANN ckpt not found")
    return ok, dt


def v3_kl_smoke():
    print("== V3: 3D KL smoke ==")
    t0 = time.time()
    E_rf = kl3d.make_E_field_3d(mu_E_i=3.0e4, t=1.0, h=0.5, n_z=3)
    nu_rf = kl3d.make_nu_field_3d(t=1.0, h=0.5, n_z=3)
    kl3d.report(E_rf, nu_rf)
    print(f"    KL build time: {time.time()-t0:.1f} s")
    mesh = mesh3d.plate_with_hole_3d(n_theta=8, n_r=2, n_z=1, t=1.0)
    cent = element_centroids(mesh)
    rng = np.random.default_rng(0)
    ok = True
    for k in range(10):
        Ee = E_rf.sample(rng.standard_normal(E_rf.n_modes), cent)
        ne = nu_rf.sample(rng.standard_normal(nu_rf.n_modes), cent)
        ok &= bool(np.isfinite(Ee).all() and np.isfinite(ne).all())
        ok &= bool((Ee > 0).all() and ((ne > 0) & (ne < 0.5)).all())
    return check("V3 10 realizations finite & in bounds", ok)


def v4_kill_resume():
    print("== V4: mini-MC kill/resume ==")
    import signal
    outdir = os.path.join(HERE, "output_v4")
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    py = sys.executable
    cmd = [py, os.path.join(HERE, "run_3d.py"),
           "--mu", "3.0e4", "--constitutive", "ref",
           "--n0", "50", "--dn", "25", "--ncap", "75",
           "--theta", "8", "--nr", "2", "--nz", "1",
           "--workers", "1", "--intra-ckpt", "5",
           "--tag", "v4test", "--outdir", outdir]
    env = dict(os.environ)
    # NOTE: never use stdout=PIPE here: run_3d forks pool workers that
    # inherit the pipe; killing only the parent orphans them and the
    # parent's read() then blocks forever. Use files + process-group kill.
    log1 = os.path.join(outdir, "phase1.log")
    with open(log1, "w") as fh:
        p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                             env=env, start_new_session=True)
        try:
            p.wait(timeout=30)
            killed = False
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)   # parent AND forked workers
            p.wait()
            killed = True
    ckpt = os.path.join(outdir, "v4test_mu3.0e+04_ref_checkpoint.npz")
    has_ckpt = os.path.exists(ckpt)
    n1 = int(np.load(ckpt)["sigma_char"].shape[0]) if has_ckpt else 0
    print(f"    killed={killed} checkpoint N={n1}")
    ok = check("V4 checkpoint written before kill", has_ckpt and n1 > 0,
               f"N={n1}")
    # resume to completion
    log2 = os.path.join(outdir, "phase2.log")
    with open(log2, "w") as fh:
        p2 = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                            env=env, timeout=900)
    out2 = open(log2).read()
    resumed = "resuming at N=" in out2
    final = os.path.join(outdir, "v4test_mu3.0e+04_ref.npz")
    ok &= check("V4 resume detected checkpoint", resumed)
    ok &= check("V4 final npz written", os.path.exists(final))
    if os.path.exists(final):
        d = np.load(final, allow_pickle=True)
        n = int(np.isfinite(d["sigma_char"]).sum())
        ok &= check("V4 sample continuity (N=75, no gap/dup)",
                    n == 75 and len(d["sigma_char"]) == 75, f"N={n}")
    return ok


def main():
    t0 = time.time()
    ok = True
    ok &= v0_tangent()
    ok &= v1_patch()
    ok2, dt_single = v2_single_sample()
    ok &= ok2
    ok &= v3_kl_smoke()
    ok &= v4_kill_resume()
    print(f"\nALL VALIDATION {'PASSED' if ok else 'FAILED'} "
          f"({time.time()-t0:.0f}s total)")
    print(f"[timing] single 3D sample (96 hex, const E/nu): {dt_single:.1f} s")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
