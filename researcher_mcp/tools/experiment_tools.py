"""Experiment registry tools: build, inspect, and validate experiments.

MCP contracts: ``create_experiment_from_idea``, ``get_experiment``,
``list_experiments``, ``validate_experiment``.

Every experiment folder follows ARCHITECTURE.md §5.4 and always contains a
baseline, a config (seed + runtime limit), tests, metric logging, and a
validator note — no experiment is valid without a baseline.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ..config import get_config
from ..logging_utils import get_logger
from ..storage import repository as repo
from ..storage.models import (
    Experiment,
    ExperimentStatus,
    IdeaStatus,
    ValidatorVerdict,
)

log = get_logger("tools.experiment")

EXPERIMENT_SUBDIRS = ("src", "tests", "configs", "results", "results/plots", "results/logs")


def _slug(text: str, max_len: int = 32) -> str:
    import re

    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return (s[:max_len] or "exp").strip("_")


def _templates_dir() -> Path:
    return get_config().experiments_dir / "templates"


def select_template(idea) -> str:  # noqa: ANN001 - Idea model
    """Pick an experiment template for an idea.

    Tensor-network ansatz ideas get the dedicated matched-parameter template.
    Other ideas keep using the generic VQE baseline until their topic-specific
    templates are implemented.
    """
    text = " ".join([
        getattr(idea, "title", ""),
        getattr(idea, "hypothesis", ""),
        getattr(idea, "observation", ""),
        getattr(idea, "smallest_experiment", ""),
        getattr(idea, "why_it_might_work", ""),
    ]).lower()
    tensor_markers = (
        "tensor network",
        "tensor-network",
        "mps",
        "matrix product",
        "peps",
        "mera",
        "qpeps",
        "qmera",
        "structured ansatz",
        "parameter efficiency",
    )
    if any(marker in text for marker in tensor_markers):
        return "tensor_network_ansatz"
    return "vqe_baseline"


def _next_run_id(slug: str) -> str:
    base = f"{date.today():%Y%m%d}_{slug}"
    runs_dir = get_config().experiment_runs_dir
    runs_dir.mkdir(parents=True, exist_ok=True)
    n = 1
    while (runs_dir / f"{base}_{n:03d}").exists():
        n += 1
    return f"{base}_{n:03d}"


def create_experiment_from_idea(
    idea_id: str, mode: str = "small", auto_run: bool = False
) -> dict:
    """Create a reproducible experiment folder from an idea.

    Args:
        idea_id: Source idea id (must exist and cite source papers).
        mode: ``small`` (default, CPU smoke) or ``medium`` (needs approval to run).
        auto_run: If true, immediately run the smoke experiment (``small`` only,
            still subject to runner approval gates).

    Returns:
        ``{experiment_id, folder_path, status, approval_required, run_result?}``
        or ``{"error": ...}``.
    """
    idea = repo.get_idea(idea_id)
    if idea is None:
        return {"error": f"idea {idea_id} not found"}
    if not idea.source_arxiv_ids:
        return {"error": "idea has no source papers; cannot build an experiment"}

    cfg = get_config()
    template = select_template(idea)
    tdir = _templates_dir() / template
    if not (tdir / "run.py").exists():
        return {"error": f"template '{template}' is missing run.py at {tdir}"}

    exp_id = _next_run_id(_slug(idea.title))
    folder = cfg.experiment_runs_dir / exp_id
    for sub in EXPERIMENT_SUBDIRS:
        (folder / sub).mkdir(parents=True, exist_ok=True)

    # 1) code + tests (verbatim from template)
    shutil.copy(tdir / "run.py", folder / "src" / "run.py")
    shutil.copy(tdir / "test_smoke.py", folder / "tests" / "test_smoke.py")

    # 2) config (template defaults, with seed + runtime limit pinned)
    config = json.loads((tdir / "config.template.json").read_text())
    config["seed"] = config.get("seed", 7)
    config["allowed_compute_mode"] = "small" if mode not in ("small", "medium") else mode
    config["runtime_limit_seconds"] = min(
        int(config.get("runtime_limit_seconds", 60)), cfg.experiment_timeout_seconds
    )
    config_path = folder / "configs" / "config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    # 3) experiment.yaml metadata (ARCHITECTURE.md §5.4)
    meta = {
        "id": exp_id,
        "title": idea.title,
        "status": ExperimentStatus.PROPOSED.value,
        "hypothesis": idea.hypothesis,
        "template": template,
        "source_papers": [f"arXiv:{s}" for s in idea.source_arxiv_ids],
        "baselines": [idea.baseline or "untrained ansatz (random parameters)"],
        "metrics": ["energy_error", "baseline_error", "improvement_over_baseline",
                     "parameter_count", "seed_stability_std", "runtime_seconds"],
        "allowed_compute_mode": config["allowed_compute_mode"],
        "approval_required_for": [
            "gpu", "runtime_over_10_minutes", "package_install", "external_api_spend",
        ],
        "random_seed": config["seed"],
        "runtime_limit_seconds": config["runtime_limit_seconds"],
    }
    (folder / "experiment.yaml").write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")

    # 4) hypothesis.md
    (folder / "hypothesis.md").write_text(
        f"# Hypothesis\n\n{idea.hypothesis}\n\n"
        f"## Observation\n{idea.observation or '(n/a)'}\n\n"
        f"## Why it might work\n{idea.why_it_might_work or '(n/a)'}\n",
        encoding="utf-8",
    )

    # 5) related_papers.json (source ids + titles from DB)
    related = []
    for aid in idea.source_arxiv_ids:
        p = repo.get_paper(aid)
        related.append({
            "arxiv_id": aid,
            "title": p.title if p else None,
            "url": f"https://arxiv.org/abs/{aid}",
        })
    (folder / "related_papers.json").write_text(json.dumps(related, indent=2), encoding="utf-8")

    # 6) plan.md
    fm = "\n".join(f"- {m}" for m in idea.failure_modes) or "- (none listed)"
    (folder / "plan.md").write_text(
        f"# Plan — {idea.title}\n\n"
        f"**Template:** `{template}`  ·  **Mode:** {config['allowed_compute_mode']}  ·  "
        f"**Seed:** {config['seed']}  ·  **Runtime limit:** {config['runtime_limit_seconds']}s\n\n"
        f"## Smallest experiment\n{idea.smallest_experiment or 'Run the template VQE and compare to baseline + exact.'}\n\n"
        f"## Baseline\n{idea.baseline or 'Untrained ansatz (best of random parameter sets).'}\n\n"
        f"## Metric\n{idea.metric or 'energy_error vs exact diagonalization; improvement over baseline.'}\n\n"
        f"## Failure modes\n{fm}\n\n"
        f"## Steps\n"
        f"1. Build the TFIM Hamiltonian and compute the exact ground energy.\n"
        f"2. Optimize the ansatz (seeded) and record the variational energy.\n"
        f"3. Compare against the untrained-ansatz baseline.\n"
        f"4. Check seed stability across multiple seeds.\n"
        f"5. Validate: physical bound, baseline improvement, reproducibility.\n",
        encoding="utf-8",
    )

    # 7-9) placeholders for results/report/validator
    (folder / "results" / "metrics.json").write_text("{}\n", encoding="utf-8")
    (folder / "report.md").write_text(
        f"# Experiment Report — {idea.title}\n\n*Status: proposed. "
        f"Run the experiment to populate metrics.*\n", encoding="utf-8"
    )
    validator_path = folder / "validator_notes.md"
    validator_path.write_text("# Validator Notes\n\nStatus: pending (experiment not yet run).\n", encoding="utf-8")

    # 10) DB row
    exp = Experiment(
        id=exp_id, idea_id=idea.id, title=idea.title, hypothesis=idea.hypothesis,
        status=ExperimentStatus.PROPOSED,
        folder_path=str(folder), config_path=str(config_path),
        result_path=str(folder / "results" / "metrics.json"),
        validator_notes_path=str(validator_path),
    )
    repo.upsert_experiment(exp)
    repo.update_idea_status(idea.id, IdeaStatus.PROMOTED.value)
    log.info("Built experiment %s from idea %s", exp_id, idea.id)

    result: dict[str, Any] = {
        "experiment_id": exp_id,
        "folder_path": str(folder),
        "status": ExperimentStatus.PROPOSED.value,
        # Small CPU smoke runs are autonomous; medium+ require approval.
        "approval_required": mode != "small",
    }
    if auto_run:
        from . import runner_tools  # lazy import avoids a module cycle

        result["run_result"] = runner_tools.run_experiment(exp_id, mode=mode)
    return result


def _read_json(path: Path | str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text() or "{}")
    except (OSError, ValueError):
        return {}


def get_experiment(experiment_id: str) -> dict:
    """Return full experiment detail: metadata, config, latest metrics, validator note."""
    exp = repo.get_experiment(experiment_id)
    if exp is None:
        return {"error": f"experiment {experiment_id} not found"}
    folder = Path(exp.folder_path) if exp.folder_path else None
    metrics = _read_json(exp.result_path)
    latest = repo.latest_run(experiment_id)
    files = (
        sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())
        if folder and folder.exists() else []
    )
    validator_note = ""
    if exp.validator_notes_path and Path(exp.validator_notes_path).exists():
        validator_note = Path(exp.validator_notes_path).read_text(encoding="utf-8")
    return {
        "experiment": exp.model_dump(mode="json"),
        "config": _read_json(exp.config_path),
        "metrics": metrics or (latest.metrics if latest else {}),
        "latest_run": latest.model_dump(mode="json") if latest else None,
        "files": files,
        "validator_notes": validator_note,
    }


def _verdict_for_status(status: str) -> str:
    return {
        "validated": "accepted",
        "rejected": "rejected",
    }.get(status, "inconclusive")


def list_experiments(status: str | None = None, limit: int = 100) -> dict:
    """List experiments with their latest metric + validator verdict."""
    exps = repo.list_experiments(status=status, limit=limit)
    out = []
    for e in exps:
        metrics = _read_json(e.result_path)
        latest = repo.latest_run(e.id)
        st = str(getattr(e.status, "value", e.status))
        out.append({
            "id": e.id, "title": e.title, "status": st,
            "baseline": "untrained ansatz (random parameters)",
            "metric": "energy_error",
            "best_result": metrics.get("energy_error"),
            "improvement_over_baseline": metrics.get("improvement_over_baseline"),
            "validator_verdict": _verdict_for_status(st),
            "last_run": latest.finished_at if latest else None,
        })
    return {"count": len(out), "experiments": out}


# =============================================================================
# Validation (MCP contract: validate_experiment)
# =============================================================================
def validate_experiment(experiment_id: str, *, rel_error_threshold: float = 0.05) -> dict:
    """Skeptically review an experiment and assign a verdict.

    Verdicts: ``accepted`` | ``rejected`` | ``inconclusive``. Writes a
    checklist to ``validator_notes.md`` and updates the experiment status.
    """
    exp = repo.get_experiment(experiment_id)
    if exp is None:
        return {"error": f"experiment {experiment_id} not found"}

    folder = Path(exp.folder_path) if exp.folder_path else None
    config = _read_json(exp.config_path)
    metrics = _read_json(exp.result_path)
    latest = repo.latest_run(experiment_id)
    ran_ok = bool(latest and latest.status == "completed")

    checks: dict[str, bool] = {
        "folder_exists": bool(folder and folder.exists()),
        "config_exists": bool(config),
        "code_ran": ran_ok,
        "metrics_saved": bool(metrics),
        "seed_fixed": "seed" in config,
        "baseline_present": "baseline_energy" in metrics,
        "comparison_fair": "improvement_over_baseline" in metrics,
    }

    notes: list[str] = []
    verdict = ValidatorVerdict.INCONCLUSIVE

    if not ran_ok or not metrics:
        verdict = ValidatorVerdict.INCONCLUSIVE
        notes.append("No successful run with saved metrics yet; cannot validate.")
    else:
        exact = metrics.get("exact_energy")
        vqe = metrics.get("vqe_energy")
        err = metrics.get("energy_error")
        improvement = metrics.get("improvement_over_baseline", 0.0)

        # Bug check: a variational energy below the exact ground state is impossible.
        below_exact = exact is not None and vqe is not None and vqe < exact - 1e-6
        checks["physical_bound_respected"] = not below_exact

        rel_err = (abs(err) / abs(exact)) if (err is not None and exact) else None
        meaningful = rel_err is not None and rel_err <= rel_error_threshold
        improved = improvement is not None and improvement > 1e-6
        checks["improves_on_baseline"] = improved
        checks["meaningful_accuracy"] = bool(meaningful)

        if below_exact:
            verdict = ValidatorVerdict.REJECTED
            notes.append(f"Variational energy {vqe} is below exact ground {exact}: likely a bug.")
        elif not checks["baseline_present"]:
            verdict = ValidatorVerdict.REJECTED
            notes.append("No baseline recorded; a result without a baseline is not valid.")
        elif meaningful and improved:
            verdict = ValidatorVerdict.ACCEPTED
            notes.append(
                f"Relative energy error {rel_err:.3%} <= {rel_error_threshold:.0%} and the "
                f"optimizer improves on baseline by {improvement:.4f}."
            )
        else:
            verdict = ValidatorVerdict.INCONCLUSIVE
            reasons = []
            if not meaningful:
                rel_str = f"{rel_err:.3%}" if rel_err is not None else "unknown"
                reasons.append(f"relative error {rel_str} above threshold")
            if not improved:
                reasons.append("no improvement over baseline")
            notes.append("Result is plausible but not decisive: " + "; ".join(reasons) + ".")

    next_test = (
        "Increase ansatz_layers by 1 and re-check whether energy_error drops, "
        "then scale n_spins from 3 to 4 to confirm the trend holds."
    )

    # Persist validator note + update status.
    checklist = "\n".join(f"- [{'x' if v else ' '}] {k.replace('_', ' ')}" for k, v in checks.items())
    note_md = (
        f"# Validator Notes — {exp.title}\n\n"
        f"**Verdict: {verdict.value.upper()}**\n\n"
        f"## Checks\n{checklist}\n\n"
        f"## Reasoning\n" + "\n".join(f"- {n}" for n in notes) + "\n\n"
        f"## Simplest next test\n{next_test}\n"
    )
    if exp.validator_notes_path:
        Path(exp.validator_notes_path).write_text(note_md, encoding="utf-8")

    new_status = {
        ValidatorVerdict.ACCEPTED: ExperimentStatus.VALIDATED.value,
        ValidatorVerdict.REJECTED: ExperimentStatus.REJECTED.value,
    }.get(verdict, exp.status if isinstance(exp.status, str) else exp.status.value)
    repo.update_experiment_status(experiment_id, new_status)

    return {
        "experiment_id": experiment_id,
        "verdict": verdict.value,
        "checks": checks,
        "notes": notes,
        "next_test": next_test,
        "status": new_status,
    }
