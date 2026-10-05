"""KL random fields for Example I (§5.1) — Harazin et al., CMAME 452 (2026).

Uncertain inputs:
  - E^iprf : interval-probability random field, marginal N(mu_E^i, 1e3^2) MPa,
             mu_E^i in [2.8e4, 3.2e4] (set by the caller, e.g. T08 interval analysis),
             squared-exponential autocorrelation, lcorr,E = 1 m
  - nu^rf  : random field, marginal N(0.3, 0.03^2),
             squared-exponential autocorrelation, lcorr,nu = 2 m
  - v      : shifted log-normal displacement V = x0 + exp(Y),
             Y ~ N(muU=-0.12, sigmaU=0.05^2), x0 = -0.2  (unit: m)

Karhunen-Loeve expansion (paper [38]):
    C(x, x') = sigma^2 * exp(-|x-x'|^2 / l^2)

Eigenpairs are solved once on a reference grid (8x8 m plate minus r=2 m
central hole, 0.2 m spacing, ~1372 points); `RandomField.sample` evaluates
realizations at arbitrary query points by interpolating the retained modes
(LinearNDInterpolator, nearest-neighbour fallback outside the hull) — T08
maps the fields onto Gauss points.

All randomness flows through explicit numpy.random.Generator instances.
"""

import numpy as np
from scipy.linalg import eigh
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

SEED = 20261005

# Plate geometry (paper §5.1, Fig. 6): l = 8 m, b = 2 m (width), r = 2 m hole.
# Reference grid: full 8x8 m with 0.2 m spacing, points inside the central
# hole (r = 2 m) removed -> ~1372 nodes.
PLATE_L = 8.0
HOLE_R = 2.0
GRID_H = 0.2


def reference_grid(L=PLATE_L, r=HOLE_R, h=GRID_H):
    """Reference grid points (n_pts, 2) for the KL eigenproblem."""
    xs = np.arange(0.0, L + h / 2, h)
    ys = np.arange(0.0, L + h / 2, h)
    X, Y = np.meshgrid(xs, ys)
    inside = ((X - L / 2) ** 2 + (Y - L / 2) ** 2) < r ** 2
    return np.column_stack([X[~inside], Y[~inside]])


def build_kl(points, sigma, lcorr, var_ratio=0.95):
    """KL eigenpairs of the squared-exponential covariance on `points`.

    Returns (eigvals, eigvecs) with eigvals sorted descending, truncated so
    that the retained variance ratio >= var_ratio.
    """
    d2 = ((points[:, None, :] - points[None, :, :]) ** 2).sum(-1)
    C = sigma ** 2 * np.exp(-d2 / lcorr ** 2)
    vals, vecs = eigh(C)  # ascending
    vals = vals[::-1]
    vecs = vecs[:, ::-1]
    total = vals.sum()
    n = int(np.searchsorted(np.cumsum(vals) / total, var_ratio)) + 1
    return vals[:n], vecs[:, :n]


class RandomField:
    """Zero-mean KL field + constant mean, evaluable at arbitrary points."""

    def __init__(self, points, mean, sigma, lcorr, var_ratio=0.95):
        self.points = np.asarray(points, dtype=float)
        self.mean = float(mean)
        self.sigma = float(sigma)
        self.lcorr = float(lcorr)
        vals, vecs = build_kl(self.points, sigma, lcorr, var_ratio)
        self.eigvals = vals
        self.eigvecs = vecs
        self.n_modes = int(len(vals))
        # scaled modes: sqrt(lambda_k) * phi_k(x_i), shape (n_pts, n_modes)
        self.modes = vecs * np.sqrt(vals)[None, :]
        self._lin = LinearNDInterpolator(self.points, self.modes)
        self._nn = NearestNDInterpolator(self.points, self.modes)

    def var_ratio_retained(self):
        d2 = ((self.points[:, None, :] - self.points[None, :, :]) ** 2).sum(-1)
        total = (self.sigma ** 2 * np.exp(-d2 / self.lcorr ** 2)).trace()
        return float(self.eigvals.sum() / total)

    def sample(self, xi, query_points):
        """Realize the field at `query_points` given std-normal coefficients.

        xi: (n_modes,) standard-normal coefficients, or (K, n_modes) for
            K independent realizations.
        query_points: (m, 2) array.
        Returns: (m,) field values, or (K, m) for batched xi.
        """
        xi = np.asarray(xi, dtype=float)
        batched = xi.ndim == 2
        if not batched:
            xi = xi.reshape(1, -1)
        assert xi.shape[1] == self.n_modes, (xi.shape, self.n_modes)
        q = np.asarray(query_points, dtype=float).reshape(-1, 2)
        w = self._lin(q)
        miss = np.isnan(w).any(axis=1)
        if miss.any():
            w[miss] = self._nn(q[miss])
        out = self.mean + xi @ w.T   # (K, m)
        return out if batched else out[0]


_grid_cache = {}


def _ref_grid():
    if "grid" not in _grid_cache:
        _grid_cache["grid"] = reference_grid()
    return _grid_cache["grid"]


