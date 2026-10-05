"""RVE generation for the reproduction.

Paper §4.1, §5.2: the RVE geometry is parametrized by uncertain descriptors
u in U. Each realization must be convergence-tested (§2.4, Fig. 10) before it
contributes training data.

YADE realization: periodic Cell filled with a polydisperse sphere packing.
Descriptors u = (vf, rMean, rRelFuzz, E_soft, E_stiff, ...).

Biphasic variant (T02): stiff inclusions in a soft matrix via two FrictMat
materials ("DEM heterogeneous RVE analogue", not the paper's continuum RVE).
FrictMat is cohesionless: tension S~0 is the physical response; gates are
judged in the compression/shear domain only.

T01 experience reused:
- densify by affine cell scaling until ~1200 contacts, then STOP (deeper
  densification locks in large prestress);
- only a brief relaxation at fixed cell afterwards (a long free relaxation
  lets the periodic packing clump and lose contacts);
- every hSize change must affinely carry particle positions (else boundary
  particles teleport across the periodic boundary).
"""

import math
import random

E_SOFT_DEFAULT = 1e7
E_STIFF_DEFAULT = 5e7


def affine_scale_cell(s):
    """Isotropically scale the periodic cell AND particle positions by s.

    Scaling hSize alone teleports boundary particles across the periodic
    boundary (T01 finding #2); positions must follow affinely.
    """
    from yade import O
    from yade.minieigenHP import Matrix3
    h = O.cell.hSize
    for b in O.bodies:
        b.state.pos = b.state.pos * s
    O.cell.hSize = Matrix3(h[0, 0] * s, 0, 0,
                           0, h[1, 1] * s, 0,
                           0, 0, h[2, 2] * s)


def n_contacts():
    """Number of real (mechanical) contacts in the current scene."""
    from yade import O
    return sum(1 for i in O.interactions if i.isReal)


