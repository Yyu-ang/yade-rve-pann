"""Plate-with-hole triangular mesh via scipy.spatial.Delaunay.

Default domain (paper Fig. 6): 8 m x 8 m plate (x-z plane), central circular
hole r = 2 m at (4, 4). Points: rejection sampling with refinement near the
hole + points pinned on the hole circle and plate edges. Triangles whose
centroid falls inside the hole are removed.

Seed fixed for reproducibility (recorded in handoff).
"""

import numpy as np
from scipy.spatial import Delaunay

L_DEFAULT = 8.0          # plate edge length [m]
R_HOLE_DEFAULT = 2.0     # hole radius [m]


def _sizing_accept_prob(xy, c_hole, r_hole):
    """Acceptance probability: ~1 near hole, lower far away (refinement)."""
    d = np.linalg.norm(xy - c_hole, axis=1) - r_hole  # distance to hole edge
    # fine band within 1.2 m of hole edge, coarse elsewhere
    return np.where(d < 1.2, 1.0, 0.22)


def _laplacian_smooth(coords, tris, fixed_mask, n_iter=40):
    """Laplacian smoothing of free (interior) nodes to remove slivers."""
    from scipy.sparse import coo_matrix
    N = coords.shape[0]
    # adjacency from triangles
    ii = np.concatenate([tris[:, 0], tris[:, 1], tris[:, 2],
                         tris[:, 1], tris[:, 2], tris[:, 0]])
    jj = np.concatenate([tris[:, 1], tris[:, 2], tris[:, 0],
                         tris[:, 0], tris[:, 1], tris[:, 2]])
    A = coo_matrix((np.ones_like(ii), (ii, jj)), shape=(N, N)).tocsr()
    A = A.maximum(A.T)  # symmetric
    deg = np.asarray(A.sum(axis=1)).ravel()
    free = ~fixed_mask
    for _ in range(n_iter):
        nbr_sum = A @ coords
        new = coords.copy()
        new[free] = nbr_sum[free] / deg[free][:, None]
        coords = new
    return coords


def plate_with_hole(n_points=1100, n_hole_edge=140, seed=20261005,
                    L=L_DEFAULT, r_hole=R_HOLE_DEFAULT, c_hole=None):
    """Generate the mesh.

    Returns dict with:
      coords : (N,2) node coordinates
      tris   : (M,3) triangle connectivity
      bnd_bottom, bnd_top, bnd_hole : boolean node masks
      L, r_hole : geometry parameters (for downstream use)
    """
    c_hole = (np.array([L / 2.0, L / 2.0]) if c_hole is None
              else np.asarray(c_hole, dtype=float))
    rng = np.random.default_rng(seed)
    pts = []

    # 1) hole edge (pinned on the circle -> clean polygonal hole boundary)
    th = np.linspace(0.0, 2.0 * np.pi, n_hole_edge, endpoint=False)
    pts.append(np.stack([c_hole[0] + r_hole * np.cos(th),
                         c_hole[1] + r_hole * np.sin(th)], axis=1))

    # 2) plate edges (sparse, for clean Dirichlet boundaries)
    n_edge = 40
    s = np.linspace(0.0, L, n_edge)
    pts.append(np.stack([s, np.zeros_like(s)], axis=1))          # bottom
    pts.append(np.stack([s, np.full_like(s, L)], axis=1))        # top
    pts.append(np.stack([np.zeros_like(s), s], axis=1))          # left
    pts.append(np.stack([np.full_like(s, L), s], axis=1))        # right

    # 3) interior rejection sampling with hole refinement
    n_interior = n_points
    cand = rng.random((n_interior * 6, 2)) * L
    d2 = np.sum((cand - c_hole) ** 2, axis=1)
    cand = cand[d2 > (r_hole + 0.02) ** 2]          # outside the hole
    keep = rng.random(cand.shape[0]) < _sizing_accept_prob(cand, c_hole, r_hole)
    cand = cand[keep][:n_interior]
    pts.append(cand)

    coords = np.vstack(pts)
    # de-duplicate (corners appear twice)
    coords = np.unique(np.round(coords, 9), axis=0)

    tri = Delaunay(coords)
    tris = tri.simplices.copy()

    # drop triangles whose centroid lies inside the hole
    cent = coords[tris].mean(axis=1)
    inside = np.sum((cent - c_hole) ** 2, axis=1) < (r_hole - 1e-9) ** 2
    tris = tris[~inside]

    # boundary masks
    tol = 1e-9
    bnd_bottom = coords[:, 1] <= tol
    bnd_top = coords[:, 1] >= L - tol
    bnd_left = coords[:, 0] <= tol
    bnd_right = coords[:, 0] >= L - tol
    r_node = np.linalg.norm(coords - c_hole, axis=1)
    bnd_hole = np.abs(r_node - r_hole) < 5e-3

    # Laplacian smoothing of interior nodes (fixed: all boundaries)
    fixed_bnd = bnd_bottom | bnd_top | bnd_left | bnd_right | bnd_hole
    coords = _laplacian_smooth(coords, tris, fixed_bnd)

    # re-evaluate boundary masks after smoothing (node identities unchanged)
    bnd_bottom = coords[:, 1] <= tol
    bnd_top = coords[:, 1] >= L - tol
    r_node = np.linalg.norm(coords - c_hole, axis=1)
    bnd_hole = np.abs(r_node - r_hole) < 0.02

    return {
        "coords": coords,
        "tris": tris,
        "bnd_bottom": bnd_bottom,
        "bnd_top": bnd_top,
        "bnd_hole": bnd_hole,
        "L": L,
        "r_hole": r_hole,
    }


def tri_areas_and_grads(coords, tris):
    """Vectorized area and shape-function gradients for linear triangles.

    Returns area (M,), dNdx (M,3), dNdz (M,3).
    """
    x = coords[tris]                      # (M,3,2)
    x1, x2, x3 = x[:, 0, :], x[:, 1, :], x[:, 2, :]
    area2 = (x2[:, 0] - x1[:, 0]) * (x3[:, 1] - x1[:, 1]) \
        - (x3[:, 0] - x1[:, 0]) * (x2[:, 1] - x1[:, 1])   # signed 2*area
    area = 0.5 * np.abs(area2)
    # linear-triangle shape gradients, valid with the signed area2 as is
    dNdx = np.stack([x2[:, 1] - x3[:, 1],
                     x3[:, 1] - x1[:, 1],
                     x1[:, 1] - x2[:, 1]], axis=1) / area2[:, None]
    dNdz = np.stack([x3[:, 0] - x2[:, 0],
                     x1[:, 0] - x3[:, 0],
                     x2[:, 0] - x1[:, 0]], axis=1) / area2[:, None]
    return area, dNdx, dNdz