def make_E_field(mu_E_i=3.0e4):
    """E^iprf field. `mu_E_i` is the interval parameter set by the caller."""
    return RandomField(_ref_grid(), mu_E_i, sigma=1e3, lcorr=1.0)


def make_nu_field():
    """nu^rf field."""
    return RandomField(_ref_grid(), 0.3, sigma=0.03, lcorr=2.0)


def sample_displacement(rng):
    """Shifted log-normal displacement: V = x0 + exp(Y), Y~N(-0.12, 0.05^2)."""
    return -0.2 + np.exp(rng.normal(-0.12, 0.05))


def _check(cond, name, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {detail}")
    return cond


def main():
    rng = np.random.default_rng(SEED)
    N = 2000
    ok = True

    # --- grid ---
    pts = _ref_grid()
    print(f"[info] reference grid points: {len(pts)}")

    # --- fields ---
    E = make_E_field(mu_E_i=3.0e4)
    nu = make_nu_field()
    print(f"[info] E modes: {E.n_modes}, var_ratio={E.var_ratio_retained():.4f}")
    print(f"[info] nu modes: {nu.n_modes}, var_ratio={nu.var_ratio_retained():.4f}")
    ok &= _check(E.var_ratio_retained() >= 0.95, "E var_ratio>=0.95")
    ok &= _check(nu.var_ratio_retained() >= 0.95, "nu var_ratio>=0.95")

    # --- DOD 1: sample mean / std ---
    xi_E = rng.standard_normal((N, E.n_modes))
    xi_nu = rng.standard_normal((N, nu.n_modes))
    E_s = E.sample(xi_E, pts)   # (N, n_pts)
    nu_s = nu.sample(xi_nu, pts)
    m_err = abs(E_s.mean() - 3.0e4) / 3.0e4
    # std evaluated at the field centre point (grid point => truncated var)
    s_err = abs(E_s.std() - 1e3) / 1e3
    ok &= _check(m_err < 0.01, "DOD1 E mean rel err <1%", f"err={m_err:.2e}")
    ok &= _check(s_err < 0.05, "DOD1 E std rel err <5%", f"err={s_err:.2e}")

    # --- DOD 2: empirical correlation at 1 m (E) and 2 m (nu) ---
    from scipy.spatial.distance import pdist
    d = pdist(pts)
    E_flat = E_s.reshape(N, -1)
    nu_flat = nu_s.reshape(N, -1)
    tri = np.triu_indices(len(pts), 1)

    def emp_corr_at(target, field_flat):
        sel = np.abs(d - target) < 0.03
        i, j = tri[0][sel], tri[1][sel]
        a = field_flat[:, i]
        b = field_flat[:, j]
        a = a - a.mean(0, keepdims=True)
        b = b - b.mean(0, keepdims=True)
        num = (a * b).mean(0)
        den = np.sqrt((a ** 2).mean(0) * (b ** 2).mean(0))
        return float(np.median(num / den)), int(sel.sum())

    cE, nE = emp_corr_at(1.0, E_flat)
    cnu, nnu = emp_corr_at(2.0, nu_flat)
    tgt = np.exp(-1)
    ok &= _check(abs(cE - tgt) < 0.05, "DOD2 E corr(1m)~exp(-1)+-0.05",
                 f"emp={cE:.4f} target={tgt:.4f} pairs={nE}")
    ok &= _check(abs(cnu - tgt) < 0.05, "DOD2 nu corr(2m)~exp(-1)+-0.05",
                 f"emp={cnu:.4f} target={tgt:.4f} pairs={nnu}")

    # --- DOD 3: positivity / bounds ---
    ok &= _check(bool((E_s > 0).all()), "DOD3 E all positive",
                 f"min={E_s.min():.1f}")
    ok &= _check(bool(((nu_s > 0) & (nu_s < 0.5)).all()), "DOD3 nu in (0,0.5)",
                 f"min={nu_s.min():.4f} max={nu_s.max():.4f}")

    # --- DOD 4: report truncation orders ---
    print(f"[info] DOD4 E modes={E.n_modes}, nu modes={nu.n_modes}")

    # --- DOD 5: displacement ---
    v = np.array([sample_displacement(rng) for _ in range(N)])
    med, mean = np.median(v), v.mean()
    ok &= _check(abs(med - 0.69) / 0.69 < 0.02, "DOD5 v median~0.69 +-2%",
                 f"median={med:.4f}")
    ok &= _check(abs(mean - 0.688) / 0.688 < 0.02, "DOD5 v mean~0.688 +-2%",
                 f"mean={mean:.4f}")

    # --- DOD 6: interpolation to off-grid query points (T08 Gauss-point use) ---
    q = rng.uniform(0, 8, size=(50, 2))
    qE = E.sample(rng.standard_normal(E.n_modes), q)
    ok &= _check(np.isfinite(qE).all() and qE.shape == (50,),
                 "off-grid query finite")

    print("ALL CHECKS PASSED" if ok else "CHECKS FAILED")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
