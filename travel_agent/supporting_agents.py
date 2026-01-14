from google.adk.agents import Agent
from google.adk.tools import AgentTool
from travel_agent.tools import google_search_grounding
# LLM = "gemini-3-flash-preview"
LLM = "gemini-2.5-flash"


news_agent = Agent(
    model=LLM,
    name="news_agent",
    description="Suggests key travel events and news; uses search for current info.",
    instruction="""
            You are responsible for providing a list of events and news recommendations based on the user's query. 
            Limit the choices to 10 results. You need to use the google_search_grounding agent tool to search the web for information.
        """,
    tools=[google_search_grounding]    
)

# places_agent = Agent(
#     model=LLM,
#     name="places_agent",
#     description="Suggests locations based on user preferences",
#     instruction="""
#             You are responsible for making suggestions on actual places based on the user's query. Limit the choices to 10 results.
#             Each place must have a name, location, and address.
#             You can use the places_tool to find the latitude and longitude of the place and address.
#         """,
#     tools=[location_search_tool]    
# )

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
    tools=[AgentTool(agent=news_agent)]
)
