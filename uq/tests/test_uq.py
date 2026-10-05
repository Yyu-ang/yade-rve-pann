"""T05 self-test: material-point UQ demo DOD.

Runs the full demo (MC N=20000 + interval optimization), prints q99 and
interval bounds with analytic comparisons, and asserts every relative error
is < 3%. Exit code 0 on PASS.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from uq.material_uq import (  # noqa: E402
    load_model, mc_uq, interval_uq, print_report,
    analytic_s11, analytic_s11_scalar, pann_s11_batch,
    E_LO, E_HI, NU_LO, NU_HI, F_DEMO, MC_N, MC_SEED, CKPT,
)


def main():
    # --- preconditions ------------------------------------------------------
    assert os.path.isfile(CKPT), "missing checkpoint: %s" % CKPT
    model = load_model()

    # --- cross-check: vectorized analytic vs T03 pk2_stress ------------------
    rng = np.random.default_rng(7)
    E = rng.uniform(E_LO, E_HI, 20)
    nu = rng.uniform(NU_LO, NU_HI, 20)
    ref = np.array([analytic_s11_scalar(e, n) for e, n in zip(E, nu)])
    vec = analytic_s11(E, nu)
    err = np.max(np.abs(vec - ref) / np.abs(ref))
    print("[xcheck] vectorized analytic vs T03 pk2_stress: max rel err = %.3e"
          % err)
    assert err < 1e-12, "analytic vectorization mismatch"

    # --- PANN sanity at one point -------------------------------------------
    s1 = float(pann_s11_batch(model, np.array([3.0e4]),
                              np.array([0.30]))[0])
    s1r = analytic_s11_scalar(3.0e4, 0.30)
    print("[xcheck] PANN S11(E=3e4,nu=0.3) = %.4f vs analytic %.4f"
          % (s1, s1r))
    assert abs(s1 - s1r) / abs(s1r) < 0.05, "PANN far off at domain center"

    # --- DOD 1: MC -----------------------------------------------------------
    mc = mc_uq(model, n=MC_N, seed=MC_SEED)
    assert mc["n"] >= 20000
    assert E_LO <= 2.5e4 and E_HI <= 3.5e4  # domain guard (constants)

    # --- DOD 2: interval ------------------------------------------------------
    iv = interval_uq(model)

    # --- report + DOD 3% gates ------------------------------------------------
    ok = print_report(mc, iv)
    assert ok, "DOD failed: some relative error >= 3%"
    print("ALL UQ CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
