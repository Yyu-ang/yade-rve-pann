"""Self-test for T04b -- run from the repo root (worktree root):

    /home/hatch/workspace/venvs/rve-pann/bin/python surrogate/tests/test_pann.py

Does, end-to-end with fixed seeds:
  1. generate the 50x100 base DoE (T03 neohooke Eq.(33) reference, T04-identical),
  2. generate the T04b boundary augmentation (nu-band [0.33,0.39] + 4 corners,
     train-only),
  3. train the PANN (5->175->175->1, softplus) on base-train + boundary,
  4. assert test-set stress relative L2 < 5% (DOD, no regression vs T04 1.51%),
  5. NEW: assert the four domain corners' S11 at F=diag(1.1,1,1) each have
     relative error < 3% (T05 interval-max root cause; was -5.56% at
     (E=3.5e4, nu=0.39)),
  6. cross-check stress(C,u) against central finite differences of the
     network energy w.r.t. C,
  7. spot-check tangent minor/major symmetries,
  8. save pann_v2.pt + metrics to the T04b sandbox.

Exit code 0 on success; prints the DOD metrics.
"""

import argparse
import json
import os
import sys

import numpy as np
import torch

TESTDIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(TESTDIR))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "surrogate"))

import train_pann  # noqa: E402
from train_pann import neohooke  # noqa: E402
from pann import PANN  # noqa: E402

SEED = 42
TOL_REL_L2 = 0.05
TOL_CORNER = 0.03


def sandbox_dir():
    parts = os.path.abspath(ROOT).split(os.sep)
    if ".worktrees" in parts:
        main_root = os.sep.join(parts[:parts.index(".worktrees")])
    else:
        main_root = os.path.abspath(ROOT)
    d = os.path.join(main_root, "for_worker", "T04b", "w1")
    os.makedirs(d, exist_ok=True)
    return d


