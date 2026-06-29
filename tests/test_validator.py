"""Validator/Critic: accepts good results, rejects bugs and missing baselines."""

from __future__ import annotations

import json
from pathlib import Path

from researcher_mcp.tools import experiment_tools, idea_tools, paper_tools, runner_tools


def _built_and_run(mock_client) -> dict:
    paper_tools.ingest_paper("2606.01234", client=mock_client)
    idea = idea_tools.create_idea(
        "TFIM VQE", "Ansatz reaches near-exact energy.", ["2606.01234"],
        baseline="untrained ansatz", metric="energy_error", feasibility_score=4.0,
    )
    built = experiment_tools.create_experiment_from_idea(idea["id"], mode="small")
    runner_tools.run_experiment(built["experiment_id"], mode="small")
    return built


def test_good_result_accepted(mock_client):
    built = _built_and_run(mock_client)
    res = experiment_tools.validate_experiment(built["experiment_id"])
    assert res["verdict"] == "accepted"
    assert res["status"] == "validated"
    assert all(res["checks"].values())
    # validator notes were written
    exp = experiment_tools.get_experiment(built["experiment_id"])
    assert "ACCEPTED" in exp["validator_notes"]


def test_below_exact_energy_rejected(mock_client):
    built = _built_and_run(mock_client)
    exp = experiment_tools.get_experiment(built["experiment_id"])
    metrics_path = Path(exp["experiment"]["result_path"])
    m = json.loads(metrics_path.read_text())
    m["vqe_energy"] = m["exact_energy"] - 1.0  # impossible -> bug
    metrics_path.write_text(json.dumps(m))

    res = experiment_tools.validate_experiment(built["experiment_id"])
    assert res["verdict"] == "rejected"
    assert res["checks"]["physical_bound_respected"] is False


def test_no_run_is_inconclusive(mock_client):
    paper_tools.ingest_paper("2606.01234", client=mock_client)
    idea = idea_tools.create_idea(
        "TFIM VQE", "h", ["2606.01234"], baseline="b", metric="energy_error", feasibility_score=3.0
    )
    built = experiment_tools.create_experiment_from_idea(idea["id"], mode="small")
    # never run it
    res = experiment_tools.validate_experiment(built["experiment_id"])
    assert res["verdict"] == "inconclusive"
