# Idea — QESTO's advantage is an entanglement-budget effect: a Bell-pair-per-cut-edge threshold below which it loses to partitioned QAOA

**Status:** proposed ·
**Novelty:** 2.8 · **Feasibility:** 4.5 ·
**Compute:** small

## Source papers
- [2606.04548](https://arxiv.org/abs/2606.04548)

## Observation
Matwiejew et al. (2606.04548) show QESTO beats equally-partitioned QAOA at depth ≥2 using exactly one pre-shared Bell pair per distributed edge and no non-local gates after initialization.

## Hypothesis
QESTO's advantage over equally-partitioned QAOA is governed by the entanglement budget b/k (pre-shared Bell pairs b per k cut edges), not by the ansatz form itself. There exists a critical fraction f_c ≤ 1 such that for b/k < f_c, QESTO's approximation ratio degrades to or below partitioned QAOA at matched depth; the empirical "one Bell pair per cut edge" rule corresponds to operating at or above f_c.

## Why it might work
(n/a)

## Smallest experiment
On small weighted Wang-tile / MaxCut graphs partitioned into two halves with k cut edges, sweep the Bell-pair budget b from k down to 0 (with a defined reuse-by-reset policy when b<k). At matched ansatz depth, measure approximation ratio and fraction of globally valid solutions vs b, and locate the critical fraction f_c.

## Baseline
Equally-partitioned QAOA with no distributed gates (the paper's own baseline) and monolithic QAOA at matched depth (expressivity ceiling).

## Metric
Approximation ratio (cost/optimal) and valid-solution fraction as a function of b/k; the threshold f_c; the depth at which QESTO ≥ partitioned-QAOA for each b.

## Failure modes
- Reuse-by-reset policy for b<k is not unique; results may be policy-dependent
- Small graphs solved optimally by all methods, washing out the threshold
- Advantage may turn out depth-driven rather than entanglement-driven (clean negative result, still informative)

## Expected runtime
Minutes on a laptop statevector simulator (≤10 qubits, small graphs).
