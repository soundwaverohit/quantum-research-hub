# ⚛️ Quantum Research Hub

A **local-first, MCP-powered autonomous research system** for quantum computing.
It watches arXiv, builds compact paper memory, proposes small testable ideas,
generates and runs bounded experiments, validates the results skeptically, and
shows everything in a dashboard — all under a budget, with every agent action
logged.

> Every day it answers: *what changed in quantum computing, which papers matter,
> what ideas are worth testing, and what the agents actually tried.*

This is a **functional MVP**, not a skeleton: arXiv search is real (with a clean
injectable adapter for tests), the experiment engine runs a genuine tiny VQE
against exact diagonalization, and the validator can reject results.

---

## Highlights

- **Researcher MCP server** (FastMCP) exposing 17 bounded tools to Claude Code.
- **Real arXiv ingestion** (`httpx` + `feedparser`) -> compact **paper cards**
  with deterministic fallback and an optional Claude model pass.
- **SQLite** storage for papers, chunks, ideas, experiments, runs, agent events,
  and budget events.
- **Local vector paper-memory search** using dependency-free hashed embeddings
  (`QRH_MEMORY_BACKEND=bm25|hybrid` remains available).
- **Orchestrator + 8 agents**: Paper Scout, Summarizer, Curator, Idea Generator,
  Experiment Builder, Runner, Validator/Critic, Reporter.
- **Daily run** under `low`/`medium`/`high` budget profiles -> daily report;
  scheduler can also write weekly reports.
- **Real experiment engine**: tiny TFIM **VQE** and
  **tensor-network-structured ansatz** templates (numpy), run in a
  **sandboxed, timeout-bounded, approval-gated** subprocess.
- **Dashboard**: Overview, Papers, Ideas, Experiments, Agent Logs, Budget, Reports —
  available as a **zero-dependency stdlib HTTP app** (recommended, always runs) and
  as a Streamlit app.
- **Safety first**: small CPU smoke runs are autonomous; installs/GPU/long jobs
  require approval; secrets are scrubbed from experiment subprocesses; ideas must
  cite source papers; no experiment is valid without a baseline.

---

## Quickstart

The whole MVP runs on a lightweight stack (`mcp`, `pydantic`, `httpx`,
`feedparser`, `numpy`, `pandas`, `streamlit`, `pyyaml`). `pypdf` is **optional**
(full-text parsing only) — the MVP works without it.

### Option A — uv (recommended)
```bash
uv sync
cp .env.example .env
uv run python -m researcher_mcp.storage.db init
uv run python scripts/seed_demo.py            # demo data so the dashboard is populated
uv run python -m orchestrator.daily_run --profile low
uv run python -m apps.dashboard.server        # dashboard → http://127.0.0.1:8533
uv run pytest
```

### Option B — pip / existing interpreter
```bash
python -m pip install -e ".[dev]"
cp .env.example .env
python -m researcher_mcp.storage.db init
python scripts/seed_demo.py
python -m orchestrator.daily_run --profile low
python -m apps.dashboard.server               # dashboard → http://127.0.0.1:8533
python -m pytest
```

### Option C — one shot
```bash
scripts/bootstrap.sh        # installs deps, makes .env, inits + seeds the DB
scripts/run_daily.sh --profile low
scripts/dev.sh              # seed + launch the dashboard
```

> The shell scripts default to `python3`; override with `PYTHON="uv run python" scripts/run_daily.sh`.

---

## How to run each piece

| Action | Command |
|---|---|
| **Initialize the DB** | `python -m researcher_mcp.storage.db init` |
| **DB status / reset** | `python -m researcher_mcp.storage.db status` · `… reset --yes` |
| **Seed demo data** | `python scripts/seed_demo.py` |
| **Daily research run** | `python -m orchestrator.daily_run --profile low` |
| **Daily run (full pipeline w/ experiment)** | `python -m orchestrator.daily_run --profile medium` |
| **Daily run (no network/demo)** | `python -m orchestrator.daily_run --profile low --offline` |
| **Weekly report** | `python -m orchestrator.scheduler weekly --profile low` |
| **Scheduler loop** | `python -m orchestrator.scheduler loop --profile low --weekly` |
| **Dashboard (recommended, zero deps)** | `python -m apps.dashboard.server` → http://127.0.0.1:8533 |
| **Dashboard (Streamlit)** | `streamlit run apps/dashboard/Home.py` → http://localhost:8501 |
| **MCP server** | `python -m researcher_mcp.server` (stdio) |
| **Tests** | `python -m pytest` |

> **Dashboard note:** the stdlib dashboard (`python -m apps.dashboard.server`) has
> zero third-party dependencies and always runs. The Streamlit dashboard is
> equivalent but imports `pyarrow`; if your Python env has a `pyarrow` built for a
> different NumPy major version (a common conda/pip mismatch), Streamlit will fail
> to import. A clean `uv sync` avoids this, or use the stdlib dashboard.

### Budget profiles
| profile | papers/day | ideas/day | experiments created | experiments run |
|---|---|---|---|---|
| `low` | 5 | 3 | **0** | **0** |
| `medium` | 15 | 8 | 1 | 1 |
| `high` | 30 | 15 | 2 | 2 |

> On `low`, the pipeline discovers/ingests/ranks/ideates but **does not create or
> run experiments** (cap 0) — by design. Use `--profile medium` to exercise the
> full build → run → validate flow. The seed script uses `medium`.

