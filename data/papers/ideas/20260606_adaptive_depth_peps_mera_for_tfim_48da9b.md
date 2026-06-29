# Idea — Adaptive-depth PEPS-MERA for TFIM

**Status:** proposed ·
**Novelty:** 3.5 · **Feasibility:** 4.0 ·
**Compute:** small

## Source papers
- [2406.01234](https://arxiv.org/abs/2406.01234)

## Observation
The paper reports adaptive depth helps on small Ising models.

## Hypothesis
Adaptive MERA layers on top of short-range PEPS reduce energy error at fixed parameter count.

## Why it might work
MERA captures longer-range correlations cheaply.

## Smallest experiment
VQE on 3-site TFIM, compare to untrained baseline + exact.

## Baseline
Untrained ansatz (random parameters).

## Metric
energy_error vs exact.

## Failure modes
- barren plateau
- optimizer stuck in local minimum

## Expected runtime
< 1 minute
