"""T01 self-test: YADE periodic stress homogenization chain + Hill-Mandel.

Run from the worktree root:
    yadedaily -x rve/tests/test_stress_mapping.py

DOD (for_manager/T01/dispatch.md):
 1. F=I relaxed packing: ||S||/E_small (no spurious stress from mapping)
 2a. Uniaxial tension F=diag(1.1,1,1) quasi-static: S symmetric
     (+ documented tension behavior for cohesionless DEM)
 2b. Uniaxial compression F=diag(0.9,1,1) quasi-static: S symmetric, S11<0
 3. Hill-Mandel: C1 direct sigma vs getStress(); C2 virtual-work
    |V0*P:dF - sum_c f.(dF.l)| / scale < 1%

YADE sign convention: compression negative, tension positive.
"""

import sys
import os

# worktree root on sys.path so `import rve...` works inside yadedaily
# NOTE: inside yadedaily, __file__ is /usr/bin/yadedaily, so use cwd
# (dispatch runs from the worktree root).
_WTROOT = os.getcwd()
if _WTROOT not in sys.path:
    sys.path.insert(0, _WTROOT)

from yade import O
from yade import utils, pack
from yade.minieigenHP import Matrix3, Vector3
from yade.utils import PWaveTimeStep, unbalancedForce

from rve.homogenize import (
    set_reference_hsize, get_deformation_gradient, deformation_invariants,
    cauchy_to_pk2, homogenized_stress, s_voigt, probe_F,
)

E_MAT = 1e7          # particle Young's modulus (Pa) — stress scale reference
SEED = 42
N_SPHERES = 1000


def mean_stress():
    s = utils.getStress()
    return (s[0, 0] + s[1, 1] + s[2, 2]) / 3.0


def n_contacts():
    return sum(1 for i in O.interactions if i.isReal)


def set_cell_scale(s):
    """Isotropically scale the cell AND particle positions (affine).

    Scaling hSize alone teleports boundary particles across the periodic
    boundary; positions must follow affinely.
    """
    h = O.cell.hSize
    for b in O.bodies:
        b.state.pos = b.state.pos * s
    O.cell.hSize = Matrix3(h[0, 0] * s, 0, 0, 0, h[1, 1] * s, 0, 0, 0, h[2, 2] * s)


def build_packing():
    """Dense periodic packing, unloaded to small residual stress; set reference."""
    O.periodic = True
    O.cell.hSize = Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 1)
    mat = FrictMat(young=E_MAT, poisson=0.3, frictionAngle=0.5, density=2600)
    O.materials.append(mat)
    sp = pack.SpherePack()
    sp.makeCloud(minCorner=(0, 0, 0), maxCorner=(1, 1, 1), rMean=0.04,
                 rRelFuzz=0.3, periodic=True, num=N_SPHERES, seed=SEED)
    print("[setup] placed %d spheres" % len(sp), flush=True)
    O.engines = [
        ForceResetter(),
        InsertionSortCollider([Bo1_Sphere_Aabb()]),
        InteractionLoop([Ig2_Sphere_Sphere_ScGeom()],
                        [Ip2_FrictMat_FrictMat_FrictPhys()],
                        [Law2_ScGeom_FrictPhys_CundallStrack()]),
        NewtonIntegrator(damping=0.85, gravity=(0, 0, 0)),
    ]
    sp.toSimulation()
    O.dt = 0.5 * PWaveTimeStep()
    # densify stepwise until a percolating network forms (~1200 contacts).
    # Stop early: deeper densification locks in large prestress; the stress
    # at ~1200 contacts is already small enough for DOD-1 (<5e-4 * E).
    for k in range(12):
        set_cell_scale(0.97)
        O.run(1200, True)
        nc = n_contacts()
        if k % 3 == 0 or nc > 1200:
            print("[setup] densify %d: contacts=%d meanStress=%.3e"
                  % (k, nc, mean_stress()), flush=True)
        if nc >= 1200:
            break
    # relax briefly at fixed cell to settle transients (NOT to zero stress:
    # a long free relaxation lets the periodic packing clump and lose contacts;
    # the locked-in stress here already satisfies DOD-1)
    O.run(500, True)
    print("[setup] ready: contacts=%d meanStress=%.3e unbalanced=%.3e" %
          (n_contacts(), mean_stress(), unbalancedForce()), flush=True)
    set_reference_hsize(O.cell.hSize)


