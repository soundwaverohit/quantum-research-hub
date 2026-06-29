# Idea — Tensor-Network-Topology-Aware Qubit Placement: Matching Ansatz Entanglement Graphs to Hardware Lattices

**Status:** proposed ·
**Novelty:** 6.0 · **Feasibility:** 9.0 ·
**Compute:** small

## Source papers
- [2112.10239](https://arxiv.org/abs/2112.10239)
- [1809.02573](https://arxiv.org/abs/1809.02573)
- [2106.13304](https://arxiv.org/abs/2106.13304)

## Observation
SABRE (1809.02573) optimizes placement generically via reverse traversal, with no knowledge of circuit structure. QCTN ansatze (2112.10239) have interaction graphs that are themselves lattices (chains, trees, ladders) — often subgraph-isomorphic or near-isomorphic to hardware topologies. A structure-aware placement pass should find embeddings that need few or zero SWAPs, where SABRE finds them only by luck. Directly relevant to NVIDIA CUDA-Q compiler passes.

## Hypothesis
For circuits with explicit tensor-network structure (brickwork MPS, tree/MERA layouts), an initial qubit placement that minimizes the graph edit distance between the ansatz's entanglement graph and the hardware coupling map (heavy-hex, square grid) reduces post-routing two-qubit gate count by >=20% versus SABRE's default initial mapping, because TN circuits have sparse, regular interaction graphs that generic placement heuristics fail to exploit.

## Why it might work
(n/a)

## Smallest experiment
12-16 qubit brickwork-MPS and binary-tree ansatz circuits; compile to heavy-hex and 4x4 grid coupling maps; compare SABRE baseline vs subgraph-matching placement (VF2 or simulated annealing on edge-overlap objective). Pure compilation study - no quantum simulation needed, runs in minutes on CPU.

## Baseline
Qiskit transpile(optimization_level=3) with SABRE layout+routing on the same circuits and coupling maps; report post-routing CNOT count and depth.

## Metric
Post-routing two-qubit gate count, circuit depth, and SWAP count, averaged over 20 seeds; placement-pass runtime overhead.

## Failure modes
- SABRE already near-optimal for small structured circuits, gains vanish below 20 qubits
- VF2 subgraph matching times out on irregular couplings
- Gains in SWAP count do not translate to fidelity gains once gate errors are heterogeneous

## Expected runtime
Smoke test: <10 minutes local CPU. Full study: 1-2 days.
