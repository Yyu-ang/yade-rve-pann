"""Domain-separated sampling — paper §4.2.2, Fig. 4.

1. LHS in the uncertain-parameter space U (N_U samples).
2. Per sample: generate RVE geometry + convergence test (only here!).
3. Per accepted RVE: LHS in the mechanical space F (N_F samples each).
4. Evaluate homogenized (I, u, S) for every mechanical sample.

This avoids a convergence test per mechanical sample while keeping the
design space-filling in each separated domain.
"""
N_U = 50
N_F = 1000


def lhs(n_samples, bounds):
    """Latin hypercube samples in [bounds[:,0], bounds[:,1]]."""
    raise NotImplementedError


def generate_dataset(u_bounds, f_bounds, out_path):
    """Run the full separated sampling; save (I, u, S) tuples to out_path."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit("not implemented yet")
