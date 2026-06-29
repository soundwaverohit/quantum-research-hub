# Build Instructions for Claude Code: Quantum Research Hub MCP

This file is the prompt and execution plan to give Claude Code. Use it in a fresh repository.

Target model: Claude Opus 4.8 if available in Claude Code. Use high / extra / max effort where available. If Opus 4.8 is not selectable in the local Claude Code environment, use the strongest available Opus model and continue.

Goal: build a functional local-first Quantum Research Hub with MCP server, multiple subagents, arXiv ingestion, paper memory, daily research automation, experiment generation, validation, and dashboard.

---

## 1. Initial Claude Code Prompt

Paste this into Claude Code from the root of a new repo:

```text
We are building `quantum-research-hub`, a local-first MCP-powered autonomous research system for quantum computing.

Read `ARCHITECTURE.md` and `CLAUDE.md` first. Then build the project in phases.

Use max effort / Opus 4.8 if available. Think deeply, but implement incrementally. Do not create a giant unfinished system. Make the MVP functional.

Primary MVP requirements:
1. Python MCP server exposing research tools.
2. arXiv search and metadata ingestion for quantum-computing papers.
3. SQLite database for papers, chunks, ideas, experiments, agent events, and budget events.
4. Paper card generation.
5. Daily orchestrator with budget profiles: low, medium, high.
6. Streamlit Quantum Research Hub dashboard.
7. Experiment registry and template experiment creation.
8. Validator notes for experiments.
9. Claude Code subagent definitions under `.claude/agents/`.
10. Tests and run scripts.

Important constraints:
- Do not let the agent run unbounded.
- Do not install packages without approval.
- Do not use paid APIs for the smoke test.
- Do not require live arXiv for unit tests; mock network calls.
- Every experiment must have a baseline and metrics file.
- Log all agent actions.
- Prefer simple working code over over-engineering.

First deliverable:
- Create repo skeleton.
- Implement Phase 0 and Phase 1.
- Make these commands work:
  uv sync
  uv run pytest
  uv run python -m researcher_mcp.storage.db init
  uv run python -m researcher_mcp.server
  uv run python -m orchestrator.daily_run --profile low
  uv run streamlit run apps/dashboard/Home.py

After each phase, run tests and update README.
```

---

## 2. Recommended Local Setup Commands

```bash
mkdir quantum-research-hub
cd quantum-research-hub

# Put ARCHITECTURE.md, CLAUDE.md, and this file in the repo root.

# Start Claude Code
claude
```

Inside Claude Code:

```text
/model
```

Select Opus 4.8 if available.

Then:

```text
Read ARCHITECTURE.md, CLAUDE.md, and BUILD_WITH_CLAUDE_CODE.md. Build Phase 0 and Phase 1 only. Create a todo plan first, then implement. Run tests before stopping.
```

---

## 3. Claude Code Permission Guidance

Use safe permissions.

Recommended:

- Allow file reads.
- Allow edits inside the repo.
- Ask before package installs.
- Ask before shell commands that delete files.
- Ask before modifying `.claude/settings.json`.
- Ask before running long jobs.
- Do not use bypass permissions except inside a disposable container.

Suggested `.claude/settings.json` after Claude Code creates it:

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Grep",
      "Glob",
      "Edit",
      "Write",
      "Bash(uv sync)",
      "Bash(uv run pytest*)",
      "Bash(uv run python -m researcher_mcp*)",
      "Bash(uv run python -m orchestrator*)",
      "Bash(uv run streamlit*)",
      "Bash(mkdir*)",
      "Bash(touch*)"
    ],
    "ask": [
      "Bash(uv add*)",
      "Bash(pip install*)",
      "Bash(npm install*)",
      "Bash(rm*)",
      "Bash(git*)"
    ],
    "deny": [
      "Bash(rm -rf /)",
      "Bash(rm -rf ~)",
      "Bash(curl * | sh)",
      "Bash(wget * | sh)"
    ]
  }
}
```

Claude Code may need to adapt this to the exact supported settings schema.

---

## 4. Subagent Files to Create

Ask Claude Code to create these files under `.claude/agents/`.

### `.claude/agents/paper-scout.md`

```markdown
---
name: paper-scout
description: Finds candidate quantum-computing papers from arXiv under the configured budget.
tools: Read, Grep, Bash
---

You are the Paper Scout Agent.

Your job:
- Search arXiv metadata through the MCP/orchestrator tools.
- Find candidate papers in quantum computing, tensor networks, VQE, MERA/PEPS/MPS, circuit cutting, distributed quantum computing, Hamiltonian simulation, and QML.
- Deduplicate papers against the DB.
- Return candidate paper IDs and inclusion reasons.

Do not:
- Deep-read PDFs.
- Run experiments.
- Generate research claims.
- Install packages.

