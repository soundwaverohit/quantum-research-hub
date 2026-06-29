# Idea — Symmetry-sector trainability bounds the classical MPS bond dimension needed to certify a VQE ground state

**Status:** proposed ·
**Novelty:** 3.3 · **Feasibility:** 3.5 ·
**Compute:** small

## Source papers
- [2606.05719](https://arxiv.org/abs/2606.05719)
- [2606.04771](https://arxiv.org/abs/2606.04771)

## Observation
2606.05719 links a symmetry-segmented Hilbert space to overparametrization/trainability via DLA dimension and QFIM rank; 2606.04771 shows symmetry-compressed MPS can certify many-body states at dramatically reduced effective bond dimension.

## Hypothesis
For a symmetry-respecting HVA-VQE ground state in a fixed invariant sector, the minimal MPS bond dimension χ* needed to reproduce the converged state to fidelity ≥0.99 is predicted by that sector's DLA dimension/entanglement and correlates with the overparametrization threshold M*: the same symmetry that makes the ansatz trainable (per 2606.05719) simultaneously caps the classical bond dimension needed to certify it (per 2606.04771). A non-symmetry-respecting ansatz of equal parameter count yields a state with larger χ* at equal energy error.

## Why it might work
(n/a)

## Smallest experiment
On a small Z2 LGT or TFIM (≤10 qubits), run a symmetry-respecting HVA-VQE and a hardware-efficient ansatz to comparable energy error. Compress each converged statevector into an MPS and find the χ* giving fidelity ≥0.99. Correlate χ* with the sector DLA dimension and with the measured overparametrization threshold M*.

## Baseline
Hardware-efficient (non-symmetry) ansatz ground state at equal parameter count and equal energy error; exact ground state from ED as the fidelity reference.

## Metric
χ* (bond dimension for 0.99 fidelity) vs DLA dimension; correlation between χ* and M*; Δχ* between symmetry-respecting and hardware-efficient ansätze at matched energy error.

## Failure modes
- At small system size χ* saturates at full Schmidt rank, hiding the trend
- The fidelity-threshold choice (0.99) influences χ*
- Correlation confounded by system size; needs a small size-scan to disentangle

## Expected runtime
Tens of minutes on a laptop (≤10 qubits; ED plus SVD compression).