---

## Using the MCP server from Claude Code

Add the server to Claude Code (stdio). Example `.mcp.json` / client config:

```json
{
  "mcpServers": {
    "quantum-research-hub": {
      "command": "python",
      "args": ["-m", "researcher_mcp.server"],
      "cwd": "/absolute/path/to/this/repo"
    }
  }
}
```

Tools exposed: `search_arxiv`, `ingest_paper`, `get_paper_card`,
`search_paper_memory`, `list_recent_papers`, `create_idea`, `list_ideas`,
`create_experiment_from_idea`, `get_experiment`, `list_experiments`,
`run_experiment`, `get_experiment_results`, `validate_experiment`,
`create_daily_report`, `create_weekly_report`, `get_budget_status`, `get_overview`.

Subagent definitions live in `.claude/agents/` (paper-scout, curator,
idea-generator, experiment-builder, validator, reporter, architect,
test-engineer, plus paper-summarizer, experiment-runner, dashboard-builder,
mcp-server-engineer).

---

## Safety & approval model

**Autonomous:** arXiv search, paper-card creation, ranking, idea generation,
experiment-folder creation, unit/smoke tests, short CPU runs, dashboard/DB updates.

**Requires approval** (returns `needs_approval`, does nothing): package installs,
GPU, jobs > the configured timeout / `medium`+ runner modes, cloud/paid APIs,
deleting files outside `data/` and `experiments/runs/`, changing safety logic.

**Hard rules:** every idea cites ≥1 source paper; every experiment has a baseline,
metric, seed, and validator note; the variational energy can never drop below the
exact ground state (flagged as a bug); experiment subprocesses get a
secret-scrubbed environment and a hard wall-clock timeout.

Set `QRH_APPROVAL_GRANTED=1` (or pass `approve=True` to `run_experiment`) to allow
a single non-`small` run when you have reviewed it.

---

## Project layout

```
researcher_mcp/        # MCP server + tools + ingestion + storage (the capability layer)
  server.py            # FastMCP server (python -m researcher_mcp.server)
  config.py            # paths, budget profiles, categories, keyword groups
  tools/               # arxiv, paper, memory, idea, experiment, runner, budget, dashboard
  ingest/              # arxiv_client, paper_card, chunker, pdf_* (optional)
  storage/             # schema.sql, db.py, models.py (pydantic), repository.py, vector_store.py
orchestrator/          # the autonomous daily layer
  daily_run.py         # python -m orchestrator.daily_run --profile {low,medium,high}
  budget_manager.py    # enforces caps, records usage
  agent_router.py      # RunContext + pipeline
  reporting.py         # daily + weekly report builders
  agents/              # the 8 pipeline agents
apps/dashboard/        # server.py (stdlib HTTP, recommended) + Streamlit Home.py + pages/1..6
experiments/
  templates/vqe_baseline/          # runnable TFIM-VQE template
  templates/tensor_network_ansatz/ # runnable matched-parameter ansatz template
  runs/                            # generated experiment folders
scripts/               # bootstrap, dev, run_daily, reset_dev_db, run_tests, seed_demo
tests/                 # pytest (mocked network)
data/, db/             # artifacts + SQLite (gitignored)
.claude/agents/        # subagent definitions   .claude/settings.json
```

> **Layout note:** `researcher_mcp/` and `orchestrator/` are top-level packages
> (a flattened version of ARCHITECTURE.md's `services/...` tree) so every
> documented `python -m ...` command works from the repo root with no install.
> Module paths are identical to the architecture doc.

---

## What an experiment contains

Each `experiments/runs/<id>/` has: `experiment.yaml`, `hypothesis.md`,
`related_papers.json`, `plan.md`, `src/run.py`, `tests/test_smoke.py`,
`configs/config.json`, `results/metrics.json` (+ `logs/`, `plots/`), `report.md`,
`validator_notes.md`. Templates report `exact_energy`, `vqe_energy`,
`baseline_energy`, `energy_error`, `improvement_over_baseline`,
`parameter_count`, `seed_stability_std`, and `runtime_seconds`. The tensor
template also reports `structured_ansatz_energy`, `hardware_efficient_energy`,
and `structured_vs_hardware_delta`.

---

## Configuration (`.env`)

See `.env.example`. Common knobs: `QRH_DB_PATH`, `QRH_DATA_DIR`,
`QRH_BUDGET_PROFILE`, `QRH_LOOKBACK_DAYS`, `QRH_ARXIV_MIN_INTERVAL`,
`QRH_EXPERIMENT_TIMEOUT_SECONDS`, `QRH_APPROVAL_GRANTED`, and
`QRH_MEMORY_BACKEND`.

Optional Claude model pass:

```bash
export QRH_ENABLE_MODEL_PASS=1
export ANTHROPIC_API_KEY=...
export QRH_CLAUDE_MODEL=claude-sonnet-4-5
```

When disabled or unavailable, paper cards, ideas, and reports fall back to the
deterministic path. No secrets are required for the offline MVP.

---

## Limitations (MVP)

- The Claude model pass is optional and requires an Anthropic key.
- Circuit-cutting and QML templates are still stubs that fall back to the VQE
  template.
- The vector memory backend is a local hashed embedding index, not a persistent
  Chroma/FAISS store yet.
- Full-text PDF parsing requires the optional `pdf` extra.

See `ARCHITECTURE.md` for the full design and `CLAUDE.md` for the working rules.
