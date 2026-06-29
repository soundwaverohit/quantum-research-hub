# Quantum Research Hub Architecture

## 1. Product Vision

The Quantum Research Hub is a local-first, MCP-powered autonomous research system for quantum-computing work. It watches new arXiv papers, builds structured paper memory, proposes research ideas, creates bounded experiments, runs validation, and exposes everything through a dashboard.

The goal is not to let an LLM free-run indefinitely. The goal is to build a controlled research lab where Claude Code and subagents operate through a budgeted orchestrator and a safe MCP interface.

Primary user outcome:

> Every day, the system tells me what changed in quantum computing, which papers matter to my research, what ideas are worth testing, and what experiments the agents attempted.

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
- Benchmarking and reproducibility

---

## 2. High-Level System Design

```text
Claude Code / Claude Max or Pro
        |
        v
Research Orchestrator
        |
        +-- Paper Scout Agent
        +-- Paper Curator Agent
        +-- Paper Summarizer Agent
        +-- Idea Generator Agent
        +-- Experiment Builder Agent
        +-- Experiment Runner Agent
        +-- Validator / Critic Agent
        +-- Research Reporter Agent
        |
        v
Researcher MCP Server
        |
        +-- arXiv tools
        +-- PDF parsing tools
        +-- paper memory tools
        +-- embedding / retrieval tools
        +-- experiment registry tools
        +-- code runner tools
        +-- budget tools
        +-- dashboard tools
        |
        v
Storage Layer
        |
        +-- SQLite/Postgres metadata DB
        +-- Chroma/LanceDB/FAISS vector DB
        +-- local PDF store
        +-- experiment artifacts
        +-- logs and reports
        |
        v
Quantum Research Hub Dashboard
```

The MCP server is the tool layer. Claude Code and subagents should not directly scrape, parse, mutate, or execute everything by themselves. They should call bounded tools exposed by the MCP server.

---

## 3. Core Architectural Principle

```text
Raw paper ingestion -> local deterministic pipeline
Paper ranking -> local heuristics + optional model pass
Deep interpretation -> Claude
Experiment planning -> Claude
Experiment execution -> sandboxed local runner
Validation -> deterministic tests + Claude critic
Dashboard -> transparent audit trail
```

Do not send full PDFs to Claude by default.

Claude should receive:

- Paper cards
- Targeted retrieved chunks
- Related-paper clusters
- Experiment plans
- Metrics and logs

Claude should not receive:

- Every page of every PDF
- Full paper corpus
- Unbounded logs
- Giant raw experiment outputs

---

## 4. Repository Layout

```text
quantum-research-hub/
  README.md
  ARCHITECTURE.md
  CLAUDE.md
  pyproject.toml
  .env.example
  .gitignore

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

  apps/
    dashboard/
      README.md
      package.json
      src/
        app/
        components/
        lib/

  services/
    researcher_mcp/
      researcher_mcp/
        __init__.py
        server.py
        config.py
        tools/
          arxiv_tools.py
          paper_tools.py
          memory_tools.py
          idea_tools.py
          experiment_tools.py
          runner_tools.py
          budget_tools.py
          dashboard_tools.py
        ingest/
          arxiv_client.py
          pdf_downloader.py
          pdf_parser.py
          chunker.py
          metadata.py
        storage/
          db.py
          schema.sql
          models.py
          vector_store.py
        prompts/
          paper_card.md
          idea_generation.md
          experiment_plan.md
          validation.md
          daily_report.md
      tests/

    orchestrator/
      orchestrator/
        __init__.py
        daily_run.py
        scheduler.py
        budget_manager.py
        task_queue.py
        agent_router.py
        agents/
          paper_scout.py
          paper_curator.py
          paper_summarizer.py
          idea_generator.py
          experiment_builder.py
          experiment_runner.py
          validator_critic.py
          research_reporter.py
      tests/

  data/
    papers/
      pdfs/
      parsed/
      cards/
    embeddings/
    experiments/
    reports/
    logs/

  db/
    dev.sqlite3
    migrations/

  experiments/
    templates/
      vqe_baseline/
      tensor_network_ansatz/
      circuit_cutting/
      qml_feature_map/
    runs/

  scripts/
    bootstrap.sh
    dev.sh
    run_daily.sh
    reset_dev_db.sh
    run_tests.sh
```

---

## 5. Main Components

### 5.1 Researcher MCP Server

The MCP server exposes controlled tools to Claude Code and any other MCP client.

