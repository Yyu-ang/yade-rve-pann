"""3D KL random fields for the T09 macro UQ (Example I analogue).

Same uncertainty model as the 2D T07/T08 pipeline, extended to the 3D
plate volume (8 x 8 x t m minus the r = 2 m through-hole):

- E^iprf : marginal N(mu_E^i, 1e3^2) MPa, squared-exponential, lcorr = 1 m
- nu^rf  : marginal N(0.3, 0.03^2),  squared-exponential, lcorr = 2 m
- v      : shifted log-normal V = -0.2 + exp(Y), Y ~ N(-0.12, 0.05^2) [m]
           (reused from ``macro.kl_fields``)

The KL eigenproblem is solved on a 3D reference grid; realizations at
arbitrary query points (element centroids) use linear interpolation of
the retained modes with nearest-neighbour fallback. Eigenpairs for a
given (mu_E^i) are cached per process.

Memory model (printed by ``report()``):
- covariance: 8 * n_pts^2 bytes (one-off, freed after eigh);
- modes: 8 * n_pts * n_modes bytes (kept);
- MC streams: 8 * N_CAP * n_modes bytes per field (kept in driver).
"""

import numpy as np
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

from macro.kl_fields import build_kl, sample_displacement  # noqa: F401

SEED = 20261005
PLATE_L = 8.0
HOLE_R = 2.0


def reference_grid_3d(L=PLATE_L, r=HOLE_R, t=1.0, h=0.5, n_z=3):
    """Reference grid (n_pts, 3) for the 3D KL eigenproblem."""
    xs = np.arange(-L / 2, L / 2 + h / 2, h)
    ys = np.arange(-L / 2, L / 2 + h / 2, h)
    zs = np.linspace(0.0, t, n_z)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    inside = (X ** 2 + Y ** 2) < r ** 2
    return np.column_stack([X[~inside], Y[~inside], Z[~inside]])


class RandomField3D:
    """Zero-mean KL field + constant mean, evaluable at (m,3) points."""

    def __init__(self, points, mean, sigma, lcorr, var_ratio=0.95):
        self.points = np.asarray(points, dtype=float)
        self.mean = float(mean)
        self.sigma = float(sigma)
        self.lcorr = float(lcorr)
        vals, vecs = build_kl(self.points, sigma, lcorr, var_ratio)
        self.eigvals = vals
        self.eigvecs = vecs
        self.n_modes = int(len(vals))
        self.modes = vecs * np.sqrt(vals)[None, :]
        self._lin = LinearNDInterpolator(self.points, self.modes)
        self._nn = NearestNDInterpolator(self.points, self.modes)

    def var_ratio_retained(self):
        d2 = ((self.points[:, None, :] - self.points[None, :, :]) ** 2).sum(-1)
        total = (self.sigma ** 2 * np.exp(-d2 / self.lcorr ** 2)).trace()
        return float(self.eigvals.sum() / total)

    def memory_bytes(self):
        n, m = self.points.shape[0], self.n_modes
        return {"covariance": 8 * n * n, "modes": 8 * n * m}

    def sample(self, xi, query_points):
        xi = np.asarray(xi, dtype=float)
        batched = xi.ndim == 2
        if not batched:
            xi = xi.reshape(1, -1)
        assert xi.shape[1] == self.n_modes, (xi.shape, self.n_modes)
        q = np.asarray(query_points, dtype=float).reshape(-1, 3)
        w = self._lin(q)
        miss = np.isnan(w).any(axis=1)
        if miss.any():
            w[miss] = self._nn(q[miss])
        out = self.mean + xi @ w.T
        return out if batched else out[0]


_grid_cache = {}
_field_cache = {}


def _ref_grid(t=1.0, h=0.5, n_z=3):
    key = (t, h, n_z)
    if key not in _grid_cache:
        _grid_cache[key] = reference_grid_3d(t=t, h=h, n_z=n_z)
    return _grid_cache[key]


def make_E_field_3d(mu_E_i=3.0e4, t=1.0, h=0.5, n_z=3):
    key = ("E", mu_E_i, t, h, n_z)
    if key not in _field_cache:
        _field_cache[key] = RandomField3D(_ref_grid(t, h, n_z), mu_E_i,
                                          sigma=1e3, lcorr=1.0)
    return _field_cache[key]


def make_nu_field_3d(t=1.0, h=0.5, n_z=3):
    key = ("nu", t, h, n_z)
    if key not in _field_cache:
        _field_cache[key] = RandomField3D(_ref_grid(t, h, n_z), 0.3,
                                          sigma=0.03, lcorr=2.0)
    return _field_cache[key]


def report(E_rf, nu_rf, n_cap=40000):
    """Print mode counts and memory estimates."""
    for name, rf in [("E", E_rf), ("nu", nu_rf)]:
        mem = rf.memory_bytes()
        streams = 8 * n_cap * rf.n_modes
        print(f"[kl3d] {name}: n_pts={rf.points.shape[0]} "
              f"modes={rf.n_modes} var_ratio={rf.var_ratio_retained():.4f}")
        print(f"[kl3d]   covariance {mem['covariance']/2**20:.1f} MB "
              f"(one-off), modes {mem['modes']/2**20:.1f} MB, "
              f"streams(N_CAP={n_cap}) {streams/2**20:.1f} MB")
