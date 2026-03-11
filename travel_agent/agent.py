from google.adk.agents import SequentialAgent

from travel_agent.specialized_agents import budget_agent, itinerary_agent, weather_agent
from travel_agent.supporting_agents import travel_inspiration_agent

# Full trip planning pipeline: each step passes its output as context to the next.
# SequentialAgent guarantees deterministic execution order, unlike LlmAgent routing.
root_agent = SequentialAgent(
    name="trip_planner_pipeline",
    description=(
        "End-to-end trip planning pipeline: inspires destination, fetches weather, "
        "builds day-by-day itinerary, and estimates budget."
    ),
    sub_agents=[
        travel_inspiration_agent,  # Step 1: destination inspiration + news + nearby places
        weather_agent,             # Step 2: climate & packing guide
        itinerary_agent,           # Step 3: day-by-day itinerary (uses prior context)
        budget_agent,              # Step 4: cost breakdown
    ],
)
