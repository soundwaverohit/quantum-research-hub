# Idea — Certified Qubit Mapping: Sound Constraint Propagation with Infeasibility Certificates for Routing

**Status:** proposed ·
**Novelty:** 7.0 · **Feasibility:** 8.0 ·
**Compute:** small

## Source papers
- [2605.08605](https://arxiv.org/abs/2605.08605)
- [1809.02573](https://arxiv.org/abs/1809.02573)
- [2112.10239](https://arxiv.org/abs/2112.10239)

## Observation
arXiv 2605.08605 solves constraint-satisfaction tasks (Sudoku, mazes) by projecting onto an abstract-interpretation lattice between passes, staying sound and abstaining when it cannot certify an answer. Qubit mapping is structurally the same problem: assign logical to physical qubits respecting coupling-graph adjacency for every two-qubit gate. The natural abstract domain is the per-qubit possibility set (exactly the Sudoku candidate-set lattice); routing becomes monotone narrowing via arc-consistency plus branching (SWAP insertion) when narrowing stalls. SABRE (1809.02573) and RL routers give neither legality-by-construction nor an infeasibility proof, so they can emit illegal mappings needing repair. The exact fixpoint of this process is VF2-style subgraph matching, connecting this to the TN-topology-aware placement idea; the contribution here is the sound, abstain-capable propagation layer.

## Hypothesis
Framing qubit placement and routing as abstract interpretation over a possibility-set lattice (for each logical qubit, the set of still-feasible physical qubits, ordered by inclusion) yields a router that is legal-by-construction — a lattice-projection step forbids illegal partial mappings — and emits an infeasibility certificate ("no SWAP-free embedding exists for this circuit layer on this coupling map") when constraint narrowing stalls. This provides correctness guarantees that neither SABRE nor RL-based routers offer, at post-routing two-qubit gate counts within 10% of SABRE on structured (tensor-network) circuits.

## Why it might work
(n/a)

## Smallest experiment
12-16 qubit brickwork-MPS and binary-tree ansatz circuits on heavy-hex and 4x4 grid coupling maps. Implement arc-consistency narrowing over per-qubit candidate sets + SWAP branching when stalled; compare legality and CNOT count vs Qiskit SABRE. Add a few hand-built unembeddable layers to test the abstain certificate. Pure compilation, local CPU, <15 min.

## Baseline
Qiskit transpile(optimization_level=3) with SABRE layout+routing on identical circuits and coupling maps; report post-routing CNOT count, depth, and any post-hoc legality repairs needed.

## Metric
(1) Legality: fraction of emitted mappings that are valid without repair (target: 100% by construction); (2) post-routing two-qubit gate count and depth vs SABRE; (3) infeasibility-certificate correctness on hand-constructed unembeddable layers (precision/recall of the abstain signal); (4) propagation runtime vs SABRE.

## Failure modes
- Constraint propagation alone is too weak; without strong branching heuristics the CNOT count blows past SABRE
- Arc-consistency narrowing is expensive per layer and dominates compile time on larger circuits
- The 'infeasibility certificate' is only meaningful for SWAP-free embedding; with SWAPs allowed everything is feasible, so the abstain signal needs a cost threshold to be useful

## Expected runtime
Smoke test: <15 min local CPU. Full study: 1-2 days.
