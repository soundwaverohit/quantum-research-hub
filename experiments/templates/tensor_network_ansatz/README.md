# Template: `tensor_network_ansatz`

Small CPU-only TFIM benchmark for tensor-network-structured ansatz ideas.

The experiment compares:

- `structured`: a nearest-neighbor Jastrow/MPS-style positive-amplitude ansatz
- `hardware_efficient`: a matched-parameter Ry + CX-chain ansatz

Both use `2 * n_spins - 1` trainable parameters. The primary metric is energy
error versus exact diagonalization, plus the matched-parameter delta:

```text
improvement_over_baseline = hardware_efficient_energy - structured_ansatz_energy
```

This is intentionally tiny and reproducible. It is a proxy for your
QPEPS-QMERA direction: test whether local tensor-network structure buys energy
accuracy at the same parameter count before scaling to richer ansatz families.
