# Idea — Ansatz depth vs VQE convergence on the TFIM

**Status:** proposed ·
**Novelty:** 2.5 · **Feasibility:** 4.8 ·
**Compute:** small

## Source papers
- [2606.01001](https://arxiv.org/abs/2606.01001)
- [2606.01002](https://arxiv.org/abs/2606.01002)

## Observation
Suggested by 'Adaptive QPEPS-QMERA ansatz for the 2D transverse-field Ising model' and 2 related paper(s) in group B_vqe.

## Hypothesis
Increasing ansatz depth lowers VQE energy error on the small TFIM, with diminishing returns past a few layers.

## Why it might work
More layers add expressivity but also more parameters to optimize and more barren-plateau risk.

## Smallest experiment
Sweep ansatz_layers in {1,2,3} on a 3-site TFIM VQE; record energy error and parameter count.

## Baseline
Untrained ansatz (best of random parameter sets); equal-parameter generic ansatz.

## Metric
energy_error vs exact diagonalization; improvement over baseline.

## Failure modes
- overfitting to one seed
- vanishing gradients at depth
- no improvement past 2 layers

## Expected runtime
< 1 minute (CPU)
