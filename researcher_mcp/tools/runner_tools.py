"""Safe local experiment runner.

MCP contracts: ``run_experiment``, ``get_experiment_results``.

Safety model (ARCHITECTURE.md §10 / CLAUDE.md §4):
* Only ``mode="small"`` CPU smoke runs are autonomous.
* ``medium`` / ``gpu`` / ``long`` and anything else require explicit approval
  (``approve=True`` or ``QRH_APPROVAL_GRANTED=1``); otherwise the runner returns
  ``status="needs_approval"`` WITHOUT executing anything.
* Hard wall-clock timeout (from the experiment config, capped by global config).
* The child process gets a secret-scrubbed environment and runs in its own
  experiment folder. No package installs, no network calls are performed by the
  runner itself.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_config
from ..logging_utils import get_logger
from ..storage import repository as repo
from ..storage.models import ExperimentRun, ExperimentStatus

log = get_logger("tools.runner")

# Absolute ceiling regardless of config (defense in depth).
HARD_TIMEOUT_CEILING = 600
APPROVAL_REQUIRED_MODES = {"medium", "long", "gpu", "large"}
_SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "ANTHROPIC", "OPENAI")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _scrubbed_env() -> dict[str, str]:
    """Pass through a minimal, secret-free environment to the child process."""
    return {
        k: v for k, v in os.environ.items()
        if not any(h in k.upper() for h in _SECRET_HINTS)
    }


def _read_metrics(folder: Path) -> dict:
    mp = folder / "results" / "metrics.json"
    if mp.exists():
        try:
            import json

            return json.loads(mp.read_text() or "{}")
        except (OSError, ValueError):
            return {}
    return {}


def run_experiment(experiment_id: str, mode: str = "small", *, approve: bool = False) -> dict:
    """Run an experiment's smoke script safely and record metrics + logs.

    Args:
        experiment_id: Experiment to run.
        mode: ``small`` runs autonomously; other modes need approval.
        approve: Explicit one-call approval for a non-``small`` mode.

    Returns:
        ``{experiment_id, run_id, status, metrics, logs_path, error,
        approval_required_for?}``.
    """
    cfg = get_config()
    exp = repo.get_experiment(experiment_id)
    if exp is None:
        return {"error": f"experiment {experiment_id} not found"}
    if not exp.folder_path or not Path(exp.folder_path).exists():
        return {"error": f"experiment folder missing for {experiment_id}"}

    folder = Path(exp.folder_path)
    run_py = folder / "src" / "run.py"
    if not run_py.exists():
        return {"error": f"run.py missing in {folder}"}

    # --- approval gate -------------------------------------------------------
    needs_approval = mode in APPROVAL_REQUIRED_MODES
    if needs_approval and not (approve or cfg.approval_granted):
        log.info("run_experiment(%s) blocked: mode '%s' needs approval", experiment_id, mode)
        return {
            "experiment_id": experiment_id,
            "status": "needs_approval",
            "approval_required_for": sorted(APPROVAL_REQUIRED_MODES),
            "message": (
                f"mode '{mode}' requires approval. Re-run with approve=True or set "
                f"QRH_APPROVAL_GRANTED=1. Small CPU smoke runs are autonomous."
            ),
        }

    # --- timeout -------------------------------------------------------------
    import json

    config = {}
    if exp.config_path and Path(exp.config_path).exists():
        try:
            config = json.loads(Path(exp.config_path).read_text())
        except (OSError, ValueError):
            config = {}
    timeout = min(
        int(config.get("runtime_limit_seconds", cfg.experiment_timeout_seconds)),
        cfg.experiment_timeout_seconds,
        HARD_TIMEOUT_CEILING,
    )

    run_id = f"{experiment_id}_run_{uuid.uuid4().hex[:8]}"
    logs_path = folder / "results" / "logs" / f"{run_id}.log"
    logs_path.parent.mkdir(parents=True, exist_ok=True)

    run = ExperimentRun(
        id=run_id, experiment_id=experiment_id, status="running", started_at=_now()
    )
    repo.upsert_run(run)
    repo.update_experiment_status(experiment_id, ExperimentStatus.RUNNING.value)

    t0 = time.time()
    error: str | None = None
    status = "completed"
    stdout = stderr = ""
    try:
        proc = subprocess.run(
            [sys.executable, str(run_py)],
            cwd=str(folder),
            env=_scrubbed_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout, stderr = proc.stdout, proc.stderr
        if proc.returncode != 0:
            status = "failed"
            error = f"exit code {proc.returncode}"
    except subprocess.TimeoutExpired:
        status = "failed"
        error = f"timeout after {timeout}s (hard limit)"
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        error = str(exc)

    runtime = round(time.time() - t0, 3)
    logs_path.write_text(
        f"# run {run_id}\n# status={status} runtime={runtime}s timeout={timeout}s\n"
        f"\n## STDOUT\n{stdout}\n\n## STDERR\n{stderr}\n"
        + (f"\n## ERROR\n{error}\n" if error else ""),
        encoding="utf-8",
    )

    metrics = _read_metrics(folder) if status == "completed" else {}
    run.status = status
    run.finished_at = _now()
    run.metrics = metrics
    run.logs_path = str(logs_path)
    run.error_message = error
    repo.upsert_run(run)

    if status == "failed":
        repo.update_experiment_status(experiment_id, ExperimentStatus.FAILED.value)
    # On success the experiment stays in RUNNING (= "executed, awaiting
    # validation"); the validator promotes it to validated/rejected.

    log.info("run_experiment(%s) -> %s in %ss", experiment_id, status, runtime)
    return {
        "experiment_id": experiment_id, "run_id": run_id, "status": status,
        "metrics": metrics, "logs_path": str(logs_path), "runtime_seconds": runtime,
        "error": error,
    }


def get_experiment_results(experiment_id: str) -> dict:
    """Return the latest run's status, metrics, and log path for an experiment."""
    exp = repo.get_experiment(experiment_id)
    if exp is None:
        return {"error": f"experiment {experiment_id} not found"}
    latest = repo.latest_run(experiment_id)
    if latest is None:
        return {"experiment_id": experiment_id, "status": "no_runs", "metrics": {}}
    return {
        "experiment_id": experiment_id,
        "run_id": latest.id,
        "status": latest.status,
        "metrics": latest.metrics,
        "logs_path": latest.logs_path,
        "error": latest.error_message,
        "finished_at": latest.finished_at,
    }