def check1_stress_free():
    """DOD-1: F=I relaxed -> ||S||/E small."""
    S, sigma, F, J = homogenized_stress()
    # F should be identity
    fdev = max(abs(F[r, c] - (1.0 if r == c else 0.0)) for r in range(3) for c in range(3))
    snorm = max(abs(S[r, c]) for r in range(3) for c in range(3))
    rel = snorm / E_MAT
    print("[check1] max|F-I|=%.3e  max|S|=%.3e Pa  ||S||/E=%.3e" % (fdev, snorm, rel), flush=True)
    assert fdev < 1e-9, "F deviates from identity"
    assert rel < 5e-4, "residual stress too large: ||S||/E=%.3e" % rel
    return rel


def branch_vectors():
    """Yield (f, l) per real contact.

    f = contact force on body id1 (= -(normalForce+shearForce), which YADE
        reports as the force on id2); this sign matches utils.getStress(),
        whose Love-Weber sum is negative for compressive contacts.
    l = unwrapped branch vector from id1 to id2 (via i.cellDist).
    """
    h = O.cell.hSize
    for i in O.interactions:
        if not i.isReal:
            continue
        b1 = O.bodies[i.id1]
        b2 = O.bodies[i.id2]
        f = -(i.phys.normalForce + i.phys.shearForce)  # force on id1
        cd = i.cellDist
        off = h * Vector3(cd[0], cd[1], cd[2])
        p2a = b2.state.pos + off
        p2b = b2.state.pos - off
        p2 = p2a if (p2a - b1.state.pos).norm() <= (p2b - b1.state.pos).norm() else p2b
        yield f, p2 - b1.state.pos


def check3_c1_direct_vs_getstress():
    """DOD-3 C1: independent sigma=(1/V)sum f(x)l vs utils.getStress()."""
    V = O.cell.volume
    sig = Matrix3.Zero
    n = 0
    for f, l in branch_vectors():
        sig += Matrix3(f[0]*l[0], f[0]*l[1], f[0]*l[2],
                       f[1]*l[0], f[1]*l[1], f[1]*l[2],
                       f[2]*l[0], f[2]*l[1], f[2]*l[2])
        n += 1
    sig = sig * (1.0 / V)
    s = utils.getStress()
    diff = sig - s
    md = max(abs(diff[r, c]) for r in range(3) for c in range(3))
    ms = max(abs(s[r, c]) for r in range(3) for c in range(3))
    rel = md / ms if ms > 0 else md
    print("[check3-C1] contacts=%d max|sigma_direct-getStress|=%.3e  "
          "max|getStress|=%.3e  rel=%.3e" % (n, md, ms, rel), flush=True)
    assert n > 500, "too few contacts for a meaningful check"
    assert rel < 1e-6, "getStress mismatch: rel=%.3e" % rel
    return rel


def check3_c2_virtual_work(dF_list):
    """DOD-3 C2: Hill-Mandel virtual work V0*P:dF == sum_c f.(dF.L0).

    L0 is the reference branch vector; with affine kinematics l = F*L0,
    so dL = dF*L0 = dF*F^{-1}*l.  At F=I this reduces to dF*l.
    """
    S, sigma, F, J = homogenized_stress()
    from rve.homogenize import get_reference_hsize
    V0 = get_reference_hsize().determinant()
    P = J * sigma * F.inverse().transpose()  # 1st Piola-Kirchhoff
    Finv = F.inverse()
    results = []
    for name, dF in dF_list:
        if not isinstance(dF, Matrix3):
            dF = Matrix3(*[dF[r][c] for r in range(3) for c in range(3)])
        # macro: V0 * (P : dF)
        macro = V0 * sum(P[r, c] * dF[r, c] for r in range(3) for c in range(3))
        # micro: sum_c f . (dF . L0), L0 = F^{-1} . l
        micro = 0.0
        for f, l in branch_vectors():
            L0 = Finv * l
            du = dF * L0
            micro += f.dot(du)
        scale = max(abs(macro), abs(micro), 1e-30)
        rel = abs(macro - micro) / scale
        print("[check3-C2:%s] macro=%.6e micro=%.6e rel=%.3e" %
              (name, macro, micro, rel), flush=True)
        assert rel < 0.01, "Hill-Mandel violated for %s: rel=%.3e" % (name, rel)
        results.append(rel)
    return results


