# Idea — Entanglement-Spectrum-Guided Cut Placement for Quantum Circuit Cutting

**Status:** proposed ·
**Novelty:** 7.0 · **Feasibility:** 8.0 ·
**Compute:** small

## Source papers
- [1904.00102](https://arxiv.org/abs/1904.00102)
- [2112.10239](https://arxiv.org/abs/2112.10239)

## Observation
Peng et al. (1904.00102) show clustered circuits decompose with overhead 2^O(K) in inter-cluster communication K, but existing cut-finding tools minimize the COUNT of cut wires, treating all cuts as equally expensive. An MPS simulation of the circuit reveals WHERE entanglement is actually low - those bonds are cheaper to cut. This turns a classical tensor-network diagnostic (cheap, GPU-acceleratable via cuTensorNet) into a compiler decision for distributed/knitted execution.

## Hypothesis
Placing wire cuts at circuit bipartitions where the MPS bond dimension (bisection entanglement) is minimal reduces circuit-cutting reconstruction error at a fixed shot budget by >=2x compared to naive geometric mid-point cuts, because cutting overhead scales with the effective Schmidt rank across the cut, not just the number of cut wires.

## Why it might work
(n/a)

## Smallest experiment
10-12 qubit TFIM Trotter circuits and shallow brickwork circuits; simulate with quimb MPS to get bond entropies at every candidate cut location; place 1-2 cuts at entropy minima vs midpoint baseline; reconstruct expectation values via standard wire-cut decomposition; compare error vs shots. Local CPU, under 10 minutes per configuration.

## Baseline
Same circuit, same number of cuts, placed at the geometric midpoint (balanced subcircuit sizes), reconstructed with identical total shot budget.

## Metric
Absolute error of reconstructed observable (e.g., ZZ correlator) vs exact statevector value, as a function of total shots; effective Schmidt rank at chosen cut points.

## Failure modes
- Entropy minima sit at locations that produce badly unbalanced subcircuits, negating the benefit
- Standard wire-cut decomposition has fixed overhead per cut regardless of entanglement, so gains only appear with rank-truncated cut protocols
- MPS entropy estimates unreliable for deep circuits where bond dimension saturates

## Expected runtime
Smoke test: ~15 minutes local. Full sweep over depths/cut counts: 2-3 days.