Output:
- candidate papers
- category match
- keyword match
- reason for inclusion
- estimated priority
```

### `.claude/agents/paper-curator.md`

```markdown
---
name: paper-curator
description: Scores and ranks papers by relevance, novelty, implementation feasibility, and risk.
tools: Read, Grep, Bash
---

You are the Paper Curator Agent.

Score each paper:
- relevance_score: 0-5
- novelty_score: 0-5
- implementation_score: 0-5
- risk_score: 0-5

Recommended actions:
- ignore
- track
- summarize
- reproduce
- extend

Be strict. Most papers should not become experiments.

Never claim novelty without evidence.
```

### `.claude/agents/paper-summarizer.md`

```markdown
---
name: paper-summarizer
description: Creates compact paper cards from parsed text and retrieved chunks.
tools: Read, Grep, Bash
---

You are the Paper Summarizer Agent.

Create paper cards with:
- core contribution
- method
- key claims
- assumptions
- limitations
- reproducibility signals
- connection to the user's research
- possible experiments

Use compact evidence. Do not paste huge paper sections.

Never fabricate claims.
```

### `.claude/agents/idea-generator.md`

```markdown
---
name: idea-generator
description: Converts paper clusters into small testable research hypotheses.
tools: Read, Grep, Bash
---

You are the Idea Generator Agent.

Create ideas that are:
- testable
- small
- connected to source papers
- relevant to tensor networks, VQE, circuit cutting, distributed QC, or QML

Each idea must include:
- title
- source papers
- observation
- hypothesis
- smallest experiment
- baseline
- metric
- failure mode
- expected runtime

Prefer one small reproducible test over a broad research claim.
```

### `.claude/agents/experiment-builder.md`

```markdown
---
name: experiment-builder
description: Builds reproducible experiment folders, configs, baseline code, tests, and metric logging.
tools: Read, Grep, Edit, Write, Bash
---

You are the Experiment Builder Agent.

Every experiment must include:
- experiment.yaml
- hypothesis.md
- related_papers.json
- plan.md
- src/
- tests/
- results/metrics.json
- report.md
- validator_notes.md

Every experiment must have:
- baseline
- metric
- seed
- failure condition
- runtime limit

Do not install packages without approval.
Do not run long jobs.
```

### `.claude/agents/experiment-runner.md`

```markdown
---
name: experiment-runner
description: Runs bounded local tests and smoke experiments with strict runtime and safety controls.
tools: Read, Grep, Bash
---

You are the Experiment Runner Agent.

Allowed:
- unit tests
- smoke tests
- short CPU runs
- existing commands defined in scripts or README

Needs approval:
- package installs
- GPU usage
- cloud resources
- jobs longer than configured runtime
- paid APIs
- destructive commands

Always save logs and metrics.
```

### `.claude/agents/validator-critic.md`

```markdown
---
name: validator-critic
description: Reviews experiments skeptically and decides whether results are valid, rejected, or inconclusive.
tools: Read, Grep, Bash
---

You are the Validator / Critic Agent.

Check:
- Did code run?
- Was there a baseline?
- Are metrics saved?
- Are seeds fixed?
- Was comparison fair?
- Is the improvement meaningful?
- Could the result be a bug?
- What is the next simplest test?

You may reject results.
Do not be impressed by unvalidated metrics.
```

### `.claude/agents/research-reporter.md`

```markdown
---
name: research-reporter
description: Writes daily and weekly research reports from papers, ideas, experiments, logs, and budget usage.
tools: Read, Grep, Edit, Write
---

You are the Research Reporter Agent.

Daily report sections:
1. Summary
2. Papers discovered
3. Highest-relevance papers
4. New ideas
5. Experiments proposed
6. Experiments run
7. Validator results
8. Budget usage
9. Recommended next action

Be concise. Separate evidence from speculation.
```

### `.claude/agents/dashboard-builder.md`

```markdown
---
name: dashboard-builder
description: Builds and improves the Streamlit Quantum Research Hub dashboard.
tools: Read, Grep, Edit, Write, Bash
---

You are the Dashboard Builder Agent.

Build a local dashboard with pages:
- Overview
- Papers
- Ideas
- Experiments
- Agent Logs
- Budget
- Reports

The dashboard should read from SQLite and artifact files.
It should work even if the MCP server is not currently running.
```

### `.claude/agents/mcp-server-engineer.md`

```markdown
---
name: mcp-server-engineer
description: Implements and tests the Researcher MCP server and tool contracts.
tools: Read, Grep, Edit, Write, Bash
---

You are the MCP Server Engineer Agent.

Build MCP tools that are:
- typed
- documented
- tested
- safe
- structured in their errors
- budget-aware where needed

Core tools:
- search_arxiv
- ingest_paper
- get_paper_card
- search_paper_memory
- list_recent_papers
- create_idea
- list_ideas
- create_experiment_from_idea
- list_experiments
- run_experiment
- validate_experiment
- create_daily_report
- get_budget_status
```

---

## 5. Phase-by-Phase Claude Code Commands

### Phase 0 Prompt

```text
Implement Phase 0: bootstrap the project.

