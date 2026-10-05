# RVE-based Multiscale Polymorphic UQ with PANN — YADE Reproduction

Reproduction of the method from:

> F. Harazin, J. Platen, F.N. Schietzold, W. Graf, M. Kaliske,
> "Multiscale polymorphic uncertainty quantification based on physics-augmented neural networks",
> *Comput. Methods Appl. Mech. Engrg.* 452 (2026) 118726.
> doi:10.1016/j.cma.2025.118726

## Method being reproduced (paper, §4–§5)

1. **Numerical homogenization (§2.4):** RVE with **periodic boundary conditions**
   (Hill–Mandel condition), macroscopic quantities as volume averages.
2. **PANN surrogate (§2.5, §4.2.1):** strain energy density
   Ψ(**I**(**C**(**F**)), **u**) approximated by a physics-augmented neural network,
   where **I** = invariants of the right Cauchy–Green tensor and **u** ∈ **U**
   are the uncertain RVE descriptors. Stress reconstructed by autodiff:
   **S** = 2∂Ψ/∂**C**; loss = ‖**S**ᴺᴺ − **S**ᴿⱽᴱ‖².
3. **Domain-separated sampling (§4.2.2):** sample uncertain-parameter space **U**
   by LHS → generate + convergence-test one RVE per **u** sample → LHS in the
   mechanical space **F** per RVE. Convergence criterion: Δ = std(‖**S**‖)/mean(‖**S**‖) ≤ 0.5%.
4. **Polymorphic UQ (§3–§4):** aleatoric (Monte Carlo), epistemic (interval
   optimization), parametric p-boxes; confidence intervals for unbounded
   distributions (§4.2.3).
5. **Numerical examples (§5):** (I) plate with hole, parametrized Neo-Hookean
   (reference solution available); (II) full framework on concrete-like RVE
   with ellipsoidal inclusions, uncertain volume fraction *v*ᶠ (iprf) and matrix
   modulus *E*ₘₐₜᵣᵢₓ (rf).

## Adaptation to YADE (this repo)

The paper's mesoscale solver is FEM (tetrahedral mesh, hyperelastic continuum).
Here the RVE is realized with **YADE DEM** (periodic `Cell`, prescribed
deformation gradient paths, homogenized stress via `getStress()`), keeping the
paper's workflow intact:

- periodic BCs → Hill–Mandel (§2.4, Eq. 9–10)
- RVE convergence study over realizations (§4.1)
- domain-separated LHS (§4.2.2)
- PANN surrogate Ψ(**I**, **u**) with stress via autodiff (§4.2.1)
- MC / interval / p-box UQ (§3)

DEM packings are the mesostructure; the surrogate/UQ layers are
microscale-agnostic, exactly as argued in §4.2 of the paper.

## Layout

```
rve/          RVE generation (packings), periodic homogenization, convergence test
sampling/     LHS, domain-separated U × F sampling scheme
surrogate/    PANN: Ψ(I,u) network, stress/tangent via autodiff
uq/           aleatoric (MC), epistemic (interval), p-box evaluation
examples/     ex1_neohooke/ — Example-I analog (surrogate vs analytical reference)
docs/         method notes extracted from the paper
data/         generated RVE datasets (not versioned if large)
```

## Requirements

- `yadedaily` (YADE daily build, Ubuntu 24.04) — `yadedaily` on PATH
- Python 3.12, `numpy`, `scipy`; `torch` for the PANN surrogate

## Quick start

```bash
# 1. RVE convergence study (paper §4.1, Fig. 10 analog)
yadedaily -x rve/convergence.py
# 2. Domain-separated data generation (paper §4.2.2, Fig. 4)
yadedaily -x sampling/domain_separation.py
# 3. Train PANN surrogate (paper §4.2.1)
python3 surrogate/train_pann.py
# 4. Polymorphic UQ demo (paper §3–§4)
python3 uq/run_uq.py
```

## Status

- [x] RVE periodic homogenization smoke-tested in YADE
- [ ] Convergence study implementation
- [ ] Domain-separated sampler
- [ ] PANN training pipeline
- [ ] UQ (MC / interval / p-box) + Example-I validation
