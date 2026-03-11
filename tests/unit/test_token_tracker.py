"""Unit tests for travel_agent/core/token_tracker.py."""

import asyncio

import pytest

from travel_agent.core.token_tracker import BudgetExceededError, TokenTracker


class TestTokenTracker:
    def test_initial_total_is_zero(self):
        tracker = TokenTracker(session_id="s1", budget=1000)
        assert tracker.total == 0

    def test_record_accumulates_tokens(self):
        tracker = TokenTracker(session_id="s1", budget=10000)
        tracker.record("agent_a", 100)
        tracker.record("agent_a", 200)
        assert tracker.total == 300

    def test_multiple_agents_accumulate_separately(self):
        tracker = TokenTracker(session_id="s1", budget=10000)
        tracker.record("agent_a", 100)
        tracker.record("agent_b", 250)
        assert tracker.usage_by_agent() == {"agent_a": 100, "agent_b": 250}
        assert tracker.total == 350

    def test_budget_not_exceeded_below_limit(self):
        tracker = TokenTracker(session_id="s1", budget=500)
        tracker.record("agent_a", 499)
        assert tracker.total <= tracker.budget

    def test_budget_exceeded_above_limit(self):
        tracker = TokenTracker(session_id="s1", budget=100)
        tracker.record("agent_a", 101)
        assert tracker.total > tracker.budget

    def test_usage_by_agent_returns_copy(self):
        tracker = TokenTracker(session_id="s1", budget=10000)
        tracker.record("agent_a", 50)
        usage = tracker.usage_by_agent()
        usage["agent_a"] = 9999  # mutate copy
        assert tracker.usage_by_agent()["agent_a"] == 50  # original unchanged

    def test_sessions_are_independent(self):
        t1 = TokenTracker(session_id="s1", budget=10000)
        t2 = TokenTracker(session_id="s2", budget=10000)
        t1.record("agent_a", 500)
        assert t2.total == 0

    def test_make_callback_records_tokens(self):
        from unittest.mock import MagicMock

        tracker = TokenTracker(session_id="s1", budget=10000)
        callback = tracker.make_callback("test_agent")

        mock_ctx = MagicMock()
        mock_ctx.session.id = "s1"

        mock_response = MagicMock()
        mock_response.usage_metadata.total_token_count = 42

        callback(mock_ctx, mock_response)
        assert tracker.total == 42
        assert tracker.usage_by_agent()["test_agent"] == 42

    def test_make_callback_raises_on_budget_exceeded(self):
        from unittest.mock import MagicMock

        tracker = TokenTracker(session_id="s1", budget=10)
        callback = tracker.make_callback("test_agent")

        mock_ctx = MagicMock()
        mock_ctx.session.id = "s1"
        mock_response = MagicMock()
        mock_response.usage_metadata.total_token_count = 11

        with pytest.raises(BudgetExceededError):
            callback(mock_ctx, mock_response)

    def test_make_callback_handles_missing_usage_metadata(self):
        from unittest.mock import MagicMock

        tracker = TokenTracker(session_id="s1", budget=10000)
        callback = tracker.make_callback("test_agent")

        mock_ctx = MagicMock()
        mock_ctx.session.id = "s1"
        mock_response = MagicMock()
        mock_response.usage_metadata = None

        # Should not raise; records 0 tokens
        result = callback(mock_ctx, mock_response)
        assert result is None
        assert tracker.total == 0