def make_rve_packing(cell_size=1.0, u=None, seed=0, n_spheres=1000,
                     target_contacts=1200, max_densify_steps=14, verbose=True):
    """Build a periodic biphasic RVE packing and densify it (T01 protocol).

    u: dict with keys vf (stiff-phase fraction by count ~ volume),
       rMean, rRelFuzz, E_soft, E_stiff, poisson, frictionAngle, density.

    The scene is RESET (O.reset()), so repeated calls yield independent
    realizations. Materials/engines are rebuilt; the biphasic assignment
    happens BEFORE the first collider run so Ip2 sees the correct material
    pairs from the start. The reference hSize (F = I state) is stored via
    homogenize.set_reference_hsize().

    Returns a dict with build statistics.
    """
    from yade import O, pack
    from yade.minieigenHP import Matrix3
    from yade.utils import PWaveTimeStep, unbalancedForce, getStress
    from yade.wrapper import (FrictMat, ForceResetter, InsertionSortCollider,
                              Bo1_Sphere_Aabb, InteractionLoop,
                              Ig2_Sphere_Sphere_ScGeom,
                              Ip2_FrictMat_FrictMat_FrictPhys,
                              Law2_ScGeom_FrictPhys_CundallStrack,
                              NewtonIntegrator)
    from rve.homogenize import set_reference_hsize

    u = dict(u or {})
    vf = float(u.get("vf", 0.2))
    rMean = float(u.get("rMean", 0.04))
    rRelFuzz = float(u.get("rRelFuzz", 0.3))
    E_soft = float(u.get("E_soft", E_SOFT_DEFAULT))
    E_stiff = float(u.get("E_stiff", E_STIFF_DEFAULT))
    poisson = float(u.get("poisson", 0.3))
    frictionAngle = float(u.get("frictionAngle", 0.5))
    density = float(u.get("density", 2600))

    O.reset()
    O.periodic = True
    O.cell.hSize = Matrix3(cell_size, 0, 0, 0, cell_size, 0, 0, 0, cell_size)
    O.materials.append(FrictMat(young=E_soft, poisson=poisson,
                                frictionAngle=frictionAngle, density=density))  # id 0
    O.materials.append(FrictMat(young=E_stiff, poisson=poisson,
                                frictionAngle=frictionAngle, density=density))  # id 1

    sp = pack.SpherePack()
    sp.makeCloud(minCorner=(0, 0, 0),
                 maxCorner=(cell_size, cell_size, cell_size),
                 rMean=rMean, rRelFuzz=rRelFuzz,
                 periodic=True, num=n_spheres, seed=seed)
    if verbose:
        print("[generate] seed=%d placed %d spheres" % (seed, len(sp)), flush=True)

    O.engines = [
        ForceResetter(),
        InsertionSortCollider([Bo1_Sphere_Aabb()]),
        InteractionLoop([Ig2_Sphere_Sphere_ScGeom()],
                        [Ip2_FrictMat_FrictMat_FrictPhys()],
                        [Law2_ScGeom_FrictPhys_CundallStrack()]),
        NewtonIntegrator(damping=0.85, gravity=(0, 0, 0)),
    ]
    sp.toSimulation()

    # biphasic assignment before the first collider run
    rng = random.Random(seed * 100003 + 17)
    ids = [b.id for b in O.bodies]
    n_stiff = int(round(vf * len(ids)))
    stiff_ids = set(rng.sample(ids, n_stiff))
    for b in O.bodies:
        if b.id in stiff_ids:
            b.mat = O.materials[1]
    O.dt = 0.5 * PWaveTimeStep()

    # Two-stage densify (T01 protocol, refined): coarse 0.97 steps until
    # percolation onset, then fine 0.997 steps servoed on the mean stress.
    # Rationale: near jamming, contact count explodes with tiny volumetric
    # strain (pilot: 1198 -> 1707 contacts in one 0.995 step), so a pure
    # contact-count target overshoots deep into the jammed state and locks
    # in prestress (||S||/E ~ 1e-2), which would poison the G1c closure gate.
    # Stopping at first |mean stress| ~ 1e-4 * E keeps the F=I reference
    # nearly stress-free (T01 DOD-1 scale), so the literal DOD residual
    # ||S||/E < 1e-3 measures hysteresis, not prestress.
    from yade.utils import getStress as _getStress
    for k in range(14):
        affine_scale_cell(0.97)
        O.run(1200, True)
        nc = n_contacts()
        if verbose and (k % 3 == 0 or nc >= 200):
            print("[generate] densify-coarse %d: contacts=%d" % (k, nc),
                  flush=True)
        if nc >= 200:
            break
    for k in range(40):
        affine_scale_cell(0.997)
        O.run(600, True)
        nc = n_contacts()
        s = _getStress()
        ms = abs((s[0, 0] + s[1, 1] + s[2, 2]) / 3.0) / E_soft
        if verbose and (k % 5 == 0 or nc >= 800):
            print("[generate] densify-fine %d: contacts=%d |mean|/E=%.2e"
                  % (k, nc, ms), flush=True)
        if (nc >= 800 and ms >= 1e-4) or nc >= target_contacts + 300:
            break
    O.run(1000, True)  # settle transients (NOT a long free relaxation)
    set_reference_hsize(O.cell.hSize)

    v_stiff = 0.0
    v_tot = 0.0
    for b in O.bodies:
        v = 4.0 / 3.0 * math.pi * b.shape.radius ** 3
        v_tot += v
        if b.id in stiff_ids:
            v_stiff += v
    s = getStress()
    mean_s = (s[0, 0] + s[1, 1] + s[2, 2]) / 3.0
    info = {
        "seed": seed,
        "n_bodies": len(ids),
        "n_stiff": n_stiff,
        "vf_count": n_stiff / max(len(ids), 1),
        "vf_vol": v_stiff / max(v_tot, 1e-30),
        "n_contacts": n_contacts(),
        "mean_stress": mean_s,
        "unbalanced": unbalancedForce(),
        "E_soft": E_soft,
        "E_stiff": E_stiff,
    }
    if verbose:
        print("[generate] ready: bodies=%d stiff=%d vf_vol=%.3f contacts=%d "
              "meanStress=%.3e unbalanced=%.3e"
              % (info["n_bodies"], n_stiff, info["vf_vol"],
                 info["n_contacts"], mean_s, info["unbalanced"]), flush=True)
    return info
