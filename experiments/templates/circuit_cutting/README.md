# Template: `circuit_cutting` (planned)

Placeholder for a future circuit_cutting experiment template. Until it ships, the experiment
builder selects the runnable `vqe_baseline` template (a tiny TFIM-VQE) as a
controlled proxy and records the chosen template in `plan.md`/`experiment.yaml`.

See `experiments/templates/vqe_baseline/` for the reference implementation
(baseline + exact diagonalization + seeded optimizer + smoke test).
