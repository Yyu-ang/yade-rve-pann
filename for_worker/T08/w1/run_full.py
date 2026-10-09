"""T08 full run: 4 runs (mu in {2.8,3.2}e4 x {ref,pann}) with paper MC rule.

- Mesh: n_points=275 (~846 tris). DEVIATION from dispatch "~2500 tris":
  measured 2496-tri PANN solve ~60-90 s -> 4e4 samples infeasible on 2 vCPU
  (356+ CPU-h). DOD3 is a RELATIVE PANN-vs-ref error on the SAME mesh, so
  discretization cancels to first order (T06 DOD3: coarse-vs-fine < 5%).
  Documented in handoff.
- MC rule (paper, literal): N0=1e4, then +2e3 until q99 changes < 0.5%
  within last 5 steps. Common RNG across all 4 runs.
- Incremental checkpointing per batch PLUS intra-batch every INTRA_CKPT
  samples (VM-restart hardening); 2 worker processes.
- Resume semantics (paper-literal): q99 is evaluated ONLY at canonical
  batch boundaries N0, N0+DN, ...  On resume the stored q99_hist is
  rebuilt from those sample prefixes (_canonical_q_hist) and the next
  batch runs to the next canonical boundary (_next_target), so restarts
  can no longer drift evaluation points off the paper rule.  Samples and
  their order are untouched (method-neutral).

Run:  python for_worker/T08/w1/run_full.py   (from worktree root, background)
"""

import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

import torch
torch.set_num_threads(2)

from macro import mesh as mm
from macro import uq_macro as uq

SEED = 20261008
N0 = 10000
DN = 2000
N_CAP = 40000
Q99_TOL = 0.005
MUS = [2.8e4, 3.2e4]
OUTDIR = os.path.join(ROOT, "for_worker", "T08", "w1")
# Intra-batch checkpoint cadence (samples). Pure crash-safety: does not
# change batch boundaries, the N0-first-batch rule, or any statistic.
INTRA_CKPT = 500

_G = {}


def _next_target(n_done):
    """Next canonical batch boundary strictly above n_done.

    Canonical boundaries are N0, N0+DN, N0+2*DN, ... (paper MC rule).
    The first batch is always exactly N0 samples, even when resuming
    from an intra-batch checkpoint (0 < n_done < N0).  Resuming mid-batch
    later (e.g. n_done=12500) continues to the next canonical boundary
    (14000), NOT n_done+DN (14500) -- otherwise q99 evaluation points
    drift off the paper rule after every restart.
    """
    if n_done < N0:
        return N0
    k = (n_done - N0 + DN) // DN  # smallest k with N0+k*DN > n_done
    return N0 + k * DN


def _canonical_q_hist(arr):
    """Rebuild the q99 history on canonical batch boundaries.

    Called on resume: past VM restarts may have cut batches at
    non-canonical N, so the stored q99_hist is discarded and rebuilt
    from the sample prefixes N0, N0+DN, ... <= len(arr).  The paper
    stopping rule is then always evaluated at canonical points.
    Method-neutral: samples and their order are untouched.
    """
    qh = []
    N = N0
    while N <= len(arr):
        sub = arr[:N]
        qh.append(float(np.quantile(sub[np.isfinite(sub)], 0.99)))
        N += DN
    return qh


def _init(ckpt_path, mesh_dict, streams, e_mean, centroids):
    import torch as _torch
    _torch.set_num_threads(1)   # avoid oversubscribing 2 vCPUs
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    from macro import kl_fields as _kl
    from surrogate.pann import PANN as _PANN
    _G["mesh"] = mesh_dict
    _G["streams"] = streams
    _G["centroids"] = centroids
    _G["E_rf"] = _kl.make_E_field(mu_E_i=e_mean)
    _G["nu_rf"] = _kl.make_nu_field()
    _G["model"] = _PANN.load(ckpt_path)
    _G["model"].eval()


def _one(args):
    i, constitutive = args
    from macro import uq_macro as _uq
    E_e, n_e, v = _uq.sample_inputs(i, _G["streams"], _G["E_rf"],
                                    _G["nu_rf"], _G["centroids"])
    kw = {"model": _G["model"]} if constitutive == "pann" else {}
    try:
        s, fb = _uq.solve_one(_G["mesh"], E_e, n_e, v, constitutive,
                              tol=1e-6, **kw)
        return (i, s, fb, "")
    except Exception as e:  # noqa: BLE001
        return (i, float("nan"), 0, f"{type(e).__name__}: {e}")


def _save_ckpt(ckpt_file, sc_list, batch_prefix, q_hist, n_fail, n_fallback,
               mu, constitutive):
    """Write checkpoint.

    batch_prefix is None at batch completion, or the filled prefix
    (batch[:n_in_batch]) of the in-progress batch for an intra-batch save.
    Format is identical in both cases, so resume logic is unchanged.
    """
    parts = list(sc_list)
    if batch_prefix is not None:
        parts.append(np.asarray(batch_prefix))
    arr = np.concatenate(parts) if parts else np.empty(0)
    np.savez(ckpt_file, sigma_char=arr, q99_hist=np.array(q_hist),
             n_fail=n_fail, n_fallback=n_fallback, mu=mu,
             constitutive=constitutive, seed=SEED)


