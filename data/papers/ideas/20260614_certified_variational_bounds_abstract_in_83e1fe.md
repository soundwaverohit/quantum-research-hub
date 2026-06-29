# Idea — Certified Variational Bounds: Abstract-Interpretation Soundness for ML-Accelerated VQE

**Status:** proposed ·
**Novelty:** 8.0 · **Feasibility:** 8.0 ·
**Compute:** small

## Source papers
- [2605.08605](https://arxiv.org/abs/2605.08605)
- [2106.13304](https://arxiv.org/abs/2106.13304)
- [1904.00102](https://arxiv.org/abs/1904.00102)

## Observation
arXiv 2605.08605 enforces logical soundness by projecting a recurrent model's latent state onto an abstract-interpretation lattice between forward passes, yielding correct-or-abstain behavior. The variational principle is itself a soundness condition: every evaluated energy over-approximates E0, and optimization is monotone narrowing toward a fixpoint. Current ML-accelerated variational methods report whatever energy the optimizer lands on, with no certification that it is a valid bound. Wrapping the learned optimizer in a monotone acceptance/projection layer imports the paper's soundness guarantee into quantum ground-state estimation. This directly serves the repo ethos of "no result without evidence" by making honesty a property of the optimizer, not just the validator. Relevant to NVIDIA cuQuantum/cuTensorNet training loops where the learned policy controls sweep schedule and contraction order.

## Hypothesis
An ML-accelerated VQE/DMRG optimizer wrapped in a monotone certified-bound projection — a learned parameter update is accepted only when it provably tightens the variational upper bound, otherwise the running-best (certified) bound is retained — guarantees the reported energy is always a sound over-approximation of the true ground-state energy E0 (never spuriously below it), while matching or beating naive gradient descent in iterations-to-convergence. The variational principle <psi(theta)|H|psi(theta)> >= E0 makes the running bound an abstract-interpretation soundness invariant, and the projection step is the quantum analog of the between-pass lattice projection in arXiv 2605.08605 (Lattice Deduction Transformers).

## Why it might work
(n/a)

## Smallest experiment
VQE on 6-8 qubit TFIM / H2-LiH with a hardware-efficient ansatz. Implement a wrapper that tracks the running-best certified bound and accepts a learned step only if it lowers the bound (else keeps best). Compare against plain gradient descent on: soundness violations, final error, iterations. Exact diagonalization gives E0. Statevector sim, local CPU, <30 min.

## Baseline
Plain Adam/L-BFGS VQE on the same Hamiltonian with no certification layer; report final energy, iterations-to-convergence, and how often the naive run transiently reports an energy below the certified running-best.

## Metric
(1) Soundness violations: count of reported energies below E0 (target: 0 by construction); (2) tightness: final |E_reported - E0| vs baseline; (3) iterations-to-convergence and wall-clock vs baseline; (4) overhead of the projection/acceptance step (%).

## Failure modes
- The certified-bound acceptance reduces to plain 'keep the best iterate', adding no value over standard early-stopping
- Monotone acceptance slows convergence by rejecting useful exploratory steps (exploration-soundness tension)
- On noisy/shot-based estimates the variational bound is only stochastic, so 'soundness' holds only in expectation and the guarantee weakens

## Expected runtime
Smoke test: ~30 min local CPU. Full study across Hamiltonians/ansatze: 2-3 days.
