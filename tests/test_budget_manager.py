"""Budget manager: caps, can/record/remaining, profiles."""

from __future__ import annotations

from orchestrator.budget_manager import BudgetManager
from researcher_mcp.tools.budget_tools import (
    EVENT_EXPERIMENT_CREATED,
    EVENT_IDEA_CREATED,
    EVENT_PAPER_INGESTED,
    get_budget_status,
)


def test_low_profile_blocks_experiments():
    bm = BudgetManager("low")
    assert bm.cap(EVENT_EXPERIMENT_CREATED) == 0
    assert bm.can(EVENT_EXPERIMENT_CREATED) is False
    assert bm.cap(EVENT_PAPER_INGESTED) == 5


def test_can_record_remaining_cycle():
    bm = BudgetManager("medium")
    assert bm.cap(EVENT_IDEA_CREATED) == 8
    assert bm.remaining(EVENT_IDEA_CREATED) == 8
    for _ in range(8):
        assert bm.can(EVENT_IDEA_CREATED)
        bm.record(EVENT_IDEA_CREATED)
    assert bm.remaining(EVENT_IDEA_CREATED) == 0
    assert bm.can(EVENT_IDEA_CREATED) is False


def test_uncapped_event_always_allowed():
    bm = BudgetManager("low")
    assert bm.cap("paper_fetched") is None
    assert bm.can("paper_fetched") is True


def test_status_shape():
    bm = BudgetManager("high")
    status = bm.status()
    assert status["profile"] == "high"
    assert status["caps"][EVENT_PAPER_INGESTED] == 30
    assert set(status) >= {"profile", "caps", "used", "remaining"}
    # matches the standalone tool
    assert get_budget_status("high")["caps"] == status["caps"]
