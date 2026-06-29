# Idea — Circuit-locality proxy: does a chain-entangled ansatz suffice for the TFIM?

**Status:** proposed ·
**Novelty:** 2.5 · **Feasibility:** 3.5 ·
**Compute:** small

## Source papers
- [2606.01002](https://arxiv.org/abs/2606.01002)

## Observation
Suggested by 'Circuit cutting for distributed VQE on Heisenberg chains' and 1 related paper(s) in group C_distributed.

## Hypothesis
A nearest-neighbour (cuttable) entangling chain reaches near-exact TFIM energy, suggesting limited need for long-range gates.

## Why it might work
If local entanglement suffices, the circuit is more amenable to cutting/knitting.

## Smallest experiment
Run the TFIM VQE with the nearest-neighbour CX chain ansatz; check energy error vs exact as a locality proxy.

## Baseline
Untrained ansatz (best of random parameter sets); equal-parameter generic ansatz.

## Metric
energy_error vs exact diagonalization; improvement over baseline.

## Failure modes
- locality insufficient near criticality
- proxy too coarse for real circuit cutting

## Expected runtime
< 1 minute (CPU)
