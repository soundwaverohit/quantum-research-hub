"""Central configuration for the Quantum Research Hub.

Everything path- or budget-related flows through :func:`get_config`. Values are
read from the environment (optionally via a local ``.env``) with local-first
defaults so the system runs with zero setup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:  # optional, but present in the recommended stack
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv is a listed dependency
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False


# Repo root = parent of the researcher_mcp package directory.
REPO_ROOT = Path(__file__).resolve().parent.parent


# --- Research focus -----------------------------------------------------------
# arXiv categories tracked by default (ARCHITECTURE.md §5.3).
DEFAULT_CATEGORIES: tuple[str, ...] = (
    "quant-ph",
    "cs.LG",
    "cs.ET",
    "physics.comp-ph",
    "cond-mat.str-el",
    "hep-lat",
)

# Keyword groups used for relevance scoring and topic clustering. Lower-cased;
# matching is done case-insensitively against title + abstract.
KEYWORD_GROUPS: dict[str, list[str]] = {
    "A_tensor_networks": [
        "tensor network", "tensor networks", "mps", "matrix product state",
        "peps", "mera", "tree tensor network", "tensor network state", "ttn",
    ],
    "B_vqe": [
        "vqe", "variational quantum eigensolver", "variational quantum algorithm",
        "variational quantum",
    ],
    "C_distributed": [
        "circuit cutting", "distributed quantum", "entanglement forging",
        "circuit knitting", "circuit knitting toolbox",
    ],
    "D_hamiltonian": [
        "hamiltonian simulation", "lattice gauge", "ising model", "heisenberg model",
        "lattice model", "trotter", "time evolution",
    ],
    "E_qml": [
        "quantum machine learning", "quantum feature map", "quantum kernel",
        "data re-uploading", "data reuploading", "quantum neural network",
    ],
    "F_mitigation": [
        "error mitigation", "measurement reduction", "shadow tomography",
        "classical shadow", "barren plateau", "zero-noise extrapolation",
    ],
}


# --- Budget profiles (ARCHITECTURE.md §5.5) -----------------------------------
@dataclass(frozen=True)
class BudgetProfile:
    name: str
    max_papers_per_day: int
    max_deep_summaries_per_day: int
    max_ideas_per_day: int
    max_experiments_created_per_day: int
    max_experiments_run_per_day: int
    max_claude_passes_per_day: int


BUDGET_PROFILES: dict[str, BudgetProfile] = {
    "low": BudgetProfile("low", 5, 2, 3, 0, 0, 3),
    "medium": BudgetProfile("medium", 15, 5, 8, 1, 1, 8),
    "high": BudgetProfile("high", 30, 10, 15, 2, 2, 15),
}


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (REPO_ROOT / p)


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    """Resolved, absolute configuration for one process."""

    repo_root: Path
    db_path: Path
    data_dir: Path
    experiments_dir: Path

    budget_profile: str
    arxiv_min_interval: float
    lookback_days: int
    arxiv_max_results: int

    experiment_timeout_seconds: int
    approval_granted: bool
    enable_model_pass: bool
    anthropic_api_key: str = field(repr=False)
    claude_model: str
    claude_max_tokens: int
    claude_timeout_seconds: float
    memory_backend: str

    categories: tuple[str, ...] = DEFAULT_CATEGORIES
    keyword_groups: dict[str, list[str]] = field(default_factory=lambda: dict(KEYWORD_GROUPS))

    # --- Derived artifact directories ---------------------------------------
    @property
    def schema_path(self) -> Path:
        return Path(__file__).resolve().parent / "storage" / "schema.sql"

    @property
    def pdf_dir(self) -> Path:
        return self.data_dir / "papers" / "pdfs"

    @property
    def parsed_dir(self) -> Path:
        return self.data_dir / "papers" / "parsed"

    @property
    def cards_dir(self) -> Path:
        return self.data_dir / "papers" / "cards"

    @property
    def ideas_dir(self) -> Path:
        return self.data_dir / "papers" / "ideas"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def datasets_dir(self) -> Path:
        """Output directory for exported first-principles training datasets."""
        return self.data_dir / "datasets"

    @property
    def daily_reports_dir(self) -> Path:
        return self.reports_dir / "daily"

    @property
    def experiment_runs_dir(self) -> Path:
        return self.experiments_dir / "runs"

    @property
    def budget(self) -> BudgetProfile:
        return BUDGET_PROFILES.get(self.budget_profile, BUDGET_PROFILES["low"])

    def ensure_dirs(self) -> None:
        """Create all artifact directories. Cheap and idempotent."""
        for d in (
            self.data_dir, self.pdf_dir, self.parsed_dir, self.cards_dir,
            self.ideas_dir, self.logs_dir, self.reports_dir, self.daily_reports_dir,
            self.reports_dir / "weekly", self.data_dir / "embeddings",
            self.datasets_dir,
            self.experiments_dir, self.experiment_runs_dir, self.db_path.parent,
        ):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Build the process Config from the environment (cached)."""
    # Load .env from repo root if present; never overrides already-set env vars.
    load_dotenv(REPO_ROOT / ".env")

    cfg = Config(
        repo_root=REPO_ROOT,
        db_path=_resolve(os.getenv("QRH_DB_PATH", "db/dev.sqlite3")),
        data_dir=_resolve(os.getenv("QRH_DATA_DIR", "data")),
        experiments_dir=_resolve(os.getenv("QRH_EXPERIMENTS_DIR", "experiments")),
        budget_profile=os.getenv("QRH_BUDGET_PROFILE", "low").strip().lower(),
        arxiv_min_interval=float(os.getenv("QRH_ARXIV_MIN_INTERVAL", "3.0")),
        lookback_days=int(os.getenv("QRH_LOOKBACK_DAYS", "2")),
        arxiv_max_results=int(os.getenv("QRH_ARXIV_MAX_RESULTS", "50")),
        experiment_timeout_seconds=int(os.getenv("QRH_EXPERIMENT_TIMEOUT_SECONDS", "60")),
        approval_granted=_env_bool("QRH_APPROVAL_GRANTED", False),
        enable_model_pass=_env_bool("QRH_ENABLE_MODEL_PASS", False),
        anthropic_api_key=(
            os.getenv("QRH_ANTHROPIC_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or ""
        ).strip(),
        claude_model=os.getenv("QRH_CLAUDE_MODEL", "claude-sonnet-4-5").strip(),
        claude_max_tokens=int(os.getenv("QRH_CLAUDE_MAX_TOKENS", "1800")),
        claude_timeout_seconds=float(os.getenv("QRH_CLAUDE_TIMEOUT_SECONDS", "60")),
        memory_backend=os.getenv("QRH_MEMORY_BACKEND", "vector").strip().lower(),
    )
    return cfg


def reset_config_cache() -> None:
    """Clear the cached config (used by tests that override env/paths)."""
    get_config.cache_clear()
