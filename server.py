"""
Group: [Insert Group Number]
Date: 2026-03-16
Members: [Name 1], [Name 2], [Name 3]
"""
from mesa.visualization import SolaraViz, make_space_component
from model import RobotMission

def agent_portrayal(agent):
    """Maps each agent type to a shape, color, and size on the Solara grid."""
    if agent is None:
        return
    
    # --- THE FLOOR ---
    if type(agent).__name__ == "RadioactivityAgent":
        if agent.zone == "z1":
            color = "#e0ffe0" # Light green
        elif agent.zone == "z2":
            color = "#ffffe0" # Light yellow
        else:
            color = "#ffe0e0" # Light red
        return {"color": color, "marker": "s", "size": 500} # 's' for square

    # --- THE DISPOSAL ZONE ---
    elif type(agent).__name__ == "WasteDisposalZoneAgent":
        return {"color": "black", "marker": "s", "size": 500}

    # --- THE WASTE ---
    elif type(agent).__name__ == "WasteAgent":
        return {"color": agent.color, "marker": "o", "size": 50} # 'o' for circle

    # --- THE ROBOTS ---
    elif type(agent).__name__ in ["GreenAgent", "YellowAgent", "RedAgent"]:
        if type(agent).__name__ == "GreenAgent":
            color = "darkgreen"
        elif type(agent).__name__ == "YellowAgent":
            color = "goldenrod"
        elif type(agent).__name__ == "RedAgent":
            color = "darkred"
        return {"color": color, "marker": "o", "size": 150}

# 1. Create the grid component using the portrayal function
SpaceGraph = make_space_component(agent_portrayal)

# 2. Define the starting parameters for the model
model_params = {
    "width": 15,
    "height": 10,
    "initial_green_wastes": 10,
    "num_green_robots": 2,
    "num_yellow_robots": 2,
    "num_red_robots": 1
}

# 3. Build the Solara page
page = SolaraViz(
    model=RobotMission,
    model_params=model_params,
    components=[SpaceGraph],
    name="Robot Waste Cleanup Mission"
)