Required tools for v0.1:

```text
search_arxiv(query, categories, from_date, to_date, max_results)
ingest_paper(arxiv_id)
get_paper_card(arxiv_id)
search_paper_memory(query, k)
list_recent_papers(days, min_relevance)
create_idea(title, hypothesis, source_arxiv_ids)
list_ideas(status)
create_experiment_from_idea(idea_id)
get_experiment(experiment_id)
list_experiments(status)
get_budget_status()
```

Required tools for v0.2:

```text
run_experiment(experiment_id, mode)
get_experiment_results(experiment_id)
validate_experiment(experiment_id)
create_daily_report(date)
create_weekly_report(week_start)
```

Required tools for v0.3:

```text
propose_repo_improvement(area)
create_review_item(title, patch_summary)
approve_experiment_run(experiment_id)
approve_repo_patch(review_item_id)
```

The first version should use Python's MCP SDK with FastMCP-style tool registration.

---

### 5.2 Orchestrator

The orchestrator is the daily automation layer.

Responsibilities:

- Trigger daily paper discovery.
- Apply token and compute budget rules.
- Decide which agents run.
- Queue tasks.
- Store all agent decisions.
- Ensure approval is required for risky actions.
- Produce daily and weekly reports.

Daily run sequence:

```text
1. Load budget profile.
2. Search arXiv for new papers.
3. Deduplicate against DB.
4. Ingest only papers that pass cheap filters.
5. Generate paper cards.
6. Rank paper cards by relevance.
7. Cluster papers by topic.
8. Ask Idea Generator for bounded ideas from top clusters.
9. Convert top idea into experiment proposal.
10. If auto-experiment mode is enabled, create a small experiment branch/folder.
11. Run only safe tests unless user approval exists.
12. Ask Validator/Critic to review outputs.
13. Write daily report.
14. Update dashboard state.
```

---

### 5.3 Paper Ingestion Pipeline

Paper ingestion should be mostly deterministic and cheap.

Pipeline:

```text
arXiv metadata -> relevance prefilter -> PDF download -> parse text -> section split -> chunk -> embed -> paper card -> DB
```

Paper card schema:

```json
{
  "arxiv_id": "string",
  "title": "string",
  "authors": ["string"],
  "published": "YYYY-MM-DD",
  "categories": ["quant-ph"],
  "abstract": "string",
  "core_contribution": "string",
  "methods": ["string"],
  "claims": ["string"],
  "datasets_or_benchmarks": ["string"],
  "relevance_to_user": "string",
  "possible_experiments": ["string"],
  "relevance_score": 0,
  "novelty_score": 0,
  "implementation_difficulty": 0,
  "recommended_action": "ignore | track | summarize | reproduce | extend"
}
```

Default tracked categories:

```text
quant-ph
cs.LG
cs.ET
physics.comp-ph
cond-mat.str-el
hep-lat
```

Default keyword groups:

```text
Group A: tensor networks, MPS, PEPS, MERA, tree tensor network, tensor network state
Group B: VQE, variational quantum eigensolver, variational quantum algorithm
Group C: circuit cutting, distributed quantum computing, entanglement forging, circuit knitting
Group D: Hamiltonian simulation, lattice gauge theory, Ising model, Heisenberg model
Group E: quantum machine learning, quantum feature map, quantum kernel, data re-uploading
Group F: error mitigation, measurement reduction, shadow tomography, barren plateau
```

---

### 5.4 Experiment Engine

Experiments must be small, reproducible, and auditable.

Experiment folder schema:

```text
experiments/runs/YYYYMMDD_short_slug/
  experiment.yaml
  hypothesis.md
  related_papers.json
  plan.md
  src/
  tests/
  configs/
  results/
    metrics.json
    plots/
    logs/
  report.md
  validator_notes.md
```

Experiment metadata:

```yaml
id: "20260605_qmera_depth_adaptation_001"
title: "Hybrid QPEPS-QMERA adaptive depth test on 2D Ising toy model"
status: "proposed"
hypothesis: "Short-range PEPS layers plus adaptive MERA layers reduce energy error at fixed parameter budget."
source_papers:
  - "arXiv:xxxx.xxxxx"
baselines:
  - "QMPS"
  - "QPEPS fixed depth"
  - "QMERA fixed depth"
metrics:
  - "energy_error"
  - "fidelity_if_reference_available"
  - "parameter_count"
  - "runtime_seconds"
  - "seed_stability"
allowed_compute_mode: "small"
approval_required_for:
  - "gpu"
  - "runtime_over_10_minutes"
  - "package_install"
  - "external_api_spend"
```

