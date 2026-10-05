# Paper method notes — Harazin et al., CMAME 452 (2026) 118726

## Uncertain parameters (Example II, §5.2, Table 3)

| parameter | type | distribution | bounds / params |
|---|---|---|---|
| v_f (inclusion volume fraction) | iprf (interval prob.-based random field) | Gaussian marginal, μ ∈ [16%, 34%], σ = 2% | DoE: [10%, 40%], β = 2.8e-3; sq-exp corr, l_corr = 2 m |
| E_matrix | rf (random field) | Gaussian, μ = 16814 MPa, σ = 187 MPa | DoE: [16253, 17375] MPa, β = 2.8e-3; sq-exp corr, l_corr = 1 m |
| v (macro displacement) | r (random var) | log-normal, μ_U = −0.1 m, σ_U = 0.15 m, x₀ = −0.6 m | — |
| h (macro imperfection height) | i (interval) | [0.5·l, 0.8·l] | — |
| E_inclusion | deterministic | 5e4 MPa | — |
| l_RVE | deterministic | 60 mm | — |

## Data generation (§4.2.2, §5.2)

- 50 LHS samples in **U** (uncertain-parameter space); per sample: generate RVE,
  convergence test.
- Convergence test: fixed prescribed **F** = **1** + **H**, H_ij = 0.1, over
  multiple realizations / VE sizes (NOT the 1000 mechanical LHS below).
- Convergence criterion — ⚠️ paper typesetting vs figure inconsistency, visually
  verified from PDF p.14 (see `docs/reproduction_plan_review_2026-10-05.md` §1.2):
  typeset as Δ = (E(‖**S̄**‖) − √(VAR(‖**S̄**‖)))/E(‖**S̄**‖) [%], Δ ≤ 0.5%,
  but Fig.10(b) ("Δ × 10¹" ≈ 0.9–1.3) and the criterion are only consistent with
  the coefficient of variation. **Adopted operative definition:**
  Δ = std(‖**S̄**‖)/mean(‖**S̄**‖) [%] ≤ 0.5%. Recorded as known transcription risk.
- 1000 LHS samples in **F** per converged RVE → 50 × 1000 = 50,000 (I, u, S) tuples.
  Paper cost: ~43 CPU hours (FEM RVE, i5-10400).
- Mechanical domain: H entries in [−0.2, 0.2], **F** = **H** + **1**.
- All inputs scaled to [−1, 1]; chain rule applied to Eqs. (6)/(13).

## Example I reference law — Eq.(33), §5.1 (visually verified, PDF p.11)

Modified Neo-Hookean (must be implemented exactly; NOT Simo–Taylor):

    S = F⁻¹ · ( κ·ln[J]·F⁻ᵀ + η·( J^(−2/3)·F − tr(J^(−2/3)·C)/3 · F⁻ᵀ ) )
    κ = E/(3·(1−2ν)),  η = E/(2·(1+ν))

i.e. **P** = ∂Ψ/∂**F** for Ψ = κ/2·(lnJ)² + η/2·(Ī₁−3), then **S** = **F**⁻¹·**P**.
Uncertain inputs (Table 1): E ∈ [2.5, 3.5]×10⁴ MPa (β=2.8e-3), ν ∈ [0.21, 0.39];
mechanical domain H_ij ∈ [−0.2, 0.2]; DoE 50 × 100; PANN 5→175→175→1.

## Paper scope limitations (for honest reporting)

- Hyperelasticity assumed throughout (§2.3); PANN structure requires it.
- Invariant form Ψ(**I**,**u**) requires material symmetry known a priori and
  stable over **u** (§4.2.1, Conclusion).
- Non-converged / stochastic VEs → stochastic energy response: explicitly out
  of the method's current capability (Conclusion).
- Example II has no feasible full-FE² reference solution; it demonstrates the
  framework, not a benchmark for numerical comparison.

## PANN (§2.5, §4.2.1)

- Input: invariants **I**(C) (3 invariants, isotropic) + uncertain params **u**.
- Output: strain energy Ψ; stress via autodiff **S** = 2∂Ψ/∂**C**.
- Loss: mean ‖**S**ᴺᴺ − **S**ᴿⱽᴱ‖² (Eq. 12); Ψ itself never needed as label.
- Architecture (Table 4): 5 → 170 → 55 → 1, softplus/softplus/softplus/linear.
  Must be twice differentiable (tangent ℂ needs 2nd derivatives, Eq. 13).
