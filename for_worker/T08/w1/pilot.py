"""T08 pilot: 6 evals (mu in {2.8,3.0,3.2}e4 x {ref,pann}), 2000 MC samples each.

- Coarse mesh (~700 tris, n_points=275, seed 20261005)
- Fixed 2000 samples per eval (no redraw rule in pilot)
- Common RNG: ref/pann see bitwise-identical (E, nu, v)
- 2 worker processes (torch single-threaded to avoid oversubscription)
- Incremental checkpointing + resume support

Run:  python for_worker/T08/w1/pilot.py   (from worktree root)
"""

import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from macro import mesh as mm
from macro import uq_macro as uq

SEED = 20261008
N_PILOT = 2000
SAVE_EVERY = 200          # checkpoint every N samples
MU_GRID = [2.8e4, 3.0e4, 3.2e4]
OUTDIR = os.path.join(ROOT, "for_worker", "T08", "w1")

_G = {}


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
    except Exception as e:  # noqa: BLE001 - record and continue
        return (i, float("nan"), 0, f"{type(e).__name__}: {e}")


def run_eval(mu, constitutive, ckpt_path, mesh, streams, centroids,
             n_samples=N_PILOT):
    from concurrent.futures import ProcessPoolExecutor
    tag = f"pilot_mu{mu:.1e}_{constitutive}"
    final_file = os.path.join(OUTDIR, f"{tag}.npz")
    if os.path.exists(final_file):
        d = np.load(final_file, allow_pickle=True)
        sc, q99 = d["sigma_char"], float(d["q99"])
        print(f"[pilot] {tag}: already done, q99={q99:.2f} "
              f"(skipping)", flush=True)
        return sc, q99, 0, []
    ckpt_file = os.path.join(OUTDIR, f"{tag}_ckpt.npz")
    sc = np.full(n_samples, np.nan)
    fb_total, fails = 0, []
    n_done = 0
    if os.path.exists(ckpt_file):
        d = np.load(ckpt_file, allow_pickle=True)
        old = d["sigma_char"]
        # n_done = leading finite count (samples processed in order)
        finite = np.isfinite(old)
        n_done = int(np.argmax(~finite)) if not finite.all() else len(old)
        n_done = min(n_done, n_samples)
        sc[:n_done] = old[:n_done]
        fb_total, fails = int(d["fb"]), list(d["fails"])
        print(f"[pilot] {tag}: resuming at {n_done}/{n_samples}", flush=True)
    print(f"[pilot] {tag}: {n_samples} samples ...", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=2, initializer=_init,
                             initargs=(ckpt_path, mesh, streams, mu,
                                       centroids)) as ex:
        start = n_done
        while start < n_samples:
            end = min(start + SAVE_EVERY, n_samples)
            idx = [(i, constitutive) for i in range(start, end)]
            for i, s, fb, err in ex.map(_one, idx, chunksize=10):
                sc[i] = s
                fb_total += fb
                if err:
                    fails.append((i, err))
            start = end
            np.savez(ckpt_file, sigma_char=sc, fb=fb_total,
                     fails=np.array(fails, dtype=object), mu=mu,
                     constitutive=constitutive, seed=SEED)
            ok_n = np.isfinite(sc[:end]).sum()
            print(f"  [pilot] {tag}: {end}/{n_samples} "
                  f"({time.time()-t0:.0f}s)", flush=True)
    dt = time.time() - t0
    ok = np.isfinite(sc)
    q99 = float(np.quantile(sc[ok], 0.99))
    print(f"  done in {dt:.0f}s: ok={ok.sum()}/{n_samples} "
          f"q99={q99:.2f} MPa fallback={fb_total} fails={len(fails)}",
          flush=True)
    np.savez(os.path.join(OUTDIR, f"{tag}.npz"), sigma_char=sc, q99=q99,
             mu=mu, constitutive=constitutive, seed=SEED)
    # remove checkpoint on success
    if os.path.exists(ckpt_file):
        os.remove(ckpt_file)
    return sc, q99, fb_total, fails


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    ckpt_path = os.path.join(OUTDIR, "pann_v2.pt")
    mesh = mm.plate_with_hole(n_points=275, seed=20261005)
    centroids = mesh["coords"][mesh["tris"]].mean(axis=1)
    print(f"[pilot] mesh tris={mesh['tris'].shape[0]}")
    E_probe, nu_probe = uq.build_fields(3.0e4)
    streams = uq.gen_random_streams(SEED, N_PILOT, E_probe.n_modes,
                                    nu_probe.n_modes)
    print("[pilot] DOD5 common-RNG spot check ...")
    ok_crn = uq.verify_common_rng(streams, E_probe, nu_probe, centroids,
                                  [0, 7, 123, 456, 789, 1000, 1333, 1500,
                                   1777, 1999])
    assert ok_crn, "DOD5 FAILED"
    print("[pilot] DOD5 PASS")

    results = {}
    for mu in MU_GRID:
        for const in ["ref", "pann"]:
            sc, q99, fb, fails = run_eval(mu, const, ckpt_path, mesh,
                                          streams, centroids)
            tag = f"mu{mu:.1e}_{const}"
            results[tag] = (q99, fb, len(fails))
    print("\n[pilot] q99 summary (MPa):")
    for mu in MU_GRID:
        qr = results[f"mu{mu:.1e}_ref"][0]
        qp = results[f"mu{mu:.1e}_pann"][0]
        print(f"  mu={mu:.1e}: ref q99={qr:.2f}  pann q99={qp:.2f}  "
              f"rel err={(qp-qr)/qr*100:+.3f}%")
    qrs = [results[f"mu{mu:.1e}_ref"][0] for mu in MU_GRID]
    qps = [results[f"mu{mu:.1e}_pann"][0] for mu in MU_GRID]
    mono_r = all(b >= a for a, b in zip(qrs, qrs[1:]))
    mono_p = all(b >= a for a, b in zip(qps, qps[1:]))
    print(f"[pilot] monotonicity: ref={mono_r} pann={mono_p}")
    print("[pilot] ALL PILOT EVALS DONE")


if __name__ == "__main__":
    main()