Experiment statuses:

```text
proposed
approved
building
running
failed
validated
rejected
archived
```

---

### 5.5 Budget Manager

The budget manager protects Claude usage and local compute.

Budget profiles:

```yaml
low:
  max_papers_per_day: 5
  max_deep_summaries_per_day: 2
  max_ideas_per_day: 3
  max_experiments_created_per_day: 0
  max_experiments_run_per_day: 0
  max_claude_passes_per_day: 3

medium:
  max_papers_per_day: 15
  max_deep_summaries_per_day: 5
  max_ideas_per_day: 8
  max_experiments_created_per_day: 1
  max_experiments_run_per_day: 1
  max_claude_passes_per_day: 8

high:
  max_papers_per_day: 30
  max_deep_summaries_per_day: 10
  max_ideas_per_day: 15
  max_experiments_created_per_day: 2
  max_experiments_run_per_day: 2
  max_claude_passes_per_day: 15
```

The system must always record estimated and actual costs.

Track:

- Number of papers fetched
- Number of PDFs downloaded
- Number of paper cards generated
- Number of Claude calls/tasks
- Number of experiments proposed
- Number of experiments run
- Local runtime
- Errors and retries

---

## 6. Agents and Subagents

### 6.1 Paper Scout Agent

Goal: discover candidate papers.

Inputs:

- Date range
- Categories
- Keyword groups
- Budget

Outputs:

- Candidate paper list
- Reason for inclusion
- Deduplication status

Must not:

- Deep-read PDFs
- Generate speculative ideas
- Run experiments

---

### 6.2 Paper Curator Agent

Goal: rank papers by relevance to the user's research agenda.

Scores:

```text
relevance_score: 0-5
novelty_score: 0-5
implementation_score: 0-5
risk_score: 0-5
```

Output action:

```text
ignore
track
summarize
reproduce
extend
```

---

### 6.3 Paper Summarizer Agent

Goal: create paper cards from parsed text and retrieved chunks.

Must produce:

- Core contribution
- Method
- Key claims
- Assumptions
- Limitations
- Reproducibility signals
- Connection to user's work
- Possible experiments

Must not claim novelty without evidence.

---

### 6.4 Idea Generator Agent

Goal: convert paper clusters into testable ideas.

Good idea format:

```text
Title
Source papers
Observation
Hypothesis
Why it might work
Smallest experiment
Baseline
Metrics
Failure modes
Expected runtime
```

Must prefer small experiments over grand claims.

---

### 6.5 Experiment Builder Agent

Goal: create reproducible experiment folders and code.

Must always include:

- Baseline
- Config file
- Test file
- Metric logging
- Seed control
- Result artifact paths
- README/report

Must not install packages without approval.

---

### 6.6 Experiment Runner Agent

Goal: run bounded experiments.

Allowed by default:

- Unit tests
- Smoke tests
- CPU experiments under configured time limit
- Existing dependency commands

Needs approval:

- New package installation
- GPU execution
- Long jobs
- Cloud compute
- External paid API calls
- Destructive filesystem operations

---

### 6.7 Validator / Critic Agent

Goal: decide whether the experiment result is meaningful.

Required checks:

```text
Did the code run?
Was there a baseline?
Are metrics saved?
Are seeds fixed?
Was comparison fair?
Is the improvement statistically meaningful?
Could the result be a bug?
What is the simplest next test?
```

The validator can reject results.

---

### 6.8 Research Reporter Agent

Goal: write daily and weekly research updates.

Daily report sections:

```text
1. Papers discovered
2. Papers worth reading
3. Ideas generated
4. Experiments proposed
5. Experiments run
6. Validation results
7. Budget usage
8. Recommended next action
```

Weekly report sections:

```text
1. Research trends
2. Best papers
3. Best experiment ideas
4. Failed experiments and lessons
5. Validated progress
6. Open questions
7. Next week plan
```

---

## 7. Dashboard Architecture

MVP dashboard can be Streamlit for speed. Later migrate to Next.js + FastAPI.

Recommended MVP:

```text
Streamlit app -> reads SQLite + artifact files -> displays papers, ideas, experiments, budget, logs
```

Production-oriented version:

```text
Next.js dashboard -> FastAPI backend -> DB/vector store/artifacts
```

Pages:

