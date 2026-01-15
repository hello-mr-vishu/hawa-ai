from travel_agent.tools import find_nearby_places_open
from travel_agent.supporting_agents import places_agent, travel_inspiration_agent

def test_tool_direct():
    print("\n--- Testing find_nearby_places_open direct call ---")
    # Test with a known location
    result = find_nearby_places_open("hotel", "Visakhapatnam", limit=2)
    print(f"Result (Visakhapatnam): {result}")

def test_places_agent():
    print("\n--- Testing places_agent generic call ---")
    print(f"Agent attributes: {dir(places_agent)}")
    try:
        # Attempt to guess the method if .run() failed
        if hasattr(places_agent, 'query'):
            response = places_agent.query("Find hotels near Cricket Stadium in Madhurawada, Visakhapatnam")
        elif hasattr(places_agent, 'chat'):
            response = places_agent.chat("Find hotels near Cricket Stadium in Madhurawada, Visakhapatnam")
        else:
             print("Could not find a run/query/chat method. Please check attributes above.")
             return

        print(f"Agent Response: {response}")
    except Exception as e:
        print(f"Agent Error: {e}")

def test_inspiration_agent():
    print("\n--- Testing travel_inspiration_agent nested call ---")
    try:
        response = travel_inspiration_agent.run("Give me a 5 day trip plan near cricket stadium madhurvada , visakhapatnam")
        print(f"Inspiration Agent Response: {response}")
    except Exception as e:
        print(f"Inspiration Agent Error: {e}")

if __name__ == "__main__":
    test_tool_direct()
    test_places_agent()
    # Uncomment the below if you want to test the full chain, but let's start small
    # test_inspiration_agent()
