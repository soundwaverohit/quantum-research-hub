"""Orchestrator package.

The orchestrator is the daily automation layer. It owns the budget, decides
which agents run, queues their work, logs every decision, and produces daily /
weekly reports. It calls the same tool functions the MCP server exposes.
"""

__version__ = "0.1.0"