```text
/overview
/papers
/ideas
/experiments
/agents
/budget
/reports
/settings
```

### 7.1 Overview Page

Cards:

```text
Papers fetched today
Papers ingested today
High-relevance papers
Ideas generated
Experiments proposed
Experiments run
Validated results
Budget used
```

### 7.2 Papers Page

Table columns:

```text
Date
Title
arXiv ID
Category
Relevance
Novelty
Action
Status
```

Paper detail view:

```text
Abstract
Paper card
Important chunks
Related ideas
Related experiments
```

### 7.3 Ideas Page

Columns:

```text
Title
Hypothesis
Source papers
Feasibility
Novelty
Status
Next action
```

### 7.4 Experiments Page

Columns:

```text
Experiment ID
Title
Status
Baseline
Metric
Best result
Validator verdict
Last run
```

### 7.5 Agent Activity Page

Timeline:

```text
timestamp
agent
action
input summary
output summary
status
cost estimate
artifact link
```

---

## 8. Database Schema

Initial SQLite schema:

```sql
CREATE TABLE IF NOT EXISTS papers (
  arxiv_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  authors_json TEXT,
  abstract TEXT,
  categories_json TEXT,
  published_date TEXT,
  updated_date TEXT,
  pdf_url TEXT,
  pdf_path TEXT,
  parsed_text_path TEXT,
  paper_card_path TEXT,
  relevance_score REAL DEFAULT 0,
  novelty_score REAL DEFAULT 0,
  implementation_score REAL DEFAULT 0,
  recommended_action TEXT DEFAULT 'track',
  status TEXT DEFAULT 'discovered',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  arxiv_id TEXT NOT NULL,
  section TEXT,
  chunk_index INTEGER,
  chunk_text TEXT NOT NULL,
  token_estimate INTEGER,
  embedding_id TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(arxiv_id) REFERENCES papers(arxiv_id)
);

CREATE TABLE IF NOT EXISTS ideas (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  hypothesis TEXT NOT NULL,
  source_arxiv_ids_json TEXT,
  novelty_score REAL DEFAULT 0,
  feasibility_score REAL DEFAULT 0,
  expected_compute_cost TEXT,
  status TEXT DEFAULT 'proposed',
  idea_card_path TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experiments (
  id TEXT PRIMARY KEY,
  idea_id TEXT,
  title TEXT NOT NULL,
  hypothesis TEXT,
  status TEXT DEFAULT 'proposed',
  folder_path TEXT,
  config_path TEXT,
  result_path TEXT,
  validator_notes_path TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(idea_id) REFERENCES ideas(id)
);

CREATE TABLE IF NOT EXISTS experiment_runs (
  id TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  status TEXT DEFAULT 'created',
  started_at TEXT,
  finished_at TEXT,
  metrics_json TEXT,
  logs_path TEXT,
  error_message TEXT,
  FOREIGN KEY(experiment_id) REFERENCES experiments(id)
);

CREATE TABLE IF NOT EXISTS agent_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
  agent_name TEXT NOT NULL,
  action TEXT NOT NULL,
  input_summary TEXT,
  output_summary TEXT,
  status TEXT,
  cost_estimate_json TEXT,
  artifact_path TEXT
);

CREATE TABLE IF NOT EXISTS budget_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
  budget_profile TEXT,
  event_type TEXT,
  estimated_tokens INTEGER,
  estimated_cost REAL,
  local_runtime_seconds REAL,
  notes TEXT
);
```

---

## 9. MCP Tool Contracts

### search_arxiv

```json
{
  "name": "search_arxiv",
  "description": "Search arXiv for quantum computing papers using categories, keywords, and date filters.",
  "input": {
    "query": "string",
    "categories": ["string"],
    "from_date": "YYYY-MM-DD",
    "to_date": "YYYY-MM-DD",
    "max_results": 10
  },
  "output": {
    "papers": [
      {
        "arxiv_id": "string",
        "title": "string",
        "authors": ["string"],
        "abstract": "string",
        "categories": ["string"],
        "published": "YYYY-MM-DD",
        "pdf_url": "string"
      }
    ]
  }
}
```

### ingest_paper

```json
{
  "name": "ingest_paper",
  "input": {
    "arxiv_id": "string",
    "force": false
  },
  "output": {
    "arxiv_id": "string",
    "status": "ingested | skipped | failed",
    "pdf_path": "string",
    "chunks_created": 0,
    "paper_card_path": "string",
    "error": "string|null"
  }
}
```