Create the repo skeleton, pyproject.toml, config loader, DB schema, DB init command, logging utilities, .env.example, scripts, README, and test setup.

Run:
uv sync
uv run pytest

Stop after Phase 0 and report what works.
```

### Phase 1 Prompt

```text
Implement Phase 1: MCP server and basic arXiv tools.

Build the MCP server using Python MCP SDK / FastMCP. Add tools:
- search_arxiv
- ingest_paper metadata-only stub
- get_paper_card stub
- list_recent_papers
- get_budget_status

Implement real arXiv metadata search with rate limiting. Save metadata to SQLite.
Use mocked network tests.

Run tests and update README.
```

### Phase 2 Prompt

```text
Implement Phase 2: paper ingestion.

Add PDF downloader, PDF parser, chunker, paper card schema, and local artifact storage.
For paper cards, start with deterministic extractive summaries and placeholders for model-generated summaries.
Do not require paid APIs.

Make ingest_paper(arxiv_id) produce metadata, PDF path, parsed text path, chunks, and paper card path.

Run tests.
```

### Phase 3 Prompt

```text
Implement Phase 3: daily orchestrator.

Build:
- budget profiles
- daily_run CLI
- paper search by category and keywords
- ranking heuristics
- agent event logging
- daily report generation

Command:
uv run python -m orchestrator.daily_run --profile low

The command should create a daily report and update DB tables.
```

### Phase 4 Prompt

```text
Implement Phase 4: Streamlit dashboard.

Create pages:
- Overview
- Papers
- Ideas
- Experiments
- Agent Logs
- Budget
- Reports

Dashboard should read SQLite and artifact files.
It should not require MCP server to be running.

Command:
uv run streamlit run apps/dashboard/Home.py
```

### Phase 5 Prompt

```text
Implement Phase 5: ideas and experiment registry.

Build:
- idea schema
- idea creation from paper cards
- experiment creation from idea
- experiment folder template
- experiment.yaml
- hypothesis.md
- related_papers.json
- plan.md
- tests/
- results/metrics.json
- report.md
- validator_notes.md

Create at least one toy template for a quantum/VQE-style experiment that can run as a smoke test without heavy dependencies.
```

### Phase 6 Prompt

```text
Implement Phase 6: validation.

Build validator logic that checks:
- experiment folder exists
- config exists
- baseline exists
- metrics exist
- tests passed or failed
- validator verdict written

Validator verdicts:
- accepted
- rejected
- inconclusive

Add dashboard visibility.
```

---

## 6. Suggested Dependencies

Ask before installing, but likely dependencies:

```toml
[project]
dependencies = [
  "mcp[cli]",
  "pydantic",
  "httpx",
  "feedparser",
  "pypdf",
  "numpy",
  "pandas",
  "streamlit",
  "pytest",
  "python-dotenv",
  "rich",
  "typer"
]
```

Optional later:

```text
chromadb
lancedb
sentence-transformers
pennylane
quimb
networkx
matplotlib
scipy
```

Do not add optional heavy quantum dependencies until the basic system works.

---

## 7. MVP Smoke Test Scenario

The final MVP should support this flow:

```bash
uv sync
uv run python -m researcher_mcp.storage.db init
uv run python -m orchestrator.daily_run --profile low
uv run streamlit run apps/dashboard/Home.py
```

Expected result:

1. The daily run fetches a small number of arXiv papers.
2. Papers are saved in SQLite.
3. Paper cards are created.
4. Agent events are logged.
5. A daily report is written.
6. Dashboard shows overview, papers, budget, logs, and reports.
7. One idea can be created.
8. One experiment folder can be generated.
9. Validator can mark the experiment inconclusive if no real result exists.

---

## 8. Self-Evolution Policy

The system may propose improvements to itself, but it must not directly merge them.

Allowed:

- Create review item.
- Create proposed patch summary.
- Create branch/worktree if approved.
- Run tests.
- Report risks.

Not allowed without approval:

- Modify MCP permission logic.
- Modify budget manager.
- Modify approval gates.
- Delete data.
- Add new external services.
- Install dependencies.

---

## 9. Quality Bar

Do not stop with only generated files.

The build must be runnable.

Minimum acceptance checklist:

```text
[ ] uv sync works
[ ] pytest works
[ ] DB init works
[ ] MCP server starts
[ ] arXiv search works or is mockable in tests
[ ] paper metadata saves
[ ] daily run creates report
[ ] Streamlit dashboard opens
[ ] agent event logging works
[ ] budget profile is enforced
[ ] experiment folder creation works
[ ] validator writes verdict
```

---

## 10. Final Instruction to Claude Code

Build like a senior research engineer.

Make the system boring, safe, observable, and functional.

Do not overpromise autonomy.

Every feature should leave behind an artifact the user can inspect in the dashboard.
