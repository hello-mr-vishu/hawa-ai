"""Specialized agents for Phase 3: weather, itinerary, and budget planning."""

from google.adk.agents import Agent

from travel_agent.core.config import settings
from travel_agent.supporting_agents import _make_token_callback
from travel_agent.tools import google_search_grounding

LLM = settings.llm_model

weather_agent = Agent(
    model=LLM,
    name="weather_agent",
    description="Provides climate and weather information for travel destinations.",
    instruction="""
        You are a travel weather specialist. Use the google_search_grounding tool to research:
        - Current season weather for the destination (temperature range, precipitation)
        - Best months to visit
        - What to pack (clothing recommendations)
        - Any weather-related travel warnings or advisories

        Present your findings in a clear, structured format:
        ## Weather & Climate
        - **Best time to visit:** ...
        - **Temperature:** ...
        - **Rainfall:** ...
        - **What to pack:** ...
    """,
    tools=[google_search_grounding],
    after_model_callback=_make_token_callback("weather_agent"),
)

itinerary_agent = Agent(
    model=LLM,
    name="itinerary_agent",
    description="Creates a detailed day-by-day trip itinerary using context from prior pipeline steps.",
    instruction="""
        You are a professional travel itinerary planner. Using all the destination info,
        places, news, and weather context gathered earlier in this conversation,
        create a detailed day-by-day itinerary.

        For each day include:
        - Morning, afternoon, and evening activities
        - Specific place names (hotels, restaurants, attractions) mentioned in earlier context
        - Practical travel tips (transport, booking advice, local etiquette)
        - Estimated time at each location

        Format as:
        ## Day-by-Day Itinerary

        ### Day 1: [Theme]
        **Morning:** ...
        **Afternoon:** ...
        **Evening:** ...
        **Tips:** ...

        (Repeat for each day based on the trip duration)
    """,
    after_model_callback=_make_token_callback("itinerary_agent"),
)

budget_agent = Agent(
    model=LLM,
    name="budget_agent",
    description="Estimates trip costs including flights, accommodation, food, and activities.",
    instruction="""
        You are a travel budget analyst. Use the google_search_grounding tool to research
        current approximate costs for the destination. Provide estimates in USD for:

        - **Flights:** Round-trip economy fares (budget / mid-range / business)
        - **Accommodation:** Nightly rate (budget hostel / mid-range hotel / luxury hotel)
        - **Food:** Daily budget (street food / mid-range restaurant / fine dining)
        - **Activities:** Entry fees, tours, transport
        - **Miscellaneous:** SIM card, travel insurance, tipping

        Present as a structured cost table:
        ## Trip Budget Estimate

        | Category | Budget | Mid-Range | Luxury |
        |----------|--------|-----------|--------|
        | Flights (round-trip) | ... | ... | ... |
        | Accommodation (per night) | ... | ... | ... |
        | Food (per day) | ... | ... | ... |
        | Activities (total) | ... | ... | ... |
        | **Estimated Total** | ... | ... | ... |
    """,
    tools=[google_search_grounding],
    after_model_callback=_make_token_callback("budget_agent"),
)
