"""Polymorphic UQ on the trained PANN — paper §3, §5.

- aleatoric.py: Monte Carlo over random quantities (§3.1); q99 convergence
  check (1e4 samples, redraw 2e3 until stable within 0.5% over 5 steps).
- epistemic.py: interval analysis by optimization (evolutionary strategy),
  criterion q99 (§3.2, Eq. 21).
- pbox.py: parametric p-box bounds from interval-valued distribution
  parameters (§3.3, Eqs. 22-23, 29-31).

Quantity of interest: sigma_char = max |principal stress| (Eq. 32).
"""
