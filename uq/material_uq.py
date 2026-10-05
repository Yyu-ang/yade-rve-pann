"""Material-point polymorphic UQ demo -- v2 plan Phase 1A-4.

Propagates (E, nu) uncertainty through the T04-trained PANN surrogate to the
2nd Piola-Kirchhoff stress S at a fixed deformation state:

  1. Monte-Carlo (aleatory): E ~ U[2.5,3.5]e4 MPa, nu ~ U[0.21,0.39],
     fixed seed; S11 mean / std / q99, PANN vs analytic Eq.(33) reference.
  2. Interval optimization (epistemic): multi-start minimization/maximization
     of S11(E, nu) over the (E, nu) box, PANN vs analytic interval bounds.

SCOPE: material-point level ONLY. The paper's 0.1%/0.07% q99 errors belong
to the plate-with-hole macro BVP and are NOT claimed from this demo.

Conventions:
  - E in MPa, S in MPa (T03/T04 units).
  - (E, nu) never leave the PANN training domain [2.5,3.5]e4 x [0.21,0.39].
  - MC uses common random numbers: identical (E, nu) samples feed both the
    PANN and the analytic reference, so differences isolate surrogate error.
"""

import os

import numpy as np
import torch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from surrogate.pann import PANN  # noqa: E402
from examples.ex1_neohooke.neohooke import pk2_stress  # noqa: E402

# --- fixed demo configuration ------------------------------------------------
CKPT = "/home/hatch/workspace/yade-rve-pann/for_worker/T04b/w1/pann_v2.pt"

E_LO, E_HI = 2.5e4, 3.5e4          # MPa, training domain
NU_LO, NU_HI = 0.21, 0.39          # training domain

F_DEMO = np.diag([1.1, 1.0, 1.0])  # fixed deformation state (uniaxial)
C_DEMO = F_DEMO.T @ F_DEMO

MC_N = 20000
MC_SEED = 20261005

DTORCH = torch.float64


def load_model():
    """Load the T04 checkpoint (read-only); fail loudly if missing."""
    assert os.path.isfile(CKPT), "checkpoint not found: %s" % CKPT
    return PANN.load(CKPT)


# --- analytic Eq.(33) reference, vectorized ----------------------------------
def analytic_s11(E, nu, F=F_DEMO):
    """S11 per paper Eq.(33). E, nu: (N,) arrays -> (N,) array."""
    E = np.asarray(E, dtype=float)
    nu = np.asarray(nu, dtype=float)
    J = float(np.linalg.det(F))
    kappa = E / (3.0 * (1.0 - 2.0 * nu))
    eta = E / (2.0 * (1.0 + nu))
    C = F.T @ F
    Finv = np.linalg.inv(F)
    FinvT = Finv.T
    Jm23 = J ** (-2.0 / 3.0)
    Cbar_tr = Jm23 * np.trace(C)
    # P = kappa*lnJ*FinvT + eta*(Jm23*F - Cbar_tr/3*FinvT); S = Finv @ P
    P11 = kappa * np.log(J) * FinvT[0, 0] \
        + eta * (Jm23 * F[0, 0] - (Cbar_tr / 3.0) * FinvT[0, 0])
    P21 = kappa * np.log(J) * FinvT[1, 0] \
        + eta * (Jm23 * F[1, 0] - (Cbar_tr / 3.0) * FinvT[1, 0])
    P31 = kappa * np.log(J) * FinvT[2, 0] \
        + eta * (Jm23 * F[2, 0] - (Cbar_tr / 3.0) * FinvT[2, 0])
    # S11 = Finv[0,:] . P[:,0]
    return Finv[0, 0] * P11 + Finv[0, 1] * P21 + Finv[0, 2] * P31


def analytic_s11_scalar(E, nu, F=F_DEMO):
    """Scalar cross-check against T03's pk2_stress."""
    return float(pk2_stress(F, float(E), float(nu))[0, 0])


