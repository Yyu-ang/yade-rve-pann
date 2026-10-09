"""T09 3D full-run driver: MC over the 3D plate-with-hole macro BVP.

Methodology mirrors ``for_worker/T08/w1/run_full.py`` (2D):
- paper MC rule: N0 samples, then +dN until q99 changes < 0.5% over the
  last 5 evaluations (N_CAP safety cap);
- common RNG: ref and PANN runs share pre-generated (Xi_E, Xi_nu, Yv);
- crash safety: per-batch checkpoints + intra-batch every --intra-ckpt
  samples; existing final .npz is skipped, never recomputed.

Run from the worktree root, in background::

    nohup <venv>/bin/python 3d/run_3d.py --mu 2.8e4 --mu 3.2e4 \\
        --constitutive both --pann-ckpt ~/workspace/yade-rve-pann/for_worker/T04b/w1/pann_v2.pt \\
        >> 3d/run_3d.log 2>&1 &

See 3d/README.md for the full user-machine guide.
"""

import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # worktree root: provides macro/, surrogate/
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import torch
torch.set_num_threads(2)

from macro3d import mesh3d, kl3d, uq3d
from macro3d.mesh3d import element_centroids

DEFAULT_CKPT = os.path.expanduser(
    "~/workspace/yade-rve-pann/for_worker/T04b/w1/pann_v2.pt")

_G = {}


def _init(pann_ckpt, mesh, streams, mu, t, kl_h, kl_nz, centroids):
    import torch as _torch
    _torch.set_num_threads(1)
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    from surrogate.pann import PANN as _PANN
    _G["mesh"] = mesh
    _G["streams"] = streams
    _G["centroids"] = centroids
    _G["E_rf"], _G["nu_rf"] = uq3d.build_fields(mu, t=t, kl_h=kl_h,
                                               kl_nz=kl_nz)
    _G["model"] = _PANN.load(pann_ckpt)
    _G["model"].eval()


def _one(args):
    i, constitutive = args
    from macro3d import uq3d as _uq
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
               mu, constitutive, seed, mesh_desc):
    parts = list(sc_list)
    if batch_prefix is not None:
        parts.append(np.asarray(batch_prefix))
    arr = np.concatenate(parts) if parts else np.empty(0)
    np.savez(ckpt_file, sigma_char=arr, q99_hist=np.array(q_hist),
             n_fail=n_fail, n_fallback=n_fallback, mu=mu,
             constitutive=constitutive, seed=seed, mesh_desc=mesh_desc)


