"""T08 macro UQ pipeline: Example I (paper Sec. 5.1) -> Fig. 7 p-box analogue.

Two constitutive laws solve the SAME 2D plane-stress macro BVP (T06 solver):
  - "ref"  : paper Eq.(33) (analytic, ``macro.plane_stress``)
  - "pann" : T04b PANN checkpoint (``macro.pann_const``, read-only)

Uncertainty (T07 KL fields, paper Sec. 5.1):
  - E^iprf : KL field, marginal N(mu_E^i, 1e3^2) MPa, lcorr = 1 m
             (mu_E^i is the interval parameter, set by the caller)
  - nu^rf  : KL field, marginal N(0.3, 0.03^2), lcorr = 2 m
  - v      : scalar, V = -0.2 + exp(Y), Y ~ N(-0.12, 0.05^2)  [m]

Common random numbers: ref and PANN see bitwise-identical (E, nu, v)
inputs. All randomness is pre-generated per run (Xi_E, Xi_nu, Yv arrays).

MC stopping rule (paper, literal): start with N0 = 1e4 samples, evaluate
q99; then add dN = 2e3 samples until q99 does not change more than 0.5%
within the last 5 steps. q99 via numpy.quantile.

QoI: sigma_char = max over nodes of max |principal stress| (paper Eq. 32).

Seeds are fixed and recorded in the handoff.
"""

import os
import time

import numpy as np
import torch

from . import mesh as mm
from . import solver as sv
from . import kl_fields as kl
from . import pann_const as pc

SEED_RUN = 20261008     # master seed for the MC random streams
N0 = 10000              # paper: start with 1e4 samples
DN = 2000               # paper: redraw 2e3 samples
Q99_TOL = 0.005         # paper: q99 change < 0.5% within last 5 steps
N_CAP = 40000           # safety cap on total samples per run
MU_GRID = [2.8e4, 3.0e4, 3.2e4]   # interval parameter values (pilot)
MU_BOUNDS = [2.8e4, 3.2e4]        # interval endpoints (full)


def build_fields(mu_E_i):
    """KL field objects for E (mean=mu_E_i) and nu. Eigenstructure cached."""
    E_rf = kl.make_E_field(mu_E_i=mu_E_i)
    nu_rf = kl.make_nu_field()
    return E_rf, nu_rf


def gen_random_streams(seed, n_max, nE, nNu):
    """Pre-generate common random numbers for n_max MC samples.

    Returns dict with Xi_E (n_max, nE), Xi_nu (n_max, nNu), Yv (n_max,).
    """
    rng = np.random.default_rng(seed)
    return {
        "Xi_E": rng.standard_normal((n_max, nE)),
        "Xi_nu": rng.standard_normal((n_max, nNu)),
        "Yv": rng.normal(-0.12, 0.05, size=n_max),
        "seed": seed,
        "n_max": n_max,
    }


def sample_inputs(i, streams, E_rf, nu_rf, centroids):
    """Realize (E_elem, nu_elem, v) for MC sample i. E in MPa, v in m."""
    E_elem = E_rf.sample(streams["Xi_E"][i], centroids)
    nu_elem = nu_rf.sample(streams["Xi_nu"][i], centroids)
    v = -0.2 + np.exp(streams["Yv"][i])
    return E_elem, nu_elem, float(v)


def solve_one(mesh, E_elem, nu_elem, v, constitutive, model=None,
              n_steps=8, tol=1e-8):
    """One macro BVP solve -> sigma_char. Retries once with finer stepping.

    constitutive: "ref" or "pann".
    Returns (sigma_char, n_fallback) with n_fallback in {0, 1};
    raises RuntimeError if both attempts fail.
    """
    if constitutive == "ref":
        kw = {}
    elif constitutive == "pann":
        pc.clear_cache()
        kw = {"condense_fn": pc.make_condense_fn(model)}
    else:
        raise ValueError(constitutive)
    try:
        res = sv.solve(mesh, E_elem, nu_elem, v_target=v,
                       n_steps=n_steps, tol=tol, **kw)
        return float(res["sigma_char"]), 0
    except (sv._InvalidState, RuntimeError):
        pass
    # fallback: finer load stepping
    if constitutive == "pann":
        pc.clear_cache()
    res = sv.solve(mesh, E_elem, nu_elem, v_target=v,
                   n_steps=2 * n_steps, tol=tol, **kw)
    return float(res["sigma_char"]), 1


def mc_q99(mesh, E_rf, nu_rf, streams, centroids, mu_E_i, constitutive,
           model=None, n0=N0, dn=DN, n_cap=N_CAP, verbose=True,
           solve_kw=None):
    """Run the MC with the paper's stopping rule.

    Returns dict(sigma_char, q99_hist, N, n_fail, n_fallback, seconds).
    """
    solve_kw = solve_kw or {}
    sc = []            # sigma_char samples
    q_hist = []        # q99 after each evaluation step
    n_fail = 0
    n_fallback = 0
    t0 = time.time()
    n_done = 0
    step = 0
    while True:
        n_target = n0 if step == 0 else n_done + dn
        n_target = min(n_target, n_cap, streams["n_max"])
        for i in range(n_done, n_target):
            E_e, n_e, v = sample_inputs(i, streams, E_rf, nu_rf, centroids)
            try:
                s, fb = solve_one(mesh, E_e, n_e, v, constitutive,
                                  model=model, **solve_kw)
                sc.append(s)
                n_fallback += fb
            except (sv._InvalidState, RuntimeError):
                n_fail += 1
        n_done = n_target
        step += 1
        arr = np.array(sc)
        q = float(np.quantile(arr, 0.99))
        q_hist.append(q)
        if verbose:
            print(f"    [MC] N={len(arr)} q99={q:.2f} MPa "
                  f"(fail={n_fail}, fallback={n_fallback})", flush=True)
        # paper stopping rule: q99 change < 0.5% within the last 5 steps
        if len(q_hist) >= 6:
            rel = max(abs(q_hist[-1] - q_hist[-1 - j]) / abs(q_hist[-1])
                       for j in range(1, 6))
            if rel < Q99_TOL:
                break
        if n_done >= min(n_cap, streams["n_max"]):
            break
    return {
        "sigma_char": np.array(sc),
        "q99_hist": q_hist,
        "N": len(sc),
        "n_fail": n_fail,
        "n_fallback": n_fallback,
        "seconds": time.time() - t0,
        "mu_E_i": mu_E_i,
        "constitutive": constitutive,
    }


def verify_common_rng(streams, E_rf, nu_rf, centroids, idx_list):
    """DOD5: ref/PANN inputs bitwise identical for spot-checked samples."""
    ok = True
    for i in idx_list:
        a = sample_inputs(i, streams, E_rf, nu_rf, centroids)
        b = sample_inputs(i, streams, E_rf, nu_rf, centroids)
        same = (a[0] == b[0]).all() and (a[1] == b[1]).all() and a[2] == b[2]
        ok &= bool(same)
        print(f"    [CRN] sample {i}: {'IDENTICAL' if same else 'MISMATCH'}")
    return ok
