"""
Group: 13
Date: 2026-03-23
Members: Aymane Chalh, Team MAS 13
"""
from mesa.visualization import Slider, SolaraViz, make_plot_component, make_space_component
from model import RobotMission

def agent_portrayal(agent):
    """Maps each agent type to a shape, color, and size on the Solara grid."""
    if agent is None:
        return

    # --- THE FLOOR ---
    if type(agent).__name__ == "RadioactivityAgent":
        if agent.zone == "z1":
            color = "#e0ffe0"
        elif agent.zone == "z2":
            color = "#ffffe0"
        else:
            color = "#ffe0e0"
        return {"color": color, "marker": "s", "size": 500}

    # --- THE DISPOSAL ZONE ---
    elif type(agent).__name__ == "WasteDisposalZoneAgent":
        return {"color": "black", "marker": "s", "size": 500}

    # --- THE WASTE ---
    elif type(agent).__name__ == "WasteAgent":
        return {"color": agent.color, "marker": "o", "size": 50}

    # --- THE ROBOTS ---
    elif type(agent).__name__ in ["GreenAgent", "YellowAgent", "RedAgent"]:
        if type(agent).__name__ == "GreenAgent":
            color = "darkgreen"
        elif type(agent).__name__ == "YellowAgent":
            color = "goldenrod"
        else:
            color = "darkred"
        return {"color": color, "marker": "o", "size": 150}


SpaceGraph = make_space_component(agent_portrayal)
WastePlot = make_plot_component(["Green Waste", "Yellow Waste", "Red Waste", "Total Waste"])
DisposedPlot = make_plot_component(["Disposed Red Waste"])
MessagePlot = make_plot_component(["Messages Sent", "Messages Expired", "Messages Consumed", "Active Messages"])
ScorePlot = make_plot_component(["Objective Score"])

model_params = {
    "width": Slider("Grid Width", value=15, min=9, max=40, step=1, dtype=int),
    "height": Slider("Grid Height", value=10, min=6, max=30, step=1, dtype=int),
    "initial_green_wastes": Slider("Initial Green Wastes", value=10, min=1, max=120, step=1, dtype=int),
    "num_green_robots": Slider("Green Robots", value=2, min=1, max=20, step=1, dtype=int),
    "num_yellow_robots": Slider("Yellow Robots", value=2, min=1, max=20, step=1, dtype=int),
    "num_red_robots": Slider("Red Robots", value=1, min=1, max=20, step=1, dtype=int),
    "message_ttl": Slider("Message TTL", value=10, min=1, max=50, step=1, dtype=int),
    "strategy": Slider("Strategy (0/10/20)", value=20, min=0, max=20, step=10, dtype=int),
    "seed": Slider("Random Seed", value=42, min=0, max=9999, step=1, dtype=int),
}

default_model = RobotMission(
    width=15,
    height=10,
    initial_green_wastes=10,
    num_green_robots=2,
    num_yellow_robots=2,
    num_red_robots=1,
    message_ttl=10,
    strategy="comm",
    seed=42,
)

page = SolaraViz(
    model=default_model,
    components=[SpaceGraph, WastePlot, DisposedPlot, MessagePlot, ScorePlot],
    model_params=model_params,
    name="Robot Waste Cleanup Mission"
)
