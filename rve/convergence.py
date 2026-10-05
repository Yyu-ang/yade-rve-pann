"""RVE representativeness test — paper §4.1, §5.2, Fig. 10.

For a FIXED descriptor vector u: build several independent realizations
(different seeds), probe each at a fixed deformation state, and compute

    Delta = std(||S||) / mean(||S||)   (in %)

The RVE is accepted if Delta <= 0.5%.

Definitions (visually verified from the paper PDF p.14; see
docs/reproduction_plan_review_2026-10-05.md §1.2):
the typeset formula is inconsistent with Fig. 10(b) and the <=0.5% criterion,
so the figure-consistent coefficient of variation above is the operative
definition. Recorded as a known transcription risk.

P0-5 separation (paper §5.2): the realization samples used HERE
("RVE representativeness samples") are a different sampling stage from the
1000 LHS points drawn in the mechanical domain per converged RVE during
training-data generation. The two must never share one counter variable:

    N_REP_SEEDS ......... realizations for THIS representativeness test
    N_MECH_LHS .......... mechanical-domain LHS per RVE (lives in
                          sampling/domain_separation.py, NOT here)

NOTE on the deformation state: the paper uses F = 1 + H with H_ij = 0.1
(tensile-leaning). Cohesionless DEM cannot sustain tension, so for the DEM
RVE analogue the probe defaults to uniaxial compression F = diag(0.9,1,1);
the gate is judged in the compression/shear domain only.
"""

import math
from statistics import mean, stdev

CONVERGENCE_TOL = 0.005      # Delta <= 0.5%
N_REP_SEEDS = 5              # representativeness realizations (this stage only)


def frobenius_norm(M):
    """Frobenius norm of a 3x3 (Matrix3 or nested list)."""
    from yade.minieigenHP import Matrix3
    if not isinstance(M, Matrix3):
        M = Matrix3(*[M[r][c] for r in range(3) for c in range(3)])
    return math.sqrt(sum(M[r, c] ** 2 for r in range(3) for c in range(3)))


def representativeness_test(u, n_seeds=N_REP_SEEDS, f_probe=None, seed0=0,
                            cell_size=1.0, n_spheres=1000, verbose=True,
                            probe_kwargs=None):
    """Fixed-u representativeness: Delta over n_seeds realizations.

    Each realization: fresh packing (O.reset inside make_rve_packing) ->
    quasi-static probe_F(f_probe) -> ||S|| (Frobenius).

    Returns dict(converged, delta, mean, norms, n_seeds).
    """
    from yade.minieigenHP import Matrix3
    from rve.generate import make_rve_packing
    from rve.homogenize import probe_F, homogenized_stress

    if f_probe is None:
        # uniaxial compression; tensionless DEM -> compression/shear domain only
        f_probe = Matrix3(0.9, 0, 0, 0, 1, 0, 0, 0, 1)
    probe_kwargs = dict(probe_kwargs or {})
    probe_kwargs.setdefault("n_increments", 40)
    probe_kwargs.setdefault("steps_per_increment", 120)
    probe_kwargs.setdefault("damping", 0.7)

    norms = []
    for s in range(n_seeds):
        make_rve_packing(cell_size=cell_size, u=u, seed=seed0 + s,
                         n_spheres=n_spheres, verbose=verbose)
        probe_F(f_probe, **probe_kwargs)
        S, _, _, _ = homogenized_stress()
        nrm = frobenius_norm(S)
        norms.append(nrm)
        if verbose:
            print("[representativeness] seed=%d ||S||=%.6e Pa"
                  % (seed0 + s, nrm), flush=True)

    mu = mean(norms)
    if len(norms) > 1 and mu > 0:
        delta = stdev(norms) / mu
    else:
        delta = float("inf")
    converged = delta <= CONVERGENCE_TOL
    if verbose:
        print("[representativeness] n=%d mean||S||=%.6e Pa Delta=%.4f%% "
              "(tol 0.5%%) -> %s"
              % (n_seeds, mu, 100.0 * delta,
                 "CONVERGED" if converged else "NOT CONVERGED"), flush=True)
    return {"converged": converged, "delta": delta, "mean": mu,
            "norms": norms, "n_seeds": n_seeds}
