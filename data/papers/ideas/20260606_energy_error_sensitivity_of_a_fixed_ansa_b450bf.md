# Idea — Energy-error sensitivity of a fixed ansatz across TFIM field strengths

**Status:** proposed ·
**Novelty:** 2.5 · **Feasibility:** 4.3 ·
**Compute:** small

## Source papers
- [2606.10001](https://arxiv.org/abs/2606.10001)
- [2606.10005](https://arxiv.org/abs/2606.10005)

## Observation
Suggested by 'Hybrid QPEPS-QMERA ansatz with adaptive bond dimension for 2D lattices' and 2 related paper(s) in group D_hamiltonian.

## Hypothesis
A fixed-depth ansatz's energy error peaks near the TFIM critical point (h≈J).

## Why it might work
Correlation length grows near criticality, stressing a fixed-depth ansatz.

## Smallest experiment
Run the TFIM VQE at h in {0.5, 1.0, 2.0} with fixed depth; compare energy error.

## Baseline
Untrained ansatz (best of random parameter sets); equal-parameter generic ansatz.

## Metric
energy_error vs exact diagonalization; improvement over baseline.

## Failure modes
- grid too coarse to see the peak
- optimizer variance masks the trend

## Expected runtime
< 1 minute (CPU)
