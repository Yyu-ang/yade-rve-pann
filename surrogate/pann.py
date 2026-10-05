"""PANN surrogate -- paper Sec. 2.5, Sec. 4.2.1 (Harazin et al., CMAME 2026).

Network: Psi(I, u) -> strain energy density (Eq. 27), where
I = (I1, I2, I3) are the invariants of C = F^T F and
u = (E, nu) are the uncertain parameters (Example I, Sec. 5.1).

Stress is reconstructed by autodiff (Eq. 6):  S = 2 dPsi/dC.
Tangent for FE incorporation (Eq. 13):       C = 4 d^2Psi/dCdC.

Interface follows review P0-4: the C-dependence of dI/dC is explicit,
i.e. stress/tangent take C (or F), not bare invariants:
    energy(I, u)            -> Psi
    stress(C, u)            -> S(3,3)
    stress_F(F, u)          -> S(3,3)  (convenience: C = F^T F)
    tangent(C, u)           -> C(3,3,3,3)

Inputs are affinely scaled to [-1,1] (paper Sec. 4.2.2). The scaling is part
of the autograd graph, so dPsi/dC computed by autograd automatically applies
the chain rule for the scaling function, as required by the paper.

Network: 5 -> 175 -> 175 -> 1 (paper Table 2 baseline), softplus hidden
activations (twice differentiable, unbounded), linear output.
"""

import numpy as np
import torch
import torch.nn as nn

INVARIANT_DIM = 3
DTYPE = torch.float64


def invariants_torch(C):
    """Invariants (I1, I2, I3) of C. C: (..., 3, 3) tensor. Returns (..., 3)."""
    trC = C[..., 0, 0] + C[..., 1, 1] + C[..., 2, 2]
    trC2 = (C * C).sum(dim=(-2, -1))
    I1 = trC
    I2 = 0.5 * (trC ** 2 - trC2)
    I3 = torch.linalg.det(C)
    return torch.stack([I1, I2, I3], dim=-1)


def invariants_numpy(C):
    """Invariants (I1, I2, I3) of C. C: (..., 3, 3) ndarray. Returns (..., 3)."""
    C = np.asarray(C, dtype=float)
    trC = C[..., 0, 0] + C[..., 1, 1] + C[..., 2, 2]
    trC2 = (C * C).sum(axis=(-2, -1))
    I1 = trC
    I2 = 0.5 * (trC ** 2 - trC2)
    I3 = np.linalg.det(C)
    return np.stack([I1, I2, I3], axis=-1)


def voigt6(S):
    """Symmetric (...,3,3) -> (...,6) Voigt (11,22,33,12,13,23)."""
    S = np.asarray(S, dtype=float)
    return np.stack(
        [S[..., 0, 0], S[..., 1, 1], S[..., 2, 2],
         S[..., 0, 1], S[..., 0, 2], S[..., 1, 2]], axis=-1)


