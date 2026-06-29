# CLAUDE.md

You are Claude Code working inside the `quantum-research-hub` repository.

Your job is to build a functional, local-first Quantum Research Hub: an MCP-powered research system that automatically tracks quantum-computing papers, builds paper memory, proposes research ideas, creates bounded experiments, validates results, and shows all activity in a dashboard.

Use maximum effort and deep planning for architecture and implementation. Prefer correct, working, tested code over impressive but unfinished abstractions.

---

## 1. Mission

Build a controlled autonomous research lab for quantum computing.

The system should answer these daily questions:

1. What changed in quantum computing today?
2. Which new papers matter for my research?
3. What ideas do these papers suggest?
4. Which ideas can be tested with small reproducible experiments?
5. What did the agents try, and what actually worked?

Research focus:

- Quantum computing
- Tensor networks
- VQE
- MPS / PEPS / MERA / QMERA
- Hybrid QPEPS-QMERA ansatz design
- Distributed quantum computing
- Circuit cutting
- Adaptive circuit knitting
- Hamiltonian simulation
- Lattice models
- Quantum machine learning
- Quantum feature maps
- Reproducible benchmarking

---

## 2. Core Design Rule

Do not build an unbounded autonomous agent.

Build a bounded system:

```text
MCP server = tools, memory, safe execution interface
Orchestrator = schedule, budget, approvals, agent routing
Subagents = focused reasoning workers
Dashboard = transparent research hub
User = final scientific judgment and approval
```

Claude should not read every PDF end-to-end. The local pipeline should ingest, parse, chunk, embed, and retrieve. Claude should receive compact paper cards and targeted chunks.

---

## 3. Mandatory Implementation Principles

Always follow these principles:

1. Make the system functional before making it fancy.
2. Keep the first version local-first.
3. Use SQLite first unless there is a strong reason not to.
4. Use a simple vector store first: Chroma, LanceDB, FAISS, or a lightweight local fallback.
5. Build a Streamlit dashboard first for speed.
6. Use FastMCP / Python MCP SDK for the server.
7. Add tests for every core module.
8. Log every agent action.
9. Never run long compute jobs without approval.
10. Never install new packages without asking.
11. Never claim novelty without evidence.
12. Every experiment must have a baseline.
13. Every experiment must save metrics.
14. Every experiment must have a validator note.
15. Every generated code path must be reproducible.

---

## 4. Safety Rules

Autonomous actions allowed:

- Search arXiv.
- Download public arXiv PDFs.
- Parse downloaded papers.
- Chunk and embed paper text.
- Generate paper cards.
- Rank papers.
- Generate ideas.
- Create experiment proposal folders.
- Run unit tests and short smoke tests.
- Update local DB and dashboard files.

Approval required:

- Installing dependencies.
- Modifying `.claude/settings.json`.
- Running jobs longer than 10 minutes.
- Using GPU.
- Using cloud compute.
- Calling paid APIs.
- Deleting files outside `data/`, `experiments/runs/`, or generated temp folders.
- Changing security/approval logic.
- Merging self-evolution patches.
- Declaring a result publishable.

Hard deny:

- Do not delete repository root.
- Do not run `rm -rf /`, `rm -rf ~`, or broad destructive commands.
- Do not read secrets unless explicitly needed and documented.
- Do not commit secrets.
- Do not disable the budget manager.
- Do not bypass approval gates.
- Do not execute shell scripts downloaded from the internet.

---

## 5. Expected Repository Structure

Build toward this structure:

```text
quantum-research-hub/
  README.md
  ARCHITECTURE.md
  CLAUDE.md
  pyproject.toml
  .env.example

  .claude/
    settings.json
    agents/
      paper-scout.md
      paper-curator.md
      paper-summarizer.md
      idea-generator.md
      experiment-builder.md
      experiment-runner.md
      validator-critic.md
      research-reporter.md
      dashboard-builder.md
      mcp-server-engineer.md

  services/
    researcher_mcp/
      researcher_mcp/
        server.py
        config.py
        tools/
        ingest/
        storage/
        prompts/
      tests/

    orchestrator/
      orchestrator/
        daily_run.py
        scheduler.py
        budget_manager.py
        task_queue.py
        agent_router.py
        agents/
      tests/

  apps/
    dashboard/
      Home.py
      pages/

  data/
    papers/
    embeddings/
    experiments/
    reports/
    logs/

  experiments/
    templates/
    runs/

  scripts/
```

---

## 6. Development Plan

### Phase 0: Bootstrap

Build first:

- `pyproject.toml`
- `.env.example`
- DB schema
- config loader
- basic logging
- test setup
- scripts

Definition of done:

- `uv sync` works.
- `uv run pytest` works.
- DB can initialize.

### Phase 1: MCP Server

Build:

- `researcher_mcp/server.py`
- tools:
  - `search_arxiv`
  - `ingest_paper`
  - `get_paper_card`
  - `search_paper_memory`
  - `list_recent_papers`
  - `get_budget_status`

Definition of done:

- MCP server starts.
- Tools are callable.
- Tool errors are structured.
- Tests cover tools.

### Phase 2: Paper Pipeline

Build:

- arXiv metadata client
- PDF downloader
- text parser
- chunker
- paper card generator
- DB persistence

Definition of done:

- Given an arXiv ID, system saves metadata, PDF, parsed text, chunks, and a paper card.

### Phase 3: Orchestrator

Build:

- daily run CLI
- budget profiles
- agent event logging
- paper ranking
- report generation

Definition of done:

- `uv run python -m orchestrator.daily_run --profile low` produces a daily report and logs.

### Phase 4: Dashboard

Build Streamlit app:

- overview
- papers
- ideas
- experiments
- agent logs
- budget
- reports