def run_full(mu, constitutive, ckpt_path, mesh, streams, centroids):
    from concurrent.futures import ProcessPoolExecutor
    tag = f"full_mu{mu:.1e}_{constitutive}"
    ckpt_file = os.path.join(OUTDIR, f"{tag}_checkpoint.npz")
    # resume support
    sc_list, q_hist, n_fail, n_fallback = [], [], 0, 0
    n_done = 0
    if os.path.exists(ckpt_file):
        d = np.load(ckpt_file, allow_pickle=True)
        sc_list = [d["sigma_char"]]
        n_fail, n_fallback = int(d["n_fail"]), int(d["n_fallback"])
        n_done = len(sc_list[0])
        # Rebuild q_hist on canonical boundaries (see _canonical_q_hist):
        # a restart may have cut the previous batch at non-canonical N.
        q_hist = _canonical_q_hist(sc_list[0])
        print(f"[full] {tag}: resuming at N={n_done}, "
              f"canonical q_hist len={len(q_hist)}", flush=True)
    print(f"[full] {tag}: MC start (N0={N0}, dN={DN}) ...", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=2, initializer=_init,
                             initargs=(ckpt_path, mesh, streams, mu,
                                       centroids)) as ex:
        while True:
            # Canonical batch boundaries (paper rule); see _next_target.
            # The FIRST batch is exactly N0 samples, even when resuming
            # from an intra-batch checkpoint (0 < n_done < N0).
            n_target = min(_next_target(n_done), N_CAP)
            idx = [(i, constitutive) for i in range(n_done, n_target)]
            batch = np.full(len(idx), np.nan)
            n_in_batch = 0
            for i, s, fb, err in ex.map(_one, idx, chunksize=25):
                batch[i - n_done] = s
                n_in_batch += 1
                n_fallback += fb
                if err:
                    n_fail += 1
                if n_in_batch % INTRA_CKPT == 0:
                    _save_ckpt(ckpt_file, sc_list, batch[:n_in_batch],
                               q_hist, n_fail, n_fallback, mu, constitutive)
            sc_list.append(batch)
            n_done = n_target
            arr = np.concatenate(sc_list)
            ok = np.isfinite(arr)
            q = float(np.quantile(arr[ok], 0.99))
            q_hist.append(q)
            _save_ckpt(ckpt_file, sc_list, None, q_hist, n_fail, n_fallback,
                       mu, constitutive)
            print(f"  [full] {tag}: N={ok.sum()} q99={q:.2f} MPa "
                  f"(fail={n_fail}) {time.time()-t0:.0f}s", flush=True)
            if len(q_hist) >= 6:
                rel = max(abs(q_hist[-1] - q_hist[-1 - j]) / abs(q_hist[-1])
                           for j in range(1, 6))
                if rel < Q99_TOL:
                    print(f"  [full] {tag}: STOPPING RULE MET "
                          f"(max 5-step rel change {rel:.4%})", flush=True)
                    break
            if n_done >= N_CAP:
                print(f"  [full] {tag}: N_CAP reached", flush=True)
                break
    arr = np.concatenate(sc_list)
    np.savez(os.path.join(OUTDIR, f"{tag}.npz"), sigma_char=arr,
             q99=np.array(q_hist), mu=mu, constitutive=constitutive,
             seed=SEED)
    return arr, q_hist, n_fail, n_fallback


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    ckpt_path = os.path.join(OUTDIR, "pann_v2.pt")
    mesh = mm.plate_with_hole(n_points=275, seed=20261005)
    centroids = mesh["coords"][mesh["tris"]].mean(axis=1)
    print(f"[full] mesh tris={mesh['tris'].shape[0]} (846-tri, see deviation note)")
    E_probe, nu_probe = uq.build_fields(3.0e4)
    streams = uq.gen_random_streams(SEED, N_CAP, E_probe.n_modes,
                                    nu_probe.n_modes)
    print("[full] DOD5 common-RNG spot check ...")
    assert uq.verify_common_rng(
        streams, E_probe, nu_probe, centroids,
        [0, 999, 5000, 12345, 20000, 30000, 35000, 39999]), "DOD5 FAILED"
    print("[full] DOD5 PASS")
    summary = {}
    for mu in MUS:
        for const in ["ref", "pann"]:
            tag = f"full_mu{mu:.1e}_{const}"
            final_npz = os.path.join(OUTDIR, f"{tag}.npz")
            if os.path.exists(final_npz):
                d = np.load(final_npz, allow_pickle=True)
                arr = d["sigma_char"]
                q_hist = list(d["q99"])
                ok = np.isfinite(arr)
                print(f"[full] {tag}: SKIP (final exists), "
                      f"N={ok.sum()} q99={float(np.quantile(arr[ok],0.99)):.2f} MPa",
                      flush=True)
                summary[(mu, const)] = (float(np.quantile(arr[ok], 0.99)),
                                        ok.sum(), -1, -1, q_hist)
                continue
            arr, q_hist, n_fail, n_fb = run_full(mu, const, ckpt_path, mesh,
                                                 streams, centroids)
            ok = np.isfinite(arr)
            summary[(mu, const)] = (float(np.quantile(arr[ok], 0.99)),
                                    ok.sum(), n_fail, n_fb, q_hist)
    print("\n[full] SUMMARY")
    for mu in MUS:
        qr, Nqr, _, _, _ = summary[(mu, "ref")]
        qp, Nqp, _, _, _ = summary[(mu, "pann")]
        print(f"  mu={mu:.1e}: ref q99={qr:.2f} (N={Nqr})  "
              f"pann q99={qp:.2f} (N={Nqp})  rel err={(qp-qr)/qr*100:+.3f}%")
    print("[full] ALL FULL RUNS DONE")


if __name__ == "__main__":
    main()
