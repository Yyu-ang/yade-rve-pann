"""RVE convergence test — paper §4.1, §5.2, Fig. 10.

For each sampled u in U: prescribe F = 1 + H with H_ij = 0.1 (paper §5.2),
draw 1000 mechanical samples, compute

    Delta = std(||S||) / mean(||S||)   (in %)

RVE accepted if Delta <= 0.5%.
"""
CONVERGENCE_TOL = 0.005
N_MECH_SAMPLES = 1000
H_PRESCRIBED = 0.1


def convergence_test(u, cell_size, seed=0):
    """Return (converged: bool, delta: float) for one RVE realization."""
    raise NotImplementedError
