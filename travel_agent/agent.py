from google.adk.agents import Agent
from travel_agent.supporting_agents import travel_inspiration_agent


# LLM = "gemini-3-flash-preview"
# LLM = "gemini-2.5-flash"
LLM = "gemini-2.5-flash-lite"
root_agent = Agent(
    model=LLM,
    name="travel_planner_main",
    description="A helpful travel planning assistant that helps users plan their trips by providing information and suggestions based on their preferences.",
    instruction="""
            - You are an exclusive travel concierge agent
            - You help users to discover their dream holiday destination and plan their vacation.
            - Use the inspiration_agent to get the best destination, news, places nearby e.g hotels, cafes, etc near attractions and points of interest for the user.
            - You cannot use any tool directly. 
            """,
    sub_agents=[travel_inspiration_agent]
)