def check2_compression():
    """DOD-2b: uniaxial compression F=diag(0.9,1,1): S symmetric, S11<0."""
    F_t = Matrix3(0.9, 0, 0, 0, 1, 0, 0, 0, 1)
    I1, I2, I3, Sv = probe_F(F_t, n_increments=40, steps_per_increment=120, damping=0.7)
    S, sigma, F, J = homogenized_stress()
    asym = max(abs(S[r, c] - S[c, r]) for r in range(3) for c in range(3))
    smax = max(abs(S[r, c]) for r in range(3) for c in range(3))
    print("[check2b] F_xx=%.4f S11=%.3e S22=%.3e S33=%.3e asym=%.3e" %
          (F[0, 0], S[0, 0], S[1, 1], S[2, 2], asym), flush=True)
    print("[check2b] invariants: I1=%.4f I2=%.4f I3=%.6f (expect ~2.81,~2.62,~0.81)"
          % (I1, I2, I3), flush=True)
    assert asym / max(smax, 1e-30) < 1e-4, "S not symmetric"
    assert S[0, 0] < 0, "compression should give S11<0, got %.3e" % S[0, 0]
    assert abs(S[0, 0]) / E_MAT > 1e-4, "stress magnitude suspiciously small"
    return S[0, 0]


def check2_tension():
    """DOD-2a: uniaxial tension F=diag(1.1,1,1): S symmetric; document behavior."""
    # return to reference first
    probe_F(Matrix3(1, 0, 0, 0, 1, 0, 0, 0, 1),
            n_increments=30, steps_per_increment=80, damping=0.7)
    F_t = Matrix3(1.1, 0, 0, 0, 1, 0, 0, 0, 1)
    I1, I2, I3, Sv = probe_F(F_t, n_increments=40, steps_per_increment=120, damping=0.7)
    S, sigma, F, J = homogenized_stress()
    asym = max(abs(S[r, c] - S[c, r]) for r in range(3) for c in range(3))
    smax = max(abs(S[r, c]) for r in range(3) for c in range(3))
    print("[check2a] F_xx=%.4f S11=%.3e S22=%.3e S33=%.3e asym=%.3e" %
          (F[0, 0], S[0, 0], S[1, 1], S[2, 2], asym), flush=True)
    print("[check2a] NOTE: cohesionless DEM cannot sustain tension; x-contacts open, "
          "S11~0 is the physical response. Sign convention verified via compression.", flush=True)
    assert asym / max(smax, 1e-30) < 1e-4 or smax < 1e2, "S not symmetric"
    return S[0, 0]


if __name__ == "__main__":
    build_packing()
    r1 = check1_stress_free()
    r3c1 = check3_c1_direct_vs_getstress()
    dF_uni = Matrix3(0.01, 0, 0, 0, 0, 0, 0, 0, 0)
    dF_shr = Matrix3(0, 0.01, 0, 0.01, 0, 0, 0, 0, 0)
    dF_vol = Matrix3(0.01, 0, 0, 0, 0.01, 0, 0, 0, 0.01)
    r3c2 = check3_c2_virtual_work([("uniax", dF_uni), ("shear", dF_shr), ("vol", dF_vol)])
    s11c = check2_compression()
    # Hill-Mandel also at compressed state
    r3c2b = check3_c2_virtual_work([("uniax@compressed", dF_uni)])
    s11t = check2_tension()
    print("=" * 60, flush=True)
    print("T01 SELF-TEST SUMMARY", flush=True)
    print("  check1 ||S||/E at F=I ......... %.3e  (DOD: <5e-4)" % r1, flush=True)
    print("  check3-C1 direct/getStress .... %.3e  (DOD: <1e-6)" % r3c1, flush=True)
    print("  check3-C2 Hill-Mandel max rel . %.3e  (DOD: <1e-2)" % max(r3c2 + r3c2b), flush=True)
    print("  check2b S11 compression ....... %.3e Pa (<0 OK)" % s11c, flush=True)
    print("  check2a S11 tension ........... %.3e Pa (documented)" % s11t, flush=True)
    print("ALL ASSERTS PASSED", flush=True)
