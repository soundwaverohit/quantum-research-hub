"""Smoke test for the tensor-network ansatz template."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_PY = ROOT / "src" / "run.py"
METRICS = ROOT / "results" / "metrics.json"


def _load_run_module():
    spec = importlib.util.spec_from_file_location("tensor_run", RUN_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tensor_network_ansatz_runs_and_is_physical():
    mod = _load_run_module()
    rc = mod.main()
    assert rc == 0
    assert METRICS.exists(), "metrics.json was not written"

    m = json.loads(METRICS.read_text())
    assert m["parameter_count_matched"] is True
    assert m["structured_parameter_count"] == m["hardware_parameter_count"]
    assert m["parameter_count"] == m["structured_parameter_count"]
    assert m["vqe_energy"] >= m["exact_energy"] - 1e-6
    assert m["baseline_energy"] >= m["exact_energy"] - 1e-6
    assert m["energy_error"] >= 0.0
    assert m["baseline_error"] >= 0.0
    assert "structured_vs_hardware_delta" in m


if __name__ == "__main__":
    test_tensor_network_ansatz_runs_and_is_physical()
    print("smoke test passed")
