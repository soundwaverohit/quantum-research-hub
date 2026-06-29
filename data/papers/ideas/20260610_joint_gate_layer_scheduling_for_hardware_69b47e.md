# Idea — Joint Gate-Layer Scheduling for Hardware Depth and Contraction Treewidth in QCTN Training Loops

**Status:** proposed ·
**Novelty:** 7.0 · **Feasibility:** 7.0 ·
**Compute:** small

## Source papers
- [2112.10239](https://arxiv.org/abs/2112.10239)
- [2401.09253](https://arxiv.org/abs/2401.09253)
- [1904.00102](https://arxiv.org/abs/1904.00102)

## Observation
In simulation-in-the-loop training (the regime of 2112.10239 and the GQE pipeline of 2401.09253), every optimizer step pays a tensor contraction whose cost is set by the contraction tree, which depends on gate ordering. Commuting layers (e.g., even/odd brickwork sublayers, ZZ rotations in Ising-type ansatze) can be permuted freely. A scheduler that searches this permutation space against a two-term objective (hardware depth + cotengra-estimated contraction FLOPs) is a new kind of compiler pass that serves both the QPU and the GPU simulator - squarely the CUDA-Q + cuTensorNet co-design space.

## Hypothesis
Reordering commuting entangling-gate layers in QCTN circuits to jointly minimize compiled depth on the target lattice AND the treewidth of the circuit's tensor-network contraction graph cuts classical gradient-computation cost by >=30% with zero change to the implemented unitary - because gate order is a free parameter that current compilers spend only on hardware depth, ignoring the simulation cost that dominates hybrid training loops.

## Why it might work
(n/a)

## Smallest experiment
16-24 qubit brickwork and Ising-ansatz circuits; enumerate or anneal over commuting-layer permutations; for each, record cotengra FLOPs estimate + compiled depth; report Pareto improvement over as-written order. Contraction cost estimation only - no large simulation required.

## Baseline
As-written gate order: contraction cost from cotengra's default pathfinder and compiled depth from Qiskit level-3, on identical circuits.

## Metric
Estimated contraction FLOPs and peak intermediate tensor size per energy/gradient evaluation; compiled depth on grid and heavy-hex maps; verification that reordered circuit is unitarily identical (commutation check + statevector equality at 8 qubits).

## Failure modes
- Contraction pathfinders already invariant to commuting-layer order, so no headroom exists
- Permutation search space explodes beyond ~10 layers without a good heuristic
- FLOPs estimates from cotengra do not correlate with real GPU wall-clock on cuTensorNet

## Expected runtime
Smoke test: ~20 minutes local CPU. Full permutation-search study: 3-4 days.
