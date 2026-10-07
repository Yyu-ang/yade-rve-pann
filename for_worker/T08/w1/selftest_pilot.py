"""T08 DOD7 self-test (pilot part). Prints ALL CHECKS PASSED on success.

Checks:
  1. 6 pilot npz files exist, each with 2000 finite sigma_char samples
  2. q99 values finite and positive; monotonic in mu for ref and pann
  3. PANN-vs-ref q99 rel err reported (no threshold in pilot)
  4. checkpoint sha256 matches the T04b original (not retrained/modified)
  5. preliminary p-box PNG + CSV exist in figures/T08/

Run:  python for_worker/T08/w1/selftest_pilot.py   (from worktree root)
"""

import hashlib
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

WORKDIR = os.path.join(ROOT, "for_worker", "T08", "w1")
FIGDIR = os.path.join(ROOT, "figures", "T08")
MUS = [2.8e4, 3.0e4, 3.2e4]
CKPT_ORIG = "/home/hatch/workspace/yade-rve-pann/for_worker/T04b/w1/pann_v2.pt"

ok = True


def check(cond, name, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")
    ok &= bool(cond)
    return cond


def main():
    # 1. files + sample counts
    q99 = {}
    for mu in MUS:
        for const in ["ref", "pann"]:
            tag = f"pilot_mu{mu:.1e}_{const}"
            p = os.path.join(WORKDIR, f"{tag}.npz")
            if not check(os.path.exists(p), f"{tag} exists"):
                continue
            d = np.load(p, allow_pickle=True)
            sc = d["sigma_char"]
            check(sc.shape == (2000,) and np.isfinite(sc).all(),
                  f"{tag} 2000 finite samples",
                  f"n={np.isfinite(sc).sum()}")
            q = float(d["q99"])
            check(np.isfinite(q) and q > 0, f"{tag} q99 finite", f"{q:.2f}")
            q99[(mu, const)] = q
    # 2. monotonicity
    if len(q99) == 6:
        qr = [q99[(mu, "ref")] for mu in MUS]
        qp = [q99[(mu, "pann")] for mu in MUS]
        check(all(b >= a for a, b in zip(qr, qr[1:])),
              "ref q99 monotonic in mu")
        check(all(b >= a for a, b in zip(qp, qp[1:])),
              "pann q99 monotonic in mu")
        for mu in MUS:
            r, p_ = q99[(mu, "ref")], q99[(mu, "pann")]
            print(f"    mu={mu:.1e}: ref={r:.2f} pann={p_:.2f} "
                  f"rel={(p_-r)/r*100:+.3f}%")
    # 3. checkpoint integrity
    mine = os.path.join(WORKDIR, "pann_v2.pt")
    h0 = hashlib.sha256(open(CKPT_ORIG, "rb").read()).hexdigest()
    h1 = hashlib.sha256(open(mine, "rb").read()).hexdigest()
    check(h0 == h1, "checkpoint unmodified (sha256 match)")
    # 4. p-box artifacts
    check(os.path.exists(os.path.join(FIGDIR, "fig7_analog_pilot.png")),
          "preliminary p-box PNG exists")
    check(os.path.exists(os.path.join(FIGDIR, "fig7_analog_pilot.csv")),
          "preliminary p-box CSV exists")
    print("ALL CHECKS PASSED" if ok else "CHECKS FAILED")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
