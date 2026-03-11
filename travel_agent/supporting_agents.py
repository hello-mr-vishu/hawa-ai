from typing import TYPE_CHECKING, Optional

from google.adk.agents import Agent
from google.adk.tools import AgentTool

from travel_agent.core.config import settings
from travel_agent.tools import google_search_grounding, location_search_tool

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.models.llm_response import LlmResponse

LLM = settings.llm_model


def _make_token_callback(agent_name: str):
    """Returns an after_model_callback that routes token recording to the session's tracker."""

    def _after_model_callback(
        ctx: "CallbackContext", response: "LlmResponse"
    ) -> Optional["LlmResponse"]:
        # Import here to avoid circular imports at module load time
        from travel_agent.core.token_tracker import BudgetExceededError, get_tracker  # noqa: PLC0415

        session_id = ctx.session.id if ctx.session else None
        if not session_id:
            return None

        tracker = get_tracker(session_id)
        if not tracker:
            return None  # no tracker registered for this session (e.g. direct ADK CLI usage)

        tokens = 0
        if response.usage_metadata and response.usage_metadata.total_token_count:
            tokens = response.usage_metadata.total_token_count
        tracker.record(agent_name, tokens)

        if tracker.total > tracker.budget:
            raise BudgetExceededError(
                f"Session '{session_id}' exceeded token budget of {tracker.budget}. "
                f"Used: {tracker.total} tokens."
            )
        return None

    return _after_model_callback


news_agent = Agent(
    model=LLM,
    name="news_agent",
    description="Suggests key travel events and news; uses search for current info.",
    instruction="""
            You are responsible for providing a list of events and news recommendations based on the user's query.
            Limit the choices to 10 results. You need to use the google_search_grounding agent tool to search the web for information.
        """,
    tools=[google_search_grounding],
    after_model_callback=_make_token_callback("news_agent"),
)

places_agent = Agent(
    model=LLM,
    name="places_agent",
    description="Suggests locations based on user preferences",
    instruction="""
            You are responsible for making suggestions on actual places based on the user's query. Limit the choices to 10 results.
            Each place must have a name, location, and address.
            You can use the places_tool to find the latitude and longitude of the place and address.
        """,
    tools=[location_search_tool],
    after_model_callback=_make_token_callback("places_agent"),
)

travel_inspiration_agent = Agent(
    model=LLM,
    name="travel_inspiration_agent",
    description="Inspires users with travel ideas. It may consult news and place agents",
    instruction="""
        You are travel inspiration agent who help users find their next big dream vacation destinations.
        Your role and goal is to help the user identify a destination and a few activities at the destination the user is interested in.

        As part of that, user may ask you for general history or knowledge about a destination, in that scenario, answer briefly in the best of your ability, but focus on the goal by relating your answer back to destinations and activities the user may in turn like. Use tools directly when required without asking for feedback from the user.

        - You will call the two tools `places_agent(inspiration query)` and `news_agent(inspiration query)` when appropriate:
        - Use `news_agent` to provide key events and news recommendations based on the user's query.
        - Use `places_agent` to provide a list of locations or nearby places to famous locations when user asks for it, for example "find hotels near eiffel tower", should return nearby hotels given some user preferences.
        """,
    tools=[AgentTool(agent=news_agent), AgentTool(agent=places_agent)],
    after_model_callback=_make_token_callback("travel_inspiration_agent"),
)