def fd_stress(model, C, u, h=1e-7):
    """Central finite differences of model.energy w.r.t. C: S = 2 dPsi/dC.

    Note: for a==b the entry must be perturbed ONCE (Cp[a,a]+=h), while for
    a!=b both symmetric entries are perturbed (each by h) to keep C symmetric.
    """
    C = np.asarray(C, dtype=float)
    u = np.asarray(u, dtype=float)
    from pann import invariants_numpy
    S = np.zeros((3, 3))
    for a in range(3):
        for b in range(a, 3):
            Cp, Cm = C.copy(), C.copy()
            if a == b:
                Cp[a, a] += h
                Cm[a, a] -= h
                dpsi = (model.energy(invariants_numpy(Cp), u)
                        - model.energy(invariants_numpy(Cm), u)) / (2 * h)
                S[a, a] = 2.0 * dpsi
            else:
                Cp[a, b] += h
                Cp[b, a] += h
                Cm[a, b] -= h
                Cm[b, a] -= h
                dpsi = (model.energy(invariants_numpy(Cp), u)
                        - model.energy(invariants_numpy(Cm), u)) / (2 * h)
                # (Psi+-Psi-)/(2h) = 2*dPsi/dC_ab here, so S_ab = dpsi
                S[a, b] = S[b, a] = dpsi
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=2000)
    args = ap.parse_args()

    torch.manual_seed(SEED); np.random.seed(SEED)
    print("[test] generating base DoE ...", flush=True)
    doe = train_pann.generate_doe(seed=SEED)
    tr, te = train_pann.train_test_split(doe, seed=SEED)
    print(f"[test] base DoE points: {doe['I'].shape[0]}, "
          f"train={len(tr)}, test={len(te)}", flush=True)
    assert doe["I"].shape[0] == 5000, "base DoE must be 50x100=5000 points"
    assert len(te) == 500, "test set must stay T04-identical (500 points)"

    print("[test] generating boundary augmentation ...", flush=True)
    doe_b = train_pann.generate_boundary_doe(seed=SEED)
    n_b = doe_b["I"].shape[0]
    print(f"[test] boundary points: {n_b} "
          f"({doe_b['n_u']} U x {train_pann.N_F} F, skipped={doe_b['n_skipped']})",
          flush=True)
    assert doe_b["n_u"] == train_pann.N_BAND_U + len(train_pann.CORNERS)
    assert n_b >= (train_pann.N_BAND_U + len(train_pann.CORNERS)) \
        * train_pann.N_F - 50, "too many det(F) skips in boundary DoE"

    doe_all, tr_aug, te = train_pann.build_augmented(doe, tr, te, doe_b)
    print(f"[test] augmented train={len(tr_aug)}, test={len(te)}", flush=True)

    print(f"[test] training {args.epochs} epochs ...", flush=True)
    model, history, metrics, scaler = train_pann.train_model(
        doe_all, tr_aug, te, epochs=args.epochs, seed=SEED, log_every=500)
    metrics["strategy"] = "T04b boundary-band augmentation (train-only)"
    metrics["n_boundary"] = int(n_b)
    print("[test] test_rel_l2 = %.4f%%  (DOD < 5%%, target <= 2%%)"
          % (100 * metrics["test_rel_l2"]))
    print("[test] train_rel_l2 = %.4f%%, loss tail = %.3e"
          % (100 * metrics["train_rel_l2"], metrics["train_loss_tail"]))
    assert metrics["test_rel_l2"] < TOL_REL_L2, \
        f"DOD FAILED: test rel L2 {metrics['test_rel_l2']:.4f} >= 5%"

    # ---- NEW (T04b): four-corner S11 accuracy at F=diag(1.1,1,1) ----
    F_c = np.diag([1.1, 1.0, 1.0])
    corner_errs = []
    for (E_c, nu_c) in train_pann.CORNERS:
        S_ref = neohooke.pk2_stress(F_c, E_c, nu_c)
        S_pred = model.stress_F(F_c, np.array([E_c, nu_c]))
        err = abs(S_pred[0, 0] - S_ref[0, 0]) / abs(S_ref[0, 0])
        corner_errs.append(err)
        print("[test] corner (E=%.1e, nu=%.2f): S11 pred=%.2f ref=%.2f "
              "rel err=%.4f%%  (DOD < 3%%)"
              % (E_c, nu_c, S_pred[0, 0], S_ref[0, 0], 100 * err))
    assert max(corner_errs) < TOL_CORNER, \
        f"DOD FAILED: corner rel err {max(corner_errs):.4f} >= 3%"

    # ---- stress cross-check: autograd vs finite differences of energy ----
    rng = np.random.RandomState(SEED + 7)
    fd_errs = []
    for k in rng.choice(len(te), size=3, replace=False):
        Ck, uk = doe_all["C"][te[k]], doe_all["u"][te[k]]
        S_ad = model.stress(Ck, uk)
        S_fd = fd_stress(model, Ck, uk)
        err = (np.linalg.norm(S_ad - S_fd)
               / max(np.linalg.norm(S_fd), 1e-30))
        fd_errs.append(err)
    print("[test] stress autograd-vs-FD rel err: "
          + ", ".join(f"{e:.2e}" for e in fd_errs))
    assert max(fd_errs) < 1e-3, "stress autograd/FD cross-check FAILED"

    # ---- tangent: symmetry + FD prediction dS = C:dE ----
    Ck, uk = doe_all["C"][te[0]], doe_all["u"][te[0]]
    C4 = model.tangent(Ck, uk)
    minor = max(np.abs(C4 - C4.transpose(1, 0, 2, 3)).max(),
                np.abs(C4 - C4.transpose(0, 1, 3, 2)).max())
    major = np.abs(C4 - C4.transpose(2, 3, 0, 1)).max()
    scale = np.abs(C4).max()
    print("[test] tangent minor/major symmetry rel: %.2e / %.2e"
          % (minor / scale, major / scale))
    assert minor / scale < 1e-8 and major / scale < 1e-8, \
        "tangent symmetry check FAILED"
    rng2 = np.random.RandomState(SEED + 11)
    dC = rng2.randn(3, 3); dC = 0.5 * (dC + dC.T)
    dC *= 1e-6 / np.abs(dC).max()
    dS_fd = 0.5 * (model.stress(Ck + dC, uk) - model.stress(Ck - dC, uk))
    # tangent convention (paper Eq. 13): dS = C:dE with E=(C-I)/2
    dS_pred = np.einsum("ijkl,kl->ij", C4, 0.5 * dC)
    tan_err = np.linalg.norm(dS_pred - dS_fd) / np.linalg.norm(dS_fd)
    print("[test] tangent dS-prediction rel err: %.2e" % tan_err)
    assert tan_err < 1e-4, "tangent FD prediction check FAILED"

    # ---- save checkpoint + metrics to the T04b sandbox (not git) ----
    outdir = sandbox_dir()
    ckpt_path = os.path.join(outdir, "pann_v2.pt")
    model.save(ckpt_path)
    np.savez(os.path.join(outdir, "loss_history.npz"),
             loss=np.array(history))
    np.savez(os.path.join(outdir, "scaler.npz"),
             c_in=scaler[0], s_in=scaler[1], y_std=scaler[2])
    with open(os.path.join(outdir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[test] checkpoint -> {ckpt_path}")

    print("[test] ALL CHECKS PASSED (exit 0)")


if __name__ == "__main__":
    main()
