"""Smoke test for the generated VQE experiment.

Runs the tiny VQE end-to-end and asserts the result is physically sane:
- a metrics file is produced,
- the variational energy never dips below the exact ground energy (a classic
  bug signature for statevector code),
- the optimizer does at least as well as the untrained-ansatz baseline.

Runs in well under a second. Invoked by the safe experiment runner and by the
project test suite.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_PY = ROOT / "src" / "run.py"
METRICS = ROOT / "results" / "metrics.json"


def _load_run_module():
    spec = importlib.util.spec_from_file_location("vqe_run", RUN_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_vqe_runs_and_is_physical():
    mod = _load_run_module()
    rc = mod.main()
    assert rc == 0
    assert METRICS.exists(), "metrics.json was not written"

    m = json.loads(METRICS.read_text())
    # Variational energy is an upper bound on the true ground energy.
    assert m["vqe_energy"] >= m["exact_energy"] - 1e-6, "energy below exact ground state (bug!)"
    # Optimizer should not be worse than an untrained ansatz.
    assert m["vqe_energy"] <= m["baseline_energy"] + 1e-6
    assert m["energy_error"] >= 0.0
    assert m["parameter_count"] == m["ansatz_layers"] * m["n_spins"]


if __name__ == "__main__":
    test_vqe_runs_and_is_physical()
    print("smoke test passed")
