# Template: `vqe_baseline`

A tiny, CPU-only, fully reproducible **VQE** experiment used as the default
runnable template for generated experiments.

**What it does**
- Builds a transverse-field Ising model (TFIM) on a short open chain (`n_spins`, default 3).
- Computes the **exact** ground energy by dense diagonalization (`numpy.linalg.eigvalsh`).
- Optimizes a hardware-efficient ansatz (`Ry` rotations + `CX` chain) with seeded,
  gradient-free random-restart coordinate descent.
- Compares against an **untrained-ansatz baseline** (best of many random parameter sets).
- Records seed stability across multiple seeds.

**Why it is safe**
- Matrices are `2^n x 2^n` with `n <= 5` → milliseconds of compute.
- No network, no GPU, no package installs, no quantum SDK.
- Hard wall-clock limit enforced by the runner (`runtime_limit_seconds`).

**Files**
- `run.py` — the experiment (reads `configs/config.json`, writes `results/metrics.json`).
- `test_smoke.py` — asserts the result is physically sane (variational bound, baseline check).
- `config.template.json` — default knobs; the experiment builder overrides per-idea values.

**Key metrics** (`results/metrics.json`)
`exact_energy`, `vqe_energy`, `baseline_energy`, `energy_error`, `baseline_error`,
`improvement_over_baseline`, `parameter_count`, `seed_stability_std`, `runtime_seconds`.

This template is generated and run by the orchestrator's Experiment Builder /
Runner agents and validated by the Validator/Critic agent.
