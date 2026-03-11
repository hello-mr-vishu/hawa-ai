"""Session-scoped token budget tracker using ADK after_model_callback hooks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.models.llm_response import LlmResponse

from travel_agent.core.logging import get_logger

logger = get_logger(__name__)


class BudgetExceededError(Exception):
    """Raised when a session exceeds its token budget."""


class TokenTracker:
    """Tracks token usage per agent within a single session."""

    def __init__(self, session_id: str, budget: int):
        self.session_id = session_id
        self.budget = budget
        # agent_name → cumulative tokens used
        self._usage: dict[str, int] = {}

    @property
    def total(self) -> int:
        return sum(self._usage.values())

    def usage_by_agent(self) -> dict[str, int]:
        return dict(self._usage)

    def record(self, agent_name: str, tokens: int) -> None:
        self._usage[agent_name] = self._usage.get(agent_name, 0) + tokens
        logger.info(
            "Token usage recorded",
            extra={
                "extra": {
                    "session_id": self.session_id,
                    "agent": agent_name,
                    "tokens_this_call": tokens,
                    "session_total": self.total,
                    "budget": self.budget,
                }
            },
        )

    def make_callback(self, agent_name: str):
        """Returns an after_model_callback that records usage and enforces the budget."""
        tracker = self

        def _after_model_callback(
            ctx: "CallbackContext", response: "LlmResponse"
        ) -> Optional["LlmResponse"]:
            tokens = 0
            if response.usage_metadata and response.usage_metadata.total_token_count:
                tokens = response.usage_metadata.total_token_count
            tracker.record(agent_name, tokens)
            if tracker.total > tracker.budget:
                raise BudgetExceededError(
                    f"Session '{tracker.session_id}' exceeded token budget of {tracker.budget}. "
                    f"Used: {tracker.total} tokens."
                )
            return None  # pass-through; do not modify the response

        return _after_model_callback


# Global in-memory registry: session_id → TokenTracker
# Sufficient for dev/MVP; replace with Redis or DB-backed store for multi-instance prod.
_registry: dict[str, TokenTracker] = {}


def get_or_create_tracker(session_id: str, budget: int) -> TokenTracker:
    if session_id not in _registry:
        _registry[session_id] = TokenTracker(session_id=session_id, budget=budget)
    return _registry[session_id]


def get_tracker(session_id: str) -> Optional[TokenTracker]:
    return _registry.get(session_id)