### create_experiment_from_idea

```json
{
  "name": "create_experiment_from_idea",
  "input": {
    "idea_id": "string",
    "mode": "small | medium",
    "auto_run": false
  },
  "output": {
    "experiment_id": "string",
    "folder_path": "string",
    "status": "proposed | building",
    "approval_required": true
  }
}
```

---

## 10. Safety and Approval Model

Autonomous by default:

```text
- Search arXiv
- Download public arXiv PDFs
- Parse PDFs
- Create paper cards
- Create embeddings
- Generate paper rankings
- Generate ideas
- Create experiment proposal folders
- Run unit tests
- Run smoke tests under time limit
- Update dashboard
```

Approval required:

```text
- Install packages
- Modify .claude settings
- Run commands over 10 minutes
- Use GPU
- Use cloud resources
- Use paid APIs
- Delete files outside experiment run folders
- Modify core orchestrator/MCP server code as part of self-evolution
- Merge self-generated changes
- Claim a result is novel or publishable
```

Hard deny:

```text
- Delete repository root
- Access secrets not listed in .env.example
- Exfiltrate files
- Commit API keys
- Run arbitrary shell downloaded from internet
- Disable budget manager
- Disable approval gates
```

---

## 11. Development Phases

### Phase 0: Project Bootstrap

Definition of done:

- Repo structure exists.
- Python package installs.
- DB initializes.
- MCP server starts.
- Dashboard starts.
- Tests run.

### Phase 1: Paper Memory

Definition of done:

- arXiv search works.
- Metadata saved to DB.
- PDF download works.
- PDF text parsing works.
- Paper card generated.
- Paper appears on dashboard.

### Phase 2: Daily Research Loop

Definition of done:

- `scripts/run_daily.sh` works.
- Budget profile respected.
- Top papers selected.
- Daily report generated.
- Agent events logged.

### Phase 3: Ideas

Definition of done:

- Paper clusters produce ideas.
- Ideas saved to DB.
- Ideas visible in dashboard.
- Ideas include hypothesis, baseline, metric, and failure modes.

### Phase 4: Experiments

Definition of done:

- Idea converts to experiment folder.
- Template code generated.
- Tests included.
- Smoke test runs.
- Metrics saved.
- Results visible in dashboard.

### Phase 5: Validation

Definition of done:

- Validator reviews every experiment.
- Rejection is possible.
- Report explains why result is valid/invalid.
- Baseline comparison required.

### Phase 6: Self-Evolution

Definition of done:

- Agents can propose repo improvements.
- Improvements are saved as review items.
- No auto-merge.
- Tests must pass before approval.

---

## 12. Local Run Commands

Expected commands after implementation:

```bash
# setup
uv sync
cp .env.example .env
uv run python -m researcher_mcp.storage.db init

# run MCP server
uv run python -m researcher_mcp.server

# run daily research loop
uv run python -m orchestrator.daily_run --profile low

# run dashboard
uv run streamlit run apps/dashboard/Home.py

# tests
uv run pytest
```

---

## 13. Definition of Functional MVP

A functional MVP means:

```text
1. I can run one command to fetch recent quantum papers.
2. The system ingests and ranks papers under a budget.
3. I can view papers in a local dashboard.
4. I can view generated ideas.
5. I can create one experiment from one idea.
6. The experiment has baseline, test, config, metrics, and report.
7. The validator can accept or reject the result.
8. All agent activity is logged.
9. The MCP server exposes the core tools.
10. Claude Code can use the MCP server without directly controlling unsafe actions.
```

---

## 14. Non-Goals for MVP

Do not build these first:

- A fully autonomous publishable-research agent
- Multi-GPU experiment platform
- Cloud deployment
- Full paper semantic search at massive scale
- Automatic GitHub PR creation
- Automatic package installation
- Automatic claims of novelty
- Perfect arXiv parsing
- Perfect PDF figure extraction

---

## 15. Future Extensions

After MVP:

- Add paper citation graph.
- Add Semantic Scholar / OpenAlex metadata.
- Add local LLM for cheap first-pass summarization.
- Add queue workers with Celery/RQ.
- Add Docker sandbox for experiment execution.
- Add Git worktrees per experiment.
- Add Jupyter notebook export.
- Add experiment comparison dashboard.
- Add weekly literature map.
- Add LaTeX research-note generation.
- Add benchmark suite for tensor-network ansatz experiments.
