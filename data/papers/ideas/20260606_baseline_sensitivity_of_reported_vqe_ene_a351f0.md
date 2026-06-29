# Idea — Baseline sensitivity of reported VQE energy error

**Status:** proposed ·
**Novelty:** 2.0 · **Feasibility:** 4.5 ·
**Compute:** small

## Source papers
- [2606.10005](https://arxiv.org/abs/2606.10005)
- [2606.10002](https://arxiv.org/abs/2606.10002)

## Observation
Suggested by 'Classical shadows for efficient error mitigation in variational algorithms' and 2 related paper(s) in group F_mitigation.

## Hypothesis
Reported VQE energy error is dominated by the baseline/seed choice on small TFIM instances.

## Why it might work
Without a fixed baseline and seeds, 'improvements' can be noise — a mitigation/repro check.

## Smallest experiment
Re-run the TFIM VQE across several seeds; report seed-stability std vs the headline energy error.

## Baseline
Untrained ansatz (best of random parameter sets); equal-parameter generic ansatz.

## Metric
energy_error vs exact diagonalization; improvement over baseline.

## Failure modes
- too few seeds
- baseline definition contested

## Expected runtime
< 1 minute (CPU)
