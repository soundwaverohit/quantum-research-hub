# Idea — QFIM-rank saturation as a sector-resolved predictor of VQE overparametrization onset

**Status:** proposed ·
**Novelty:** 2.0 · **Feasibility:** 4.5 ·
**Compute:** small

## Source papers
- [2606.05719](https://arxiv.org/abs/2606.05719)

## Observation
Yamanaka et al. (2606.05719) report that overparametrization onset coincides with the disappearance of local minima and that QFIM rank saturates within invariant subspaces; the VQE loss-decay rate under gradient descent scales linearly with #params.

## Hypothesis
For a symmetry-respecting Hamiltonian variational ansatz (HVA) restricted to a fixed invariant subspace, the parameter count M* at which the quantum Fisher information matrix (QFIM) rank saturates predicts the parameter count at which VQE attains a target energy error from random initialization with high success probability, and M* tracks the sector's dynamical Lie algebra (DLA) dimension rather than circuit depth or qubit number. Concretely: the "knee" in random-restart VQE success rate vs #params coincides (within ±1 ansatz layer) with the QFIM-rank-saturation point, and that coincidence disappears for a non-symmetry-respecting hardware-efficient ansatz of equal parameter count.

## Why it might work
(n/a)

## Smallest experiment
On a 2-site (≤6 qubit) Z2 lattice gauge theory, or a transverse-field Ising proxy, build one symmetry-respecting HVA and one hardware-efficient ansatz. For each parameter count: (a) estimate QFIM rank at several random points, (b) run ~100 random-initialization VQE optimizations. Locate the QFIM-saturation knee and the VQE-success knee and test their coincidence.

## Baseline
Depth-based overparametrization heuristic (#params ≈ 2·dim of accessible subspace) and the equal-parameter hardware-efficient (non-symmetry) ansatz.

## Metric
Parameter-count gap between QFIM-saturation knee and VQE-success knee (target: within 1 layer); fraction of random inits reaching |E−E_exact| < 1e-3 Ha; Spearman correlation between QFIM rank and success rate across parameter counts.

## Failure modes
- QFIM rank estimation noisy or ill-conditioned at small sample size
- TFIM proxy may not capture the Z2 LGT generator structure
- Knees too gradual to localize cleanly on small systems

## Expected runtime
Minutes to ~1 hour on a laptop statevector simulator (≤6 qubits).
