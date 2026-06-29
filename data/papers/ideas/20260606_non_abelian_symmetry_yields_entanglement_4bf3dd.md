# Idea — Non-abelian symmetry yields entanglement-growing (super-constant) bond-dimension savings in TDVP certification

**Status:** proposed ·
**Novelty:** 2.5 · **Feasibility:** 4.0 ·
**Compute:** small

## Source papers
- [2606.04771](https://arxiv.org/abs/2606.04771)

## Observation
Rausch et al. (2606.04771) reach χ≈62,000 using full U(1)×SU(2) symmetry plus GPU tensor contraction, certify the previously unresolved high-entanglement window t∈[5.2,6], and reduce a claimed 3000× quantum advantage to ~36×.

## Hypothesis
When certifying 1D Fermi-Hubbard quench dynamics to a fixed MPS truncation error ε, the effective bond dimension required under full U(1)×SU(2) symmetry is smaller than under abelian U(1)×U(1) by a factor that increases with evolution time (i.e., with entanglement), rather than a constant prefactor. Consequently the maximum certifiable time t_cert(ε) gained from non-abelian symmetry grows faster than the naive multiplet-counting (constant-factor) estimate.

## Why it might work
(n/a)

## Smallest experiment
On a small L=8–12 Fermi-Hubbard chain, run TDVP quench with (a) no symmetry, (b) abelian U(1)×U(1), (c) non-abelian U(1)×SU(2). For fixed ε, record effective χ(t) and the energy / double-occupancy error vs an exact-diagonalization reference; plot the saving ratio χ_abelian(t)/χ_nonabelian(t) against t.

## Baseline
Abelian-symmetry TDVP at the same truncation error (the conventional approach), with exact diagonalization at small L as ground truth.

## Metric
Saving ratio χ_abelian(t)/χ_nonabelian(t) as a function of t and ε; certifiable time t_cert(ε) per symmetry setting; wall-time per symmetry at matched accuracy.

## Failure modes
- At small L entanglement saturates before any scaling trend emerges
- SU(2) bookkeeping overhead dominates wall-time at small χ, masking the memory saving
- Differing truncation-error control between symmetry implementations confounds the comparison

## Expected runtime
CPU-feasible for L≤12 in minutes to tens of minutes; no GPU needed at this scale.
