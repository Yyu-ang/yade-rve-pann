"""RVE generation for the reproduction.

Paper §4.1, §5.2: the RVE geometry is parametrized by uncertain descriptors
u in U. Each realization must be convergence-tested (§2.4, Fig. 10) before it
contributes training data.

YADE realization: periodic Cell filled with a polydisperse sphere packing.
Descriptors u = (porosity, mean radius, size polydispersity, ...).
"""

from yade import pack, utils


def make_rve_packing(cell_size, u, seed=0):
    """Build one periodic RVE packing for descriptor vector u.

    u = dict(porosity=..., rMean=..., rRelFuzz=...)
    Returns the SpherePack (not yet inserted into O.bodies).
    """
    raise NotImplementedError


def insert_periodic_packing(sp):
    """Insert packing into O.bodies with O.periodic=True."""
    raise NotImplementedError