Definition of done:

- `uv run streamlit run apps/dashboard/Home.py` opens the hub.

### Phase 5: Ideas and Experiments

Build:

- idea registry
- idea generator
- experiment registry
- experiment folder generator
- templates for VQE/tensor-network/circuit-cutting experiments

Definition of done:

- One idea can become one experiment folder with hypothesis, config, baseline, tests, metrics, and report.

### Phase 6: Validation

Build:

- validator agent
- validator report schema
- metric checks
- baseline checks

Definition of done:

- Every experiment has a validator verdict: accepted, rejected, or inconclusive.

---

## 7. Subagent Strategy

Use subagents for separation of concerns. Keep each subagent narrow.

Required subagents:

1. `paper-scout`
2. `paper-curator`
3. `paper-summarizer`
4. `idea-generator`
5. `experiment-builder`
6. `experiment-runner`
7. `validator-critic`
8. `research-reporter`
9. `dashboard-builder`
10. `mcp-server-engineer`

Each subagent should have:

- clear purpose
- allowed tools
- forbidden actions
- expected output schema
- stop conditions

Do not make one giant all-purpose agent.

---

## 8. Agent Output Standards

Every agent action should create an `agent_events` row with:

```text
agent_name
action
input_summary
output_summary
status
cost_estimate_json
artifact_path
```

Every paper-related output should preserve:

```text
arxiv_id
title
authors
published date
categories
source URL or PDF path
```

Every idea should preserve:

```text
title
hypothesis
source papers
novelty score
feasibility score
smallest experiment
baseline
metric
failure mode
```

Every experiment should preserve:

```text
hypothesis
baseline
config
seed
metrics
logs
plots if any
validator notes
```

---

## 9. Coding Standards

Use Python 3.11+.

Prefer:

- `uv` for dependency management
- `pydantic` for schemas
- `sqlite3` or SQLAlchemy for DB access
- `pytest` for tests
- `ruff` for linting
- `mypy` where practical
- `structlog` or standard logging
- `httpx` for HTTP calls
- `feedparser` or arXiv API parsing
- `pypdf` or `pymupdf` for PDF parsing
- `streamlit` for MVP dashboard

Code rules:

- Type annotate public functions.
- Use small files and small functions.
- Add docstrings to MCP tools.
- Return structured errors.
- Avoid global mutable state.
- Keep paths configurable.
- Write tests for DB, arXiv client, paper card generation, and experiment creation.

---

## 10. MCP Tool Design Rules

Every MCP tool must:

- Have a clear docstring.
- Validate inputs.
- Catch and return errors cleanly.
- Log tool call status.
- Respect budget rules where applicable.
- Avoid destructive side effects unless explicitly designed.

Tool names should be stable and obvious:

```text
search_arxiv
ingest_paper
get_paper_card
search_paper_memory
list_recent_papers
create_idea
list_ideas
create_experiment_from_idea
list_experiments
run_experiment
validate_experiment
create_daily_report
get_budget_status
```

---

## 11. Experiment Rules

Every experiment must include:

- `experiment.yaml`
- `hypothesis.md`
- `related_papers.json`
- `plan.md`
- `src/`
- `tests/`
- `results/metrics.json`
- `report.md`
- `validator_notes.md`

Every experiment must define:

- baseline
- metric
- expected result
- failure condition
- runtime limit
- random seed

No experiment is valid without a baseline.

---

## 12. Dashboard Requirements

Build the MVP dashboard in Streamlit.

Pages:

```text
Home.py
pages/1_Papers.py
pages/2_Ideas.py
pages/3_Experiments.py
pages/4_Agent_Logs.py
pages/5_Budget.py
pages/6_Reports.py
```

The dashboard should read from SQLite and artifact files.

It should not require a running MCP server for basic viewing.

---

## 13. Daily Report Format

Daily report file path:

```text
data/reports/daily/YYYY-MM-DD.md
```

Report sections:

```text
# Daily Quantum Research Report: YYYY-MM-DD

## Summary

## Papers Discovered

## Highest-Relevance Papers

## New Ideas

## Experiments Proposed

## Experiments Run

## Validator Results

## Budget Usage

## Recommended Next Action
```

---

## 14. Testing Requirements

Minimum tests:

```text
test_db_init.py
test_arxiv_client.py
test_paper_card_schema.py
test_budget_manager.py
test_experiment_creation.py
test_daily_run_smoke.py
test_mcp_tools_smoke.py
```

Smoke test must run without needing paid APIs.

Use small fixtures.

Do not rely on live arXiv in unit tests. Mock network calls.

---

## 15. First Task for Claude Code

Start by creating the repository skeleton and implementing Phase 0 and Phase 1.

Do not jump directly to advanced autonomy.

First deliverable:

```text
- pyproject.toml
- DB schema
- config loader
- MCP server with stub tools
- arXiv search implementation
- paper metadata persistence
- tests
- simple Streamlit dashboard shell
- README with run commands
```

After that, implement PDF ingestion and daily orchestration.

---

## 16. Definition of Done for Initial Build

The initial build is done when this works:

```bash
uv sync
uv run pytest
uv run python -m researcher_mcp.storage.db init
uv run python -m researcher_mcp.server
uv run python -m orchestrator.daily_run --profile low
uv run streamlit run apps/dashboard/Home.py
```

And the dashboard shows:

- recent papers
- agent logs
- budget status
- reports

---

## 17. Important Behavior

When unsure, choose the simpler implementation.

When something fails, write the failure into logs and reports.

When a dependency is missing, ask before installing.

When a result looks good, have the validator try to disprove it.

When an idea is too ambitious, shrink it to the smallest reproducible test.

When asked to self-improve, create a review item instead of directly changing core logic.