# --- PANN evaluation ----------------------------------------------------------
def pann_s11_batch(model, E, nu, F=F_DEMO, batch=4096):
    """S11 via PANN stress_F. E, nu: (N,) arrays -> (N,) array."""
    E = np.asarray(E, dtype=float).ravel()
    nu = np.asarray(nu, dtype=float).ravel()
    n = E.shape[0]
    u = np.stack([E, nu], axis=1)
    Fb = np.broadcast_to(F, (n, 3, 3)).copy()
    out = np.empty(n)
    for i in range(0, n, batch):
        S = model.stress_F(Fb[i:i + batch], u[i:i + batch])
        out[i:i + batch] = S[:, 0, 0]
    return out


def _pann_s11_torch(model, E_t, nu_t):
    """Torch-native S11(E, nu) with autograd to (E, nu).

    E_t, nu_t: (K,1) float64 tensors requiring grad. Returns (K,).
    """
    u = torch.cat([E_t, nu_t], dim=1)
    K = u.shape[0]
    Cc = torch.as_tensor(C_DEMO, dtype=DTORCH).expand(K, 3, 3).clone() \
        .detach().requires_grad_(True)
    psi = model._psi_of_C(Cc, u)
    (grad,) = torch.autograd.grad(psi.sum(), Cc, create_graph=False)
    return 2.0 * grad[:, 0, 0]


# --- 1. Monte-Carlo propagation ------------------------------------------------
def mc_uq(model, n=MC_N, seed=MC_SEED, F=F_DEMO):
    """MC UQ of S11 at fixed F. Returns dict with PANN/analytic stats."""
    rng = np.random.default_rng(seed)
    E = rng.uniform(E_LO, E_HI, n)
    nu = rng.uniform(NU_LO, NU_HI, n)
    s_pann = pann_s11_batch(model, E, nu, F)
    s_ref = analytic_s11(E, nu, F)

    def stats(s):
        return {"mean": float(np.mean(s)),
                "std": float(np.std(s)),
                "q99": float(np.quantile(s, 0.99))}

    out = {"pann": stats(s_pann), "analytic": stats(s_ref),
           "n": n, "seed": seed}
    out["rel_err"] = {k: abs(out["pann"][k] - out["analytic"][k])
                      / abs(out["analytic"][k])
                      for k in ("mean", "std", "q99")}
    return out


