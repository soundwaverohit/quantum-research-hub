# Idea — A QFIM-rank-restoration law for entanglement-assisted distributed variational circuits: predicting the Bell-pair budget from dynamical-Lie-algebra deficit

**Status:** proposed ·
**Novelty:** 4.3 · **Feasibility:** 3.5 ·
**Compute:** small

## Source papers
- [2606.05719](https://arxiv.org/abs/2606.05719)
- [2606.04548](https://arxiv.org/abs/2606.04548)

## Observation
2606.05719 establishes DLA dimension and QFIM rank as the resource measures governing variational expressivity/overparametrization for a monolithic ansatz. 2606.04548 introduces pre-shared Bell pairs per cut edge as a physical resource substituting for non-local gates in a distributed ansatz, but offers only an empirical "one Bell pair per edge, depth ≥2" rule with no expressivity theory. The intersection — a DLA/QFIM resource theory for entanglement-assisted distributed ansätze — is untouched by either paper.

## Hypothesis
Cutting a variational circuit into distributed partitions removes the two-qubit generators that straddle the cut, shrinking the dynamical Lie algebra (DLA) and hence the QFIM rank reachable by the distributed ansatz relative to its monolithic counterpart. Each pre-shared Bell pair (as used by QESTO) restores a bounded number of effective generators across the cut. Therefore the minimal number of pre-shared Bell pairs b* needed for the distributed ansatz to match the monolithic QFIM rank (its expressivity ceiling) is a computable function of the cut-induced DLA/QFIM-rank deficit — and the empirical knee at which distributed solution quality saturates to the monolithic value occurs at the SAME b*. Corollary: when the cut-induced rank deficit exceeds what k Bell pairs can restore, no circuit depth makes distributed = monolithic, predicting a hard, quantifiable expressivity gap for circuit knitting.

## Why it might work
(n/a)

## Smallest experiment
Take a 6-qubit weighted-MaxCut / Wang-tile instance partitioned into two 3-qubit halves with k cut edges. (1) Compute the monolithic ansatz DLA dimension and QFIM rank at convergence. (2) Build the QESTO-style distributed ansatz with b∈{0,…,k} pre-shared Bell pairs and compute distributed DLA dimension / QFIM rank vs b. (3) Predict b* as the smallest b with QFIM-rank(b) = monolithic rank; separately run the optimization and locate the empirical knee b** where approximation ratio saturates to the monolithic value. Test whether b* ≈ b**.

## Baseline
(i) Monolithic ansatz (expressivity ceiling); (ii) b=0 fully-partitioned ansatz / partitioned QAOA (no entanglement — the QESTO baseline); (iii) the naive "one Bell pair per cut edge" heuristic from 2606.04548.

## Metric
Agreement between predicted b* (QFIM-rank-restoration) and empirical b** (approximation-ratio saturation knee), in Bell-pair units; residual QFIM-rank gap (monolithic − distributed) at b=k; approximation ratio and valid-solution fraction vs b.

## Failure modes
- DLA/QFIM-rank computation scales steeply; tractable only up to ~10 qubits
- A static DLA may not capture QESTO's measurement-/transport-based amplitude transfer — may require a generalized (measurement-assisted) Lie-algebra notion, itself a publishable refinement
- Solution quality may track overlap with the optimum rather than full QFIM rank, breaking the rank↔quality link (informative negative result)
- Bell pairs may restore generators in an instance-dependent way, so b* is a distribution rather than a single number

## Expected runtime
Hours on a laptop statevector simulator; DLA/QFIM-rank computation tractable at ≤10 qubits. No GPU or cloud required.
