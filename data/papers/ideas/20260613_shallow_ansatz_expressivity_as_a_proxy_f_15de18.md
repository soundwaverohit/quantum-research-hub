# Idea — Shallow-ansatz expressivity as a proxy for quantum feature maps

**Status:** proposed ·
**Novelty:** 2.0 · **Feasibility:** 3.8 ·
**Compute:** small

## Source papers
- [2606.13641](https://arxiv.org/abs/2606.13641)

## Observation
Suggested by 'Generalized two-qubit Hamiltonian for Projective Quantum Feature Maps' and 1 related paper(s) in group E_qml.

## Hypothesis
A shallow Ry+CX ansatz already captures most of the TFIM ground-state structure, bounding the benefit of richer feature maps.

## Why it might work
Expressivity gains may saturate quickly on small systems.

## Smallest experiment
Compare 1- vs 2-layer ansatz energy error on the 3-site TFIM as an expressivity proxy.

## Baseline
Untrained ansatz (best of random parameter sets); equal-parameter generic ansatz.

## Metric
energy_error vs exact diagonalization; improvement over baseline.

## Failure modes
- proxy weakly related to QML feature maps
- small-system effects dominate

## Expected runtime
< 1 minute (CPU)