# --- 2. interval optimization ---------------------------------------------------
def interval_uq(model, n_starts=16, grid=160, F=F_DEMO):
    """Min/max of S11(E, nu) over the box.

    PANN: dense grid + torch L-BFGS polish from the best grid candidates.
    Analytic: dense grid + scipy L-BFGS-B polish (reference bounds).
    Returns dict with PANN/analytic (min, max) and relative errors.
    """
    from scipy.optimize import minimize

    # dense grid over the box
    Es = np.linspace(E_LO, E_HI, grid)
    NUs = np.linspace(NU_LO, NU_HI, grid)
    EE, NN = np.meshgrid(Es, NUs)
    Eg, Ng = EE.ravel(), NN.ravel()
    s_pann_g = pann_s11_batch(model, Eg, Ng, F)
    s_ref_g = analytic_s11(Eg, Ng, F)

    def polish_pann(starts, find_max):
        best = None
        for e0, n0 in starts:
            x = torch.tensor([[(e0 - E_LO) / (E_HI - E_LO),
                               (n0 - NU_LO) / (NU_HI - NU_LO)]],
                             dtype=DTORCH, requires_grad=True)
            opt = torch.optim.LBFGS([x], max_iter=40,
                                    line_search_fn="strong_wolfe")

            def closure():
                opt.zero_grad()
                E_t = E_LO + x[:, 0:1] * (E_HI - E_LO)
                nu_t = NU_LO + x[:, 1:2] * (NU_HI - NU_LO)
                s = _pann_s11_torch(model, E_t, nu_t)
                loss = -s.sum() if find_max else s.sum()
                loss.backward()
                return loss

            try:
                opt.step(closure)
            except Exception:
                pass
            with torch.no_grad():
                xc = x.clamp(0.0, 1.0)
                E_v = float(E_LO + xc[0, 0].item() * (E_HI - E_LO))
                nu_v = float(NU_LO + xc[0, 1].item() * (NU_HI - NU_LO))
                val = float(model.stress_F(
                    F_DEMO, np.array([E_v, nu_v]))[0, 0])
            if best is None or (find_max and val > best) \
                    or (not find_max and val < best):
                best = val
        return best

    def polish_ref(starts, find_max):
        def f(xn):
            E = E_LO + xn[0] * (E_HI - E_LO)
            nu = NU_LO + xn[1] * (NU_HI - NU_LO)
            v = analytic_s11_scalar(E, nu, F)
            return -v if find_max else v

        best = None
        for e0, n0 in starts:
            x0 = np.array([(e0 - E_LO) / (E_HI - E_LO),
                           (n0 - NU_LO) / (NU_HI - NU_LO)])
            r = minimize(f, x0, method="L-BFGS-B",
                         bounds=[(0, 1), (0, 1)],
                         options={"maxiter": 200})
            val = -r.fun if find_max else r.fun
            if best is None or (find_max and val > best) \
                    or (not find_max and val < best):
                best = val
        return best

    idx_min = np.argsort(s_pann_g)[:n_starts]
    idx_max = np.argsort(s_pann_g)[-n_starts:]
    starts_min = list(zip(Eg[idx_min], Ng[idx_min]))
    starts_max = list(zip(Eg[idx_max], Ng[idx_max]))

    pann_min = min(float(s_pann_g.min()), polish_pann(starts_min, False))
    pann_max = max(float(s_pann_g.max()), polish_pann(starts_max, True))
    ref_min = min(float(s_ref_g.min()), polish_ref(starts_min, False))
    ref_max = max(float(s_ref_g.max()), polish_ref(starts_max, True))

    return {
        "pann": {"min": pann_min, "max": pann_max},
        "analytic": {"min": ref_min, "max": ref_max},
        "rel_err": {
            "min": abs(pann_min - ref_min) / abs(ref_min),
            "max": abs(pann_max - ref_max) / abs(ref_max),
        },
    }


def run_demo():
    model = load_model()
    mc = mc_uq(model)
    iv = interval_uq(model)
    return mc, iv


def print_report(mc, iv):
    print("=" * 64)
    print("T05 MATERIAL-POINT UQ DEMO (F = diag(1.1,1,1), fixed)")
    print("E in [2.5,3.5]e4 MPa, nu in [0.21,0.39]  (PANN training domain)")
    print("=" * 64)
    print("[MC] N=%d seed=%d (common random numbers)" % (mc["n"], mc["seed"]))
    for k in ("mean", "std", "q99"):
        print("  S11 %-4s : PANN=%12.4f  analytic=%12.4f  rel.err=%.4f%%"
              % (k, mc["pann"][k], mc["analytic"][k],
                 100.0 * mc["rel_err"][k]))
    print("[interval] multi-start min/max of S11(E,nu)")
    for k in ("min", "max"):
        print("  S11 %-3s : PANN=%12.4f  analytic=%12.4f  rel.err=%.4f%%"
              % (k, iv["pann"][k], iv["analytic"][k],
                 100.0 * iv["rel_err"][k]))
    ok = all(v < 0.03 for v in mc["rel_err"].values()) \
        and all(v < 0.03 for v in iv["rel_err"].values())
    print("DOD (<3%% all): %s" % ("PASS" if ok else "FAIL"))
    print("NOTE: material-point level only; paper's macro-BVP q99 not claimed.")
    return ok


if __name__ == "__main__":
    mc, iv = run_demo()
    ok = print_report(mc, iv)
    raise SystemExit(0 if ok else 1)