def run_3d(mu, constitutive, args, mesh, streams, centroids, mesh_desc):
    from concurrent.futures import ProcessPoolExecutor
    tag = f"{args.tag}_mu{mu:.1e}_{constitutive}"
    ckpt_file = os.path.join(args.outdir, f"{tag}_checkpoint.npz")
    sc_list, q_hist, n_fail, n_fallback = [], [], 0, 0
    n_done = 0
    if os.path.exists(ckpt_file):
        d = np.load(ckpt_file, allow_pickle=True)
        sc_list = [d["sigma_char"]]
        q_hist = list(d["q99_hist"])
        n_fail, n_fallback = int(d["n_fail"]), int(d["n_fallback"])
        n_done = len(sc_list[0])
        print(f"[3d] {tag}: resuming at N={n_done}", flush=True)
    print(f"[3d] {tag}: MC start (N0={args.n0}, dN={args.dn}) ...", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(
            max_workers=args.workers, initializer=_init,
            initargs=(args.pann_ckpt, mesh, streams, mu, args.thickness,
                      args.kl_h, args.kl_nz, centroids)) as ex:
        while True:
            n_target = args.n0 if n_done < args.n0 else n_done + args.dn
            n_target = min(n_target, args.ncap)
            idx = [(i, constitutive) for i in range(n_done, n_target)]
            batch = np.full(len(idx), np.nan)
            n_in_batch = 0
            for i, s, fb, err in ex.map(_one, idx, chunksize=10):
                batch[i - n_done] = s
                n_in_batch += 1
                n_fallback += fb
                if err:
                    n_fail += 1
                if n_in_batch % args.intra_ckpt == 0:
                    _save_ckpt(ckpt_file, sc_list, batch[:n_in_batch],
                               q_hist, n_fail, n_fallback, mu, constitutive,
                               args.seed, mesh_desc)
            sc_list.append(batch)
            n_done = n_target
            arr = np.concatenate(sc_list)
            ok = np.isfinite(arr)
            q = float(np.quantile(arr[ok], 0.99))
            q_hist.append(q)
            _save_ckpt(ckpt_file, sc_list, None, q_hist, n_fail, n_fallback,
                       mu, constitutive, args.seed, mesh_desc)
            print(f"  [3d] {tag}: N={ok.sum()} q99={q:.2f} MPa "
                  f"(fail={n_fail}) {time.time()-t0:.0f}s", flush=True)
            if len(q_hist) >= 6:
                rel = max(abs(q_hist[-1] - q_hist[-1 - j]) / abs(q_hist[-1])
                           for j in range(1, 6))
                if rel < args.q99_tol:
                    print(f"  [3d] {tag}: STOPPING RULE MET "
                          f"(max 5-step rel change {rel:.4%})", flush=True)
                    break
            if n_done >= args.ncap:
                print(f"  [3d] {tag}: N_CAP reached", flush=True)
                break
    arr = np.concatenate(sc_list)
    np.savez(os.path.join(args.outdir, f"{tag}.npz"), sigma_char=arr,
             q99=np.array(q_hist), mu=mu, constitutive=constitutive,
             seed=args.seed, mesh_desc=mesh_desc)
    return arr, q_hist, n_fail, n_fallback


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="T09 3D macro UQ full run")
    p.add_argument("--mu", action="append", type=float, default=None,
                   help="interval parameter mu_E^i [MPa] (repeatable; "
                        "default: 2.8e4 3.2e4)")
    p.add_argument("--constitutive", choices=["ref", "pann", "both"],
                   default="both")
    p.add_argument("--n0", type=int, default=10000)
    p.add_argument("--dn", type=int, default=2000)
    p.add_argument("--ncap", type=int, default=40000)
    p.add_argument("--q99-tol", type=float, default=0.005)
    p.add_argument("--seed", type=int, default=20261008)
    p.add_argument("--theta", type=int, default=32, help="angular divisions")
    p.add_argument("--nr", type=int, default=6, help="radial layers")
    p.add_argument("--nz", type=int, default=4, help="through-thickness layers")
    p.add_argument("--thickness", type=float, default=1.0)
    p.add_argument("--kl-h", type=float, default=0.5, help="KL grid spacing")
    p.add_argument("--kl-nz", type=int, default=3, help="KL grid z layers")
    p.add_argument("--pann-ckpt", default=DEFAULT_CKPT)
    p.add_argument("--outdir", default=os.path.join(HERE, "output"))
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--intra-ckpt", type=int, default=500)
    p.add_argument("--tag", default="full3d")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    os.makedirs(args.outdir, exist_ok=True)
    assert os.path.exists(args.pann_ckpt), f"PANN ckpt missing: {args.pann_ckpt}"
    mesh = mesh3d.plate_with_hole_3d(n_theta=args.theta, n_r=args.nr,
                                    n_z=args.nz, t=args.thickness)
    centroids = element_centroids(mesh)
    mesh_desc = (f"theta={args.theta} nr={args.nr} nz={args.nz} "
                 f"t={args.thickness} hex={mesh['n_hex']}")
    print(f"[3d] mesh: {mesh_desc}, min_detJ={mesh['min_detJ']:.3e}")
    E_probe, nu_probe = uq3d.build_fields(3.0e4, t=args.thickness,
                                          kl_h=args.kl_h, kl_nz=args.kl_nz)
    kl3d.report(E_probe, nu_probe, n_cap=args.ncap)
    streams = uq3d.gen_random_streams(args.seed, args.ncap,
                                      E_probe.n_modes, nu_probe.n_modes)
    print("[3d] DOD common-RNG spot check ...")
    nmax = streams["n_max"]
    spots = sorted({0, 1, nmax // 4, nmax // 2, nmax - 1})
    assert uq3d.verify_common_rng(
        streams, E_probe, nu_probe, centroids, spots), "CRN FAILED"
    print("[3d] CRN PASS")
    consts = (["ref", "pann"] if args.constitutive == "both"
              else [args.constitutive])
    mus = args.mu if args.mu else [2.8e4, 3.2e4]
    summary = {}
    for mu in mus:
        for const in consts:
            tag = f"{args.tag}_mu{mu:.1e}_{const}"
            final_npz = os.path.join(args.outdir, f"{tag}.npz")
            if os.path.exists(final_npz):
                d = np.load(final_npz, allow_pickle=True)
                arr = d["sigma_char"]
                ok = np.isfinite(arr)
                q = float(np.quantile(arr[ok], 0.99))
                print(f"[3d] {tag}: SKIP (final exists), N={ok.sum()} "
                      f"q99={q:.2f} MPa", flush=True)
                summary[(mu, const)] = (q, ok.sum())
                continue
            arr, q_hist, n_fail, n_fb = run_3d(mu, const, args, mesh,
                                               streams, centroids, mesh_desc)
            ok = np.isfinite(arr)
            summary[(mu, const)] = (float(np.quantile(arr[ok], 0.99)),
                                    ok.sum())
    if "ref" in consts and "pann" in consts:
        print("\n[3d] SUMMARY")
        for mu in mus:
            qr, Nqr = summary[(mu, "ref")]
            qp, Nqp = summary[(mu, "pann")]
            print(f"  mu={mu:.1e}: ref q99={qr:.2f} (N={Nqr})  "
                  f"pann q99={qp:.2f} (N={Nqp})  rel err={(qp-qr)/qr*100:+.3f}%")
    print("[3d] DONE")


if __name__ == "__main__":
    main()
