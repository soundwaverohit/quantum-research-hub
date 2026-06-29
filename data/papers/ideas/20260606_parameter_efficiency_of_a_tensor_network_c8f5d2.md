# Idea — Parameter efficiency of a tensor-network-structured ansatz on a small TFIM

**Status:** proposed ·
**Novelty:** 3.0 · **Feasibility:** 4.5 ·
**Compute:** small

## Source papers
- [2606.01001](https://arxiv.org/abs/2606.01001)

## Observation
Suggested by 'Adaptive QPEPS-QMERA ansatz for the 2D transverse-field Ising model' and 1 related paper(s) in group A_tensor_networks.

## Hypothesis
A tensor-network-structured entangling pattern reaches lower energy error than a generic hardware-efficient ansatz at equal parameter count on a 3-site TFIM.

## Why it might work
Tensor-network entanglement structure matches TFIM locality, so fewer parameters should suffice.

## Smallest experiment
VQE on a 3-site TFIM (J=h=1); compare structured vs generic ansatz at equal parameter count; energy error vs exact.

## Baseline
Untrained ansatz (best of random parameter sets); equal-parameter generic ansatz.

## Metric
energy_error vs exact diagonalization; improvement over baseline.

## Failure modes
- barren plateau at higher depth
- structured ansatz underparameterized
- optimizer trapped in local minima

## Expected runtime
< 1 minute (CPU)
