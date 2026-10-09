"""Structured hexahedral meshes for the 3D plate-with-hole (T09).

In-plane layout (x-y plane, plate [-L/2, L/2]^2, centred at origin):
nested layers blend a circle (r = r_hole) into the outer square, i.e.
for layer parameter s in [0, 1] and angle theta::

    R(s, theta) = (1 - s) * r_hole + s * R_square(theta),
    R_square(theta) = (L/2) / max(|cos theta|, |sin theta|).

Radial grading clusters layers near the hole (stress concentration).
The 2D quad layers are extruded uniformly through the thickness t
(z in [0, t]) giving 8-node trilinear hexahedra (hex8).

Also provides a plain box mesh (no hole) for the patch test.
"""

import numpy as np

# reference hex8 node signs (xi, eta, zeta)
_HEX_SIGNS = np.array([
    [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
    [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
], dtype=float)

_GP = 1.0 / np.sqrt(3.0)
GAUSS_PTS = np.array([[a, b, c] for a in (-_GP, _GP)
                      for b in (-_GP, _GP) for c in (-_GP, _GP)])
GAUSS_W = np.ones(8)


def shape_derivs(xi, eta, zeta):
    """dN/dxi at one reference point: (8, 3)."""
    s = _HEX_SIGNS
    dN = np.empty((8, 3))
    dN[:, 0] = 0.125 * s[:, 0] * (1 + s[:, 1] * eta) * (1 + s[:, 2] * zeta)
    dN[:, 1] = 0.125 * s[:, 1] * (1 + s[:, 0] * xi) * (1 + s[:, 2] * zeta)
    dN[:, 2] = 0.125 * s[:, 2] * (1 + s[:, 0] * xi) * (1 + s[:, 1] * eta)
    return dN


# precomputed derivatives at the 8 Gauss points: (8, 8, 3)
DN_DXI = np.stack([shape_derivs(*gp) for gp in GAUSS_PTS])


def _node_id(k, l, j, n_theta, n_z):
    return (k * n_theta + l) * (n_z + 1) + j


def plate_with_hole_3d(n_theta=32, n_r=6, n_z=4, L=8.0, r_hole=2.0, t=1.0,
                       radial_power=1.6):
    """3D plate with central through-hole. Returns mesh dict.

    n_theta: angular divisions (multiple of 4 recommended),
    n_r: radial layers, n_z: through-thickness layers.
    """
    if n_theta % 2:
        raise ValueError("n_theta should be even")
    theta = np.linspace(0.0, 2 * np.pi, n_theta, endpoint=False)
    ct, st = np.cos(theta), np.sin(theta)
    r_sq = (L / 2.0) / np.maximum(np.abs(ct), np.abs(st))  # (n_theta,)

    n_k = n_r + 1
    coords = np.zeros((n_k * n_theta * (n_z + 1), 3))
    for k in range(n_k):
        s = (k / n_r) ** radial_power
        r = (1 - s) * r_hole + s * r_sq
        base = k * n_theta * (n_z + 1)
        for l in range(n_theta):
            x, y = r[l] * ct[l], r[l] * st[l]
            for j in range(n_z + 1):
                coords[base + l * (n_z + 1) + j] = (x, y, t * j / n_z)

    hexes = []
    for k in range(n_r):
        for l in range(n_theta):
            l2 = (l + 1) % n_theta
            for j in range(n_z):
                n0 = _node_id(k, l, j, n_theta, n_z)
                n1 = _node_id(k + 1, l, j, n_theta, n_z)
                n2 = _node_id(k + 1, l2, j, n_theta, n_z)
                n3 = _node_id(k, l2, j, n_theta, n_z)
                n4 = _node_id(k, l, j + 1, n_theta, n_z)
                n5 = _node_id(k + 1, l, j + 1, n_theta, n_z)
                n6 = _node_id(k + 1, l2, j + 1, n_theta, n_z)
                n7 = _node_id(k, l2, j + 1, n_theta, n_z)
                hexes.append([n0, n1, n2, n3, n4, n5, n6, n7])
    hexes = np.asarray(hexes, dtype=int)

    # boundary flags (outer ring k == n_r lies exactly on the square)
    y = coords[:, 1]
    on_outer = np.zeros(len(coords), dtype=bool)
    on_outer[n_r * n_theta * (n_z + 1):] = True
    eps = 1e-9
    bnd_bottom = on_outer & (y < -L / 2 + eps)
    bnd_top = on_outer & (y > L / 2 - eps)
    hole_nodes = np.zeros(len(coords), dtype=bool)
    hole_nodes[:n_theta * (n_z + 1)] = True

    mesh = {
        "coords": coords,
        "hexes": hexes,
        "bnd_bottom": bnd_bottom,
        "bnd_top": bnd_top,
        "hole_nodes": hole_nodes,
        "L": float(L),
        "r_hole": float(r_hole),
        "t": float(t),
        "n_theta": n_theta,
        "n_r": n_r,
        "n_z": n_z,
    }
    q = mesh_quality(mesh)
    mesh.update(q)
    return mesh


def box_mesh(nx=2, ny=2, nz=2, Lx=1.0, Ly=1.0, Lz=1.0):
    """Plain structured box (no hole), for the patch test."""
    xs = np.linspace(0, Lx, nx + 1)
    ys = np.linspace(0, Ly, ny + 1)
    zs = np.linspace(0, Lz, nz + 1)

    def nid(i, j, k):
        return (i * (ny + 1) + j) * (nz + 1) + k

    coords = np.array([[x, y, z] for x in xs for y in ys for z in zs])
    hexes = []
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                hexes.append([nid(i, j, k), nid(i + 1, j, k),
                              nid(i + 1, j + 1, k), nid(i, j + 1, k),
                              nid(i, j, k + 1), nid(i + 1, j, k + 1),
                              nid(i + 1, j + 1, k + 1),
                              nid(i, j + 1, k + 1)])
    hexes = np.asarray(hexes, dtype=int)
    mesh = {"coords": coords, "hexes": hexes, "L": Lx, "r_hole": 0.0,
            "t": Lz, "box": (nx, ny, nz)}
    mesh.update(mesh_quality(mesh))
    return mesh


def hex_geom(coords, hexes):
    """Per-Gauss-point geometry: detJ (M*8,), dNdx (M*8, 8, 3).

    Returns (detJ, dNdx, n_elem).
    """
    M = hexes.shape[0]
    X = coords[hexes]                       # (M, 8, 3)
    detJ = np.empty((M, 8))
    dNdx = np.empty((M, 8, 8, 3))
    for g in range(8):
        dndxi = DN_DXI[g]                   # (8, 3)
        # J[m, i, j] = sum_a X[m, a, i] * dN_a/dxi_j  (i spatial, j reference)
        J = np.einsum("mai,aj->mij", X, dndxi)
        det = np.linalg.det(J)
        detJ[:, g] = det
        invJ = np.linalg.inv(J)
        dNdx[:, g] = np.einsum("maj,mji->mai", dndxi[None, :, :].repeat(M, 0),
                               invJ)
    if np.any(detJ <= 0):
        bad = np.nonzero(detJ <= 0)[0]
        raise ValueError(f"{len(bad)} inverted Gauss points, "
                         f"min detJ={detJ.min():.3e}")
    return detJ, dNdx, M


def mesh_quality(mesh):
    """Min/mean detJ over Gauss points (Jacobian positivity sanity)."""
    detJ, _, _ = hex_geom(mesh["coords"], mesh["hexes"])
    return {"min_detJ": float(detJ.min()),
            "mean_detJ": float(detJ.mean()),
            "n_nodes": int(mesh["coords"].shape[0]),
            "n_hex": int(mesh["hexes"].shape[0])}


def element_centroids(mesh):
    return mesh["coords"][mesh["hexes"]].mean(axis=1)
