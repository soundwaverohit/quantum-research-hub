# Idea — Expressivity-Compilability Pareto Frontier of Entangling-Graph Geometries for Lattice VQE

**Status:** proposed ·
**Novelty:** 5.0 · **Feasibility:** 9.0 ·
**Compute:** small

## Source papers
- [2106.13304](https://arxiv.org/abs/2106.13304)
- [2112.10239](https://arxiv.org/abs/2112.10239)
- [1809.02573](https://arxiv.org/abs/1809.02573)

## Observation
Patti et al. (2106.13304) showed shallow, structured circuits simulated as factorized tensor rings can outperform deep generic ansatze. But there is no systematic measurement of the three-way trade-off: (1) variational expressivity (energy error), (2) hardware cost (compiled gate count/depth after routing), (3) classical simulability (contraction FLOPs - what determines cuQuantum training throughput). Mapping this frontier tells both the ansatz designer and the compiler which entangling geometry to emit for a given lattice Hamiltonian.

## Hypothesis
For 2D lattice Hamiltonians (4x4 transverse-field Ising), ansatz entangling graphs restricted to hardware-native lattice subgraphs trace a Pareto frontier where ladder geometry reaches within 1% of the all-to-all ansatz ground-state energy at under 50% of the post-routing gate cost - identifying a quantitative sweet spot for geometry-constrained QCTN ansatz design.

## Why it might work
(n/a)

## Smallest experiment
VQE on 8-qubit (2x4) TFIM with four entangling geometries: chain, ladder, square-grid, all-to-all. Statevector simulation, exact diagonalization reference, fixed seeds. Then 16-qubit (4x4) confirmation run. Plot the 3-axis Pareto frontier.

## Baseline
All-to-all entangling ansatz at matched parameter count (the expressivity ceiling), and a 1D-chain ansatz (the cost floor); both compiled to the same heavy-hex and grid coupling maps.

## Metric
Relative ground-state energy error vs exact diagonalization; post-routing CNOT count and depth; estimated contraction cost (opt_einsum/cotengra FLOPs) per gradient step; all at fixed parameter budget and fixed optimizer (L-BFGS, 5 seeds).

## Failure modes
- Optimizer noise/barren plateaus larger than geometry effect, making energy differences statistically insignificant
- Conclusions at 8-16 qubits do not extrapolate to useful scales
- Pareto ordering flips between heavy-hex and grid targets, preventing a single recommendation

## Expected runtime
8-qubit sweep: ~30 minutes local CPU. 16-qubit confirmation: a few hours.
