"""Tool/service layer.

These functions hold the *real* capability logic (arXiv search, ingestion,
paper memory, ideas, experiments, runner, budget, dashboard). They return plain
JSON-able dicts and are shared by BOTH:

* the Researcher MCP server (``researcher_mcp.server``), which exposes them as
  MCP tools, and
* the orchestrator agents, which call them under budget control and log every
  action to ``agent_events``.

Keeping the logic here (and not in the agents or the server) means there is one
tested implementation behind every capability.
"""
