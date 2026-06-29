# Prompts (optional model pass)

The MVP generates paper cards, ideas, and reports **deterministically** (no paid
API, no PDF into the model) — see:

- Paper cards → `researcher_mcp/ingest/paper_card.py`
- Ideas → `orchestrator/agents/idea_generator.py` (seeded per keyword group)
- Daily report → `orchestrator/reporting.py`
- Validation → `researcher_mcp/tools/experiment_tools.py::validate_experiment`

This directory contains the prompt templates for the **optional Claude pass**
(gated by `QRH_ENABLE_MODEL_PASS=1`, off by default). The implemented templates
are:

- `paper_card.md` — refine deterministic paper cards.
- `idea_generation.md` — propose grounded, testable ideas from compact cards.
- `daily_report.md` — rewrite deterministic daily reports without changing facts.

The deterministic path remains the offline fallback, so tests and daily runs
never require a key.

Design rule (ARCHITECTURE.md §3): Claude should receive paper cards, targeted
chunks, plans, metrics, and logs — never full PDFs or unbounded corpora.