- Hyperparameter optimization: 90/10 split, 5 restarts, 50 architectures (paper).

## UQ (§3, §5)

- Quantity of interest: σ_char = max over nodes of max |principal stress| (Eq. 32).
- Aleatoric: Monte Carlo, 1e4 samples, redraw 2e3 until q99 stable within 0.5%
  over last 5 steps.
- Epistemic: interval analysis via evolutionary strategy, criterion = q99.
- Result: q99 = [1368.8, 1859.7] MPa (Example II p-box bounds).
- PANN eval ≈ 0.0005 s vs FEM RVE ≈ 203 s per Gauss-point evaluation.

## Reproduction mapping (YADE DEM)

| paper element | YADE realization (this repo) |
|---|---|
| periodic BC RVE, Hill–Mandel | `O.periodic=True`, `O.cell`, prescribed `O.cell.velGrad` / `hSize` |
| homogenized **S** | `getStress()` volume average → pull-back to 2nd Piola–Kirchhoff |
| RVE geometry parametrization | polydisperse sphere packings, descriptors **u** = (porosity, size ratio, …) |
| convergence Δ ≤ 0.5% | `rve/convergence.py` |
| domain-separated LHS | `sampling/domain_separation.py` |
| PANN Ψ(**I**,**u**) | `surrogate/pann.py` (PyTorch, autodiff stress) |
| MC / interval / p-box | `uq/` |

## Phase 0 negative result — DEM track CLOSED (2026-10-05, user decision)

**Question**: can a YADE DEM periodic cell (1000-particle bidisperse packing,
`E_soft=1e7 Pa`) serve as the microscale model under the paper's energy-PANN
ansatz (single-valued Ψ(**C**,**u**), hyperelastic premise)?

**Answer: NO** — for both contact models tested, with un-relaxed tolerances.
Evidence (all independently re-run by maintainer; scripts in `rve/tests/`):

| gate | FrictMat (T02) | bonded CohFrictMat (T02b) | DOD |
|---|---|---|---|
| G1a stress mapping | C1 rel 7.5e-18 (machine precision) | — (inherited) | <1e-6 ✓ |
| G1b Hill–Mandel | max rel 2.2e-15 (machine precision) | — (inherited) | <1e-2 ✓ |
| G1c load–unload closure | 7.89e-7 | 1.41e-3 | <1e-3: GO then **NO-GO** |
| G1c dissipation ratio | **0.255** | **0.162** | <0.10: **NO-GO** both |
| G1c path independence | 0.0349 | 0.0197 | <0.05 ✓ both |
| G1c bond breakage | n/a | 0 | 0 ✓ |
| G2a isotropy spread | 0.0070 | 0.0510 | <0.10 ✓ both |
| G2b representativeness Δ | **4.93%** | **3.62%** | ≤0.5%: **NO-GO** both |

**Physical mechanism** (diagnosed over multiple pilot/sweep runs):
- FrictMat: 25% of external work dissipated by inter-particle frictional
  sliding — incompatible with a single-valued strain energy.
- Bonded (zero broken bonds, `frictDissip`=0): dissipation drops to 16% but
  remains >10%. Residual comes from **finite-strain contact-topology
  hysteresis**: ~640 new unbonded frictional contacts form during 10%
  compression, ~55 stay stuck after unloading → self-stress state.
  Intrinsic to DEM at finite strain; cohesion cannot remove it.
- G2b: realization scatter at 1000 particles ≈ 7–10× the paper's FEM
  criterion (0.5%) — RVE size effect, independent of contact model.

**Honest reporting note**: this negative result is itself informative — it
quantifies *why* the paper uses FEM RVEs and what a DEM adaptation would
require (history-dependent surrogate, declared beyond-paper method).
The analytical track (Phase 1A: Eq.(33) → PANN → UQ) is complete and
unaffected. DEM gate infrastructure (`rve/generate.py`, `rve/convergence.py`,
`rve/tests/test_gates.py`) is retained in-repo for reuse.
