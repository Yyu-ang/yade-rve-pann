"""T04b DOD(3): re-verify the T05 interval-max with the new pann_v2.pt.

Reuses the T05-verified method chain (uq.material_uq.interval_uq:
160x160 grid + torch L-BFGS multi-start polish for PANN,
grid + scipy L-BFGS-B for the analytic reference), only swapping the
checkpoint. Also reports MC stats for information.

DOD: interval max relative error < 3%.
"""

import os
import sys

T05W = "/home/hatch/workspace/yade-rve-pann/.worktrees/T05/w1"
sys.path.insert(0, T05W)

import uq.material_uq as mu  # noqa: E402

CKPT_V2 = "/home/hatch/workspace/yade-rve-pann/for_worker/T04b/w1/pann_v2.pt"


def main():
    assert os.path.isfile(CKPT_V2), "missing v2 checkpoint: %s" % CKPT_V2
    mu.CKPT = CKPT_V2
    model = mu.load_model()
    print("[reverify] loaded pann_v2.pt", flush=True)

    print("[reverify] running interval optimization ...", flush=True)
    iv = mu.interval_uq(model)
    print("[reverify] interval min: PANN %.4f vs analytic %.4f, rel=%.4f%%"
          % (iv["pann"]["min"], iv["analytic"]["min"],
             100 * iv["rel_err"]["min"]))
    print("[reverify] interval max: PANN %.4f vs analytic %.4f, rel=%.4f%%"
          % (iv["pann"]["max"], iv["analytic"]["max"],
             100 * iv["rel_err"]["max"]))
    assert iv["rel_err"]["max"] < 0.03, \
        "DOD(3) FAILED: interval max rel err %.4f%% >= 3%" \
        % (100 * iv["rel_err"]["max"])
    assert iv["rel_err"]["min"] < 0.03, \
        "interval min regressed: %.4f%%" % (100 * iv["rel_err"]["min"])

    print("[reverify] running MC (informational) ...", flush=True)
    mc = mu.mc_uq(model)
    for k in ("mean", "std", "q99"):
        print("[reverify] MC %s: PANN %.4f vs analytic %.4f, rel=%.4f%%"
              % (k, mc["pann"][k], mc["analytic"][k],
                 100 * mc["rel_err"][k]))

    print("[reverify] DOD(3) PASSED: interval max rel err %.4f%% < 3%%"
          % (100 * iv["rel_err"]["max"]))


if __name__ == "__main__":
    main()