class PANN(nn.Module):
    """Psi(I, u) physics-augmented network with autograd stress/tangent."""

    def __init__(self, u_dim=2, hidden=(175, 175)):
        super().__init__()
        self.u_dim = u_dim
        self.in_dim = INVARIANT_DIM + u_dim
        layers = []
        d = self.in_dim
        for h in hidden:
            layers += [nn.Linear(d, h), nn.Softplus()]
            d = h
        layers += [nn.Linear(d, 1)]
        self.net = nn.Sequential(*layers)
        # affine input scaler to [-1,1]: x_tilde = (x - c) / s
        self.register_buffer("c_in", torch.zeros(self.in_dim, dtype=DTYPE))
        self.register_buffer("s_in", torch.ones(self.in_dim, dtype=DTYPE))
        self.double()

    def set_scaler(self, c, s):
        """Set affine scaler from raw input stats (arrays of len in_dim)."""
        self.c_in.copy_(torch.as_tensor(np.asarray(c, dtype=float)))
        self.s_in.copy_(torch.as_tensor(np.asarray(s, dtype=float)))

    def forward_scaled(self, x_tilde):
        """Network forward on already-scaled inputs (..., in_dim) -> (...,)."""
        return self.net(x_tilde).squeeze(-1)

    def _as_torch(self, a, shape=None):
        t = torch.as_tensor(np.asarray(a, dtype=float), dtype=DTYPE)
        if shape is not None:
            t = t.reshape(shape)
        return t

    def _pack(self, I, u):
        I = self._as_torch(I, (-1, INVARIANT_DIM))
        u = self._as_torch(u, (-1, self.u_dim))
        return torch.cat([I, u], dim=-1)

    def energy(self, I, u):
        """Strain energy density Psi for raw invariants I and params u.

        Accepts numpy arrays (single (3,)/(u_dim,) or batch (N,3)/(N,u_dim));
        returns numpy scalar/array matching the input convention.
        """
        single = np.ndim(I) == 1
        x = self._pack(I, u)
        with torch.no_grad():
            psi = self.forward_scaled((x - self.c_in) / self.s_in).numpy()
        return float(psi[0]) if single else psi

    def _psi_of_C(self, C, u):
        """Differentiable Psi(C, u); C (N,3,3) requires grad. Returns (N,)."""
        I = invariants_torch(C)
        x = torch.cat([I, u], dim=-1)
        return self.forward_scaled((x - self.c_in) / self.s_in)

    def _batch_stress_torch(self, C, u, create_graph=False):
        """S = 2 dPsi/dC for a batch. C: (N,3,3) tensor, u: (N,u_dim).

        create_graph=True keeps the path to the network parameters (training);
        False detaches (inference).
        """
        C = C.clone().detach().requires_grad_(True)
        psi = self._psi_of_C(C, u)
        (grad,) = torch.autograd.grad(psi.sum(), C,
                                      create_graph=create_graph)
        return 2.0 * grad

    def batch_stress_torch(self, C, u):
        """Torch-native batched stress for training. C (N,3,3), u (N,u_dim).

        Keeps the autograd graph to the network parameters so loss.backward()
        trains the network through the stress reconstruction (Eq. 12).
        """
        return self._batch_stress_torch(C, u, create_graph=True)

    def stress(self, C, u):
        """2nd Piola-Kirchhoff stress S (Eq. 6) from right Cauchy-Green C.

        C: (3,3) or (N,3,3); u: (u_dim,) or (N,u_dim), numpy or torch.
        Returns numpy (3,3) or (N,3,3).
        """
        single = np.ndim(C) == 2
        Ct = self._as_torch(C, (-1, 3, 3))
        ut = self._as_torch(u, (-1, self.u_dim))
        with torch.enable_grad():
            S = self._batch_stress_torch(Ct, ut).numpy()
        return S[0] if single else S

    def stress_F(self, F, u):
        """S from deformation gradient F (C = F^T F). Same conventions as stress()."""
        single = np.ndim(F) == 2
        Ft = self._as_torch(F, (-1, 3, 3))
        Ct = Ft.transpose(-2, -1) @ Ft
        ut = self._as_torch(u, (-1, self.u_dim))
        with torch.enable_grad():
            S = self._batch_stress_torch(Ct, ut).numpy()
        return S[0] if single else S

    def tangent(self, C, u):
        """Material tangent C = 4 d^2Psi/dCdC (Eq. 13).

        NOTE on symmetries: autograd differentiates w.r.t. the 9 independent
        entries of C, whose raw Hessian lacks the minor symmetries. The
        physically meaningful tangent maps symmetric dE to symmetric dS
        (dS = C:dE, E = (C-I)/2, paper Eq. 13), so the Hessian is symmetrized
        over (i,j) and (k,l); major symmetry (equality of mixed partials)
        holds by construction. Since 4.0 * 0.25 = 1.0, the returned tensor is
        exactly (H + H^T12 + H^T34 + H^T12T34), i.e. the paper's
        C = 4 d^2Psi/dCdC in the symmetric-tensor sense. Verified by FD:
        ||C:dE - dS_fd|| / ||dS_fd|| << 1.

        C: (3,3) or (N,3,3); u: (u_dim,) or (N,u_dim).
        Returns numpy (3,3,3,3) or (N,3,3,3,3).
        """
        single = np.ndim(C) == 2
        Ct = self._as_torch(C, (-1, 3, 3))
        ut = self._as_torch(u, (-1, self.u_dim))
        n = Ct.shape[0]
        with torch.enable_grad():
            Cc = Ct.clone().detach().requires_grad_(True)
            psi = self._psi_of_C(Cc, ut)
            (G,) = torch.autograd.grad(psi.sum(), Cc, create_graph=True)
            H = torch.zeros(n, 3, 3, 3, 3, dtype=DTYPE)
            for a in range(3):
                for b in range(3):
                    (dG,) = torch.autograd.grad(
                        G[:, a, b].sum(), Cc, retain_graph=True)
                    H[:, a, b] = dG
            # symmetrize to the symmetric-tensor Hessian, then x4 (Eq. 13)
            Hsym = 0.25 * (H + H.transpose(1, 2) + H.transpose(3, 4)
                           + H.transpose(1, 2).transpose(3, 4))
            out = (4.0 * Hsym).numpy()
        return out[0] if single else out

    def save(self, path):
        torch.save({
            "state_dict": self.state_dict(),
            "u_dim": self.u_dim,
            "hidden": tuple(m.out_features for m in self.net
                            if isinstance(m, nn.Linear))[:-1],
            "c_in": self.c_in.numpy(),
            "s_in": self.s_in.numpy(),
        }, path)

    @classmethod
    def load(cls, path):
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        model = cls(u_dim=ckpt["u_dim"], hidden=ckpt["hidden"])
        model.load_state_dict(ckpt["state_dict"])
        model.set_scaler(ckpt["c_in"], ckpt["s_in"])
        model.eval()
        return model
