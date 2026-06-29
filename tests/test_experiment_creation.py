"""Experiment build -> run -> results, plus idea/source-citation rules + approval gate."""

from __future__ import annotations

import json
from pathlib import Path

from researcher_mcp.tools import experiment_tools, idea_tools, paper_tools, runner_tools


def _make_idea(mock_client) -> str:
    paper_tools.ingest_paper("2606.01234", client=mock_client)
    res = idea_tools.create_idea(
        title="Depth vs VQE convergence on TFIM",
        hypothesis="Deeper ansatz lowers energy error on the small TFIM.",
        source_arxiv_ids=["2606.01234"],
        baseline="untrained ansatz", metric="energy_error", feasibility_score=4.0,
    )
    assert "error" not in res
    return res["id"]


def test_idea_requires_source_paper():
    res = idea_tools.create_idea("t", "h", [])
    assert "error" in res and "source" in res["error"].lower()


def test_experiment_folder_has_required_files(mock_client):
    idea_id = _make_idea(mock_client)
    built = experiment_tools.create_experiment_from_idea(idea_id, mode="small")
    assert "error" not in built
    folder = Path(built["folder_path"])
    for rel in ("experiment.yaml", "hypothesis.md", "related_papers.json", "plan.md",
                "src/run.py", "tests/test_smoke.py", "configs/config.json",
                "results/metrics.json", "report.md", "validator_notes.md"):
        assert (folder / rel).exists(), f"missing {rel}"
    # related_papers cites the source
    related = json.loads((folder / "related_papers.json").read_text())
    assert related[0]["arxiv_id"] == "2606.01234"
    # config pins a seed + runtime limit
    cfg = json.loads((folder / "configs" / "config.json").read_text())
    assert "seed" in cfg and cfg["runtime_limit_seconds"] <= 60


def test_run_then_results_and_metrics(mock_client):
    idea_id = _make_idea(mock_client)
    built = experiment_tools.create_experiment_from_idea(idea_id, mode="small")
    run = runner_tools.run_experiment(built["experiment_id"], mode="small")
    assert run["status"] == "completed", run
    m = run["metrics"]
    assert m["vqe_energy"] >= m["exact_energy"] - 1e-6  # variational bound
    assert m["energy_error"] >= 0.0
    assert m["parameter_count"] == m["ansatz_layers"] * m["n_spins"]

    results = runner_tools.get_experiment_results(built["experiment_id"])
    assert results["status"] == "completed"
    assert results["metrics"]["energy_error"] == m["energy_error"]


def test_tensor_network_idea_selects_tensor_template_and_runs(mock_client):
    paper_tools.ingest_paper("2606.01234", client=mock_client)
    res = idea_tools.create_idea(
        title="Parameter efficiency of a tensor-network-structured ansatz",
        hypothesis=(
            "A tensor-network-structured ansatz reaches lower TFIM energy error than a "
            "hardware-efficient ansatz at equal parameter count."
        ),
        source_arxiv_ids=["2606.01234"],
        smallest_experiment=(
            "Compare a structured MPS-style ansatz against a hardware-efficient ansatz "
            "at equal parameter count on a 3-site TFIM."
        ),
        baseline="matched-parameter hardware-efficient ansatz",
        metric="energy_error and structured_vs_hardware_delta",
        feasibility_score=4.5,
    )
    assert "error" not in res

    built = experiment_tools.create_experiment_from_idea(res["id"], mode="small")
    assert "error" not in built
    folder = Path(built["folder_path"])
    cfg = json.loads((folder / "configs" / "config.json").read_text())
    assert cfg["template"] == "tensor_network_ansatz"

    run = runner_tools.run_experiment(built["experiment_id"], mode="small")
    assert run["status"] == "completed", run
    m = run["metrics"]
    assert m["parameter_count_matched"] is True
    assert m["structured_parameter_count"] == m["hardware_parameter_count"]
    assert m["vqe_energy"] >= m["exact_energy"] - 1e-6
    assert "structured_vs_hardware_delta" in m


def test_gpu_mode_needs_approval(mock_client):
    idea_id = _make_idea(mock_client)
    built = experiment_tools.create_experiment_from_idea(idea_id, mode="small")
    blocked = runner_tools.run_experiment(built["experiment_id"], mode="gpu")
    assert blocked["status"] == "needs_approval"
    # explicit approval lets it proceed
    ok = runner_tools.run_experiment(built["experiment_id"], mode="gpu", approve=True)
    assert ok["status"] == "completed"


def test_auto_run_in_builder(mock_client):
    idea_id = _make_idea(mock_client)
    built = experiment_tools.create_experiment_from_idea(idea_id, mode="small", auto_run=True)
    assert built["run_result"]["status"] == "completed"
