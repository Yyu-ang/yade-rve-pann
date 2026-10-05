"""DoE generation + PANN training -- v2 plan Phase 1A, task T04.

DoE (paper Sec. 4.2.2, Sec. 5.1, domain-separated):
  U space : 50 LHS samples of (E, nu), E in [2.5,3.5]e4 MPa, nu in [0.21,0.39]
  mech    : per U sample, 100 LHS of H (9 comps) in [-0.2,0.2], F = H + I
  total   : 5000 points, reference S from T03 neohooke.pk2_stress (Eq.(33))

Training (paper Sec. 4.2.1, Eq.(12)):
  90/10 split (seeded); inputs affinely scaled to [-1,1] from train min/max;
  targets = Voigt S per-component-std normalized (loss = MSE on normalized,
  equivalent to weighted Eq.(12)); net 5->175->175->1 softplus, Adam.

Artifacts (sandbox, NOT git): dataset npz, checkpoint pt, metrics json,
loss history npz. Run from the repo root:
  /home/hatch/workspace/venvs/rve-pann/bin/python surrogate/train_pann.py [--epochs N] [--outdir DIR]
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _find_neohooke_dir():
    """Locate T03's neohooke.py (read-only input): worktree first, then the
    main checkout (worktree may predate the T03 merge)."""
    cands = [
        os.path.join(ROOT, "examples", "ex1_neohooke"),
        os.path.normpath(os.path.join(ROOT, "..", "..", "..",
                                      "examples", "ex1_neohooke")),
        "/home/hatch/workspace/yade-rve-pann/examples/ex1_neohooke",
    ]
    for c in cands:
        if os.path.isfile(os.path.join(c, "neohooke.py")):
            return c
    raise ImportError("neohooke.py not found in %r" % cands)


sys.path.insert(0, _find_neohooke_dir())

from surrogate.pann import PANN, invariants_numpy, voigt6  # noqa: E402
import neohooke  # noqa: E402
from scipy.stats.qmc import LatinHypercube  # noqa: E402

# ---------------------------------------------------------------- config
SEED = 42
N_U = 50
N_F = 100
E_BOUNDS = (2.5e4, 3.5e4)      # MPa, paper Table 1
NU_BOUNDS = (0.21, 0.39)       # paper Table 1
H_BOUND = 0.2                  # H_ij in [-0.2, 0.2], F = H + I, paper Sec. 5.1
HIDDEN = (175, 175)            # paper Table 2 baseline
LR = 1e-3
BATCH = 256
EPOCHS = 2000
TEST_FRAC = 0.10
DTYPE = torch.float64


def lhs(n, dim, seed):
    return LatinHypercube(d=dim, seed=seed).random(n)


def generate_doe(seed=SEED, n_u=N_U, n_f=N_F):
    """Generate the 50x100 DoE. Returns dict of numpy arrays (float64)."""
    rng = np.random.RandomState(seed)
    u_lhs = lhs(n_u, 2, seed)
    E_s = E_BOUNDS[0] + u_lhs[:, 0] * (E_BOUNDS[1] - E_BOUNDS[0])
    nu_s = NU_BOUNDS[0] + u_lhs[:, 1] * (NU_BOUNDS[1] - NU_BOUNDS[0])

    F_list, u_list, S_list = [], [], []
    n_skip = 0
    for i in range(n_u):
        h_lhs = lhs(n_f, 9, seed + 1000 + i)
        H = -H_BOUND + h_lhs * (2 * H_BOUND)
        for j in range(n_f):
            F = np.eye(3) + H[j].reshape(3, 3)
            if np.linalg.det(F) <= 1e-3:
                n_skip += 1
                continue
            S = neohooke.pk2_stress(F, E_s[i], nu_s[i])
            F_list.append(F)
            u_list.append([E_s[i], nu_s[i]])
            S_list.append(S)
    F = np.array(F_list)
    u = np.array(u_list)
    S = np.array(S_list)
    C = np.einsum("nij,nik->njk", F, F)
    I = invariants_numpy(C)
    return {
        "F": F, "C": C, "I": I, "u": u,
        "S": S, "S_voigt": voigt6(S),
        "seed": seed, "n_u": n_u, "n_f": n_f, "n_skipped": n_skip,
    }


def train_test_split(doe, test_frac=TEST_FRAC, seed=SEED):
    n = doe["I"].shape[0]
    rng = np.random.RandomState(seed + 1)
    idx = rng.permutation(n)
    n_test = int(n * test_frac)
    te, tr = idx[:n_test], idx[n_test:]
    return tr, te


def fit_scaler(X):
    lo, hi = X.min(axis=0), X.max(axis=0)
    c = 0.5 * (hi + lo)
    s = 0.5 * (hi - lo)
    s[s == 0.0] = 1.0
    return c, s


def rel_l2(S_pred, S_ref):
    """Relative L2 (Frobenius) error over a set, in physical units."""
    num = np.linalg.norm((S_pred - S_ref).reshape(len(S_ref), -1), axis=1)
    den = np.linalg.norm(S_ref.reshape(len(S_ref), -1), axis=1)
    den[den == 0.0] = 1.0
    return float(np.sqrt(np.sum(num ** 2) / np.sum(den ** 2)))


def train_model(doe, tr, te, epochs=EPOCHS, lr=LR, batch=BATCH,
                hidden=HIDDEN, seed=SEED, log_every=200, verbose=True):
    torch.manual_seed(seed)
    np.random.seed(seed)

    X = np.hstack([doe["I"], doe["u"]])          # (N,5) raw
    Y = doe["S_voigt"]                            # (N,6) MPa
    C_all = doe["C"]

    c_in, s_in = fit_scaler(X[tr])
    y_std = Y[tr].std(axis=0)
    y_std[y_std == 0.0] = 1.0

    model = PANN(u_dim=2, hidden=hidden)
    model.set_scaler(c_in, s_in)
    model.train()

    Ct_tr = torch.as_tensor(C_all[tr], dtype=DTYPE)
    ut_tr = torch.as_tensor(doe["u"][tr], dtype=DTYPE)
    Yt_tr = torch.as_tensor(Y[tr] / y_std, dtype=DTYPE)

    opt = torch.optim.Adam(model.parameters(), lr=lr)
    n_tr = len(tr)
    history = []
    t0 = time.time()
    for ep in range(1, epochs + 1):
        perm = torch.randperm(n_tr, generator=torch.Generator().manual_seed(seed + ep))
        tot, nb = 0.0, 0
        for b in range(0, n_tr, batch):
            idx = perm[b:b + batch]
            opt.zero_grad()
            S_pred = model.batch_stress_torch(Ct_tr[idx], ut_tr[idx])
            Sp = torch.stack([S_pred[:, 0, 0], S_pred[:, 1, 1], S_pred[:, 2, 2],
                              S_pred[:, 0, 1], S_pred[:, 0, 2], S_pred[:, 1, 2]], dim=1)
            loss = torch.mean((Sp / torch.as_tensor(y_std, dtype=DTYPE) - Yt_tr[idx]) ** 2)
            loss.backward()
            opt.step()
            tot += loss.item() * len(idx)
            nb += len(idx)
        mse = tot / nb
        history.append(mse)
        if verbose and (ep % log_every == 0 or ep == epochs):
            print(f"epoch {ep:5d}/{epochs}  train_MSE(normalized)={mse:.6e}", flush=True)
    train_time = time.time() - t0

    # ---- evaluation in physical units ----
    model.eval()
    with torch.no_grad():
        S_pred_te = model.stress(doe["C"][te], doe["u"][te])
        S_pred_tr = model.stress(doe["C"][tr], doe["u"][tr])
    metrics = {
        "seed": seed,
        "n_train": int(len(tr)), "n_test": int(len(te)),
        "n_doe": int(doe["I"].shape[0]),
        "hidden": list(hidden), "lr": lr, "batch": batch, "epochs": epochs,
        "train_time_s": round(train_time, 1),
        "train_loss_tail": float(history[-1]),
        "test_rel_l2": rel_l2(S_pred_te, doe["S"][te]),
        "train_rel_l2": rel_l2(S_pred_tr, doe["S"][tr]),
    }
    return model, history, metrics, (c_in, s_in, y_std)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    outdir = args.outdir
    if outdir is None:
        # for_worker lives in the MAIN checkout; if ROOT is a worktree
        # (<main>/.worktrees/<task>/<w>), go 3 levels up to find main.
        parts = os.path.abspath(ROOT).split(os.sep)
        if ".worktrees" in parts:
            main_root = os.sep.join(parts[:parts.index(".worktrees")])
        else:
            main_root = os.path.abspath(ROOT)
        outdir = os.path.join(main_root, "for_worker", "T04", "w1")
    os.makedirs(outdir, exist_ok=True)

    print(f"[T04] generating DoE (seed={args.seed}) ...", flush=True)
    doe = generate_doe(seed=args.seed)
    print(f"[T04] DoE: {doe['I'].shape[0]} points "
          f"({doe['n_u']} U x {doe['n_f']} F, skipped={doe['n_skipped']})", flush=True)
    np.savez(os.path.join(outdir, "doe.npz"),
             **{k: v for k, v in doe.items() if isinstance(v, np.ndarray)})

    tr, te = train_test_split(doe, seed=args.seed)
    print(f"[T04] training {args.epochs} epochs ...", flush=True)
    model, history, metrics, scaler = train_model(
        doe, tr, te, epochs=args.epochs, seed=args.seed)

    model.save(os.path.join(outdir, "pann.pt"))
    np.savez(os.path.join(outdir, "loss_history.npz"),
             loss=np.array(history))
    np.savez(os.path.join(outdir, "scaler.npz"),
             c_in=scaler[0], s_in=scaler[1], y_std=scaler[2])
    with open(os.path.join(outdir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print("[T04] metrics:", json.dumps(metrics, indent=2))
    print(f"[T04] artifacts in {outdir}")


if __name__ == "__main__":
    main()
