"""3D macro UQ pipeline (T09): Example I Fig. 7 analogue in 3D.

Two constitutive laws solve the SAME 3D plate-with-hole BVP:
  - "ref"  : paper Eq.(33) analytic (``macro3d.constitutive3d.ref_S``)
  - "pann" : T04b PANN checkpoint via ``make_pann_S`` (read-only)

Uncertainty: 3D KL fields (``macro3d.kl3d``) + shifted log-normal v.
Common random numbers: ref and PANN see identical (E, nu, v) inputs;
all randomness is pre-generated per run (Xi_E, Xi_nu, Yv).

MC stopping rule (paper, literal): N0 = 1e4, then +dN = 2e3 until q99
changes < 0.5% within the last 5 steps (N_CAP = 4e4 safety cap).

QoI: sigma_char = max over nodes of max |principal Cauchy stress|
(same definition as the 2D pipeline, paper Eq. 32).
"""

import time

import numpy as np

from . import kl3d
from . import solver3d as sv3
from . import constitutive3d as c3
from .mesh3d import element_centroids

SEED_RUN = 20261008
N0 = 10000
DN = 2000
Q99_TOL = 0.005
N_CAP = 40000
MU_BOUNDS = [2.8e4, 3.2e4]


def build_fields(mu_E_i, t=1.0, kl_h=0.5, kl_nz=3):
    E_rf = kl3d.make_E_field_3d(mu_E_i=mu_E_i, t=t, h=kl_h, n_z=kl_nz)
    nu_rf = kl3d.make_nu_field_3d(t=t, h=kl_h, n_z=kl_nz)
    return E_rf, nu_rf


def gen_random_streams(seed, n_max, nE, nNu):
    rng = np.random.default_rng(seed)
    return {
        "Xi_E": rng.standard_normal((n_max, nE)),
        "Xi_nu": rng.standard_normal((n_max, nNu)),
        "Yv": rng.normal(-0.12, 0.05, size=n_max),
        "seed": seed,
        "n_max": n_max,
    }


def sample_inputs(i, streams, E_rf, nu_rf, centroids):
    E_elem = E_rf.sample(streams["Xi_E"][i], centroids)
    nu_elem = nu_rf.sample(streams["Xi_nu"][i], centroids)
    v = -0.2 + np.exp(streams["Yv"][i])
    return E_elem, nu_elem, float(v)


def solve_one(mesh, E_elem, nu_elem, v, constitutive, model=None,
              n_steps=8, tol=1e-8):
    """One 3D macro BVP solve -> sigma_char. Retries once with finer steps."""
    if constitutive == "ref":
        kw = {}
    elif constitutive == "pann":
        kw = {"S_fn": c3.make_pann_S(model)}
    else:
        raise ValueError(constitutive)
    try:
        res = sv3.solve(mesh, E_elem, nu_elem, v_target=v,
                        n_steps=n_steps, tol=tol, **kw)
        return float(res["sigma_char"]), 0
    except (sv3._InvalidState, RuntimeError, ValueError):
        pass
    kw2 = dict(kw)
    res = sv3.solve(mesh, E_elem, nu_elem, v_target=v,
                    n_steps=2 * n_steps, tol=tol, **kw2)
    return float(res["sigma_char"]), 1


def verify_common_rng(streams, E_rf, nu_rf, centroids, idx_list):
    ok = True
    for i in idx_list:
        a = sample_inputs(i, streams, E_rf, nu_rf, centroids)
        b = sample_inputs(i, streams, E_rf, nu_rf, centroids)
        same = (a[0] == b[0]).all() and (a[1] == b[1]).all() and a[2] == b[2]
        ok &= bool(same)
        print(f"    [CRN] sample {i}: {'IDENTICAL' if same else 'MISMATCH'}")
    return ok


def mc_q99_serial(mesh, E_rf, nu_rf, streams, centroids, mu_E_i,
                  constitutive, model=None, n0=N0, dn=DN, n_cap=N_CAP,
                  verbose=True, solve_kw=None):
    """Serial MC with the paper's stopping rule (validation / tiny runs)."""
    solve_kw = solve_kw or {}
    sc, q_hist = [], []
    n_fail = n_fallback = 0
    t0 = time.time()
    n_done = 0
    while True:
        n_target = n0 if n_done == 0 else n_done + dn
        n_target = min(n_target, n_cap, streams["n_max"])
        for i in range(n_done, n_target):
            E_e, n_e, v = sample_inputs(i, streams, E_rf, nu_rf, centroids)
            try:
                s, fb = solve_one(mesh, E_e, n_e, v, constitutive,
                                  model=model, **solve_kw)
                sc.append(s)
                n_fallback += fb
            except (sv3._InvalidState, RuntimeError, ValueError):
                n_fail += 1
        n_done = n_target
        arr = np.array(sc)
        q = float(np.quantile(arr, 0.99))
        q_hist.append(q)
        if verbose:
            print(f"    [MC] N={len(arr)} q99={q:.2f} MPa "
                  f"(fail={n_fail}, fallback={n_fallback})", flush=True)
        if len(q_hist) >= 6:
            rel = max(abs(q_hist[-1] - q_hist[-1 - j]) / abs(q_hist[-1])
                       for j in range(1, 6))
            if rel < Q99_TOL:
                break
        if n_done >= min(n_cap, streams["n_max"]):
            break
    return {"sigma_char": np.array(sc), "q99_hist": q_hist,
            "N": len(sc), "n_fail": n_fail, "n_fallback": n_fallback,
            "seconds": time.time() - t0, "mu_E_i": mu_E_i,
            "constitutive": constitutive}
