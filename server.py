"""
Group: 13
Date: 2026-04-03
Members: Aymane Chalh, Adham Noureldin, Mohamed Benkirane, Team MAS 13
"""
from mesa.visualization import Slider, SolaraViz, make_plot_component, make_space_component
from mesa.visualization.components import AgentPortrayalStyle

from model import RobotMission


ZONE_COLORS = {
    "z1": "#d9f2e3",
    "z2": "#fdf1c7",
    "z3": "#f7d7d5",
}


def style_space(ax):
    """Paint zone backgrounds and a clean grid for readability."""
    _, x_max = ax.get_xlim()
    _, y_max = ax.get_ylim()
    width = int(round(x_max + 0.5))
    height = int(round(y_max + 0.5))

    z1_bound = width // 3
    z2_bound = 2 * (width // 3)

    ax.axvspan(-0.5, z1_bound - 0.5, facecolor=ZONE_COLORS["z1"], zorder=0)
    ax.axvspan(z1_bound - 0.5, z2_bound - 0.5, facecolor=ZONE_COLORS["z2"], zorder=0)
    ax.axvspan(z2_bound - 0.5, width - 0.5, facecolor=ZONE_COLORS["z3"], zorder=0)

    for x in range(width + 1):
        ax.axvline(x - 0.5, color="#ffffff", linewidth=0.7, alpha=0.7, zorder=0.4)
    for y in range(height + 1):
        ax.axhline(y - 0.5, color="#ffffff", linewidth=0.7, alpha=0.7, zorder=0.4)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal", adjustable="box")


def agent_portrayal(agent):
    """Map each agent type to a shape, color and size on the Solara grid."""
    if agent is None:
        return None

    class_name = type(agent).__name__

    if class_name == "RadioactivityAgent":
        return AgentPortrayalStyle(
            color="#000000",
            marker="s",
            size=1,
            edgecolors="#000000",
            linewidths=0.0,
            alpha=0.0,
            zorder=0,
        )

    if class_name == "WasteDisposalZoneAgent":
        return AgentPortrayalStyle(
            color="#111827",
            marker="s",
            size=165,
            edgecolors="#f8fafc",
            linewidths=1.4,
            alpha=0.98,
            zorder=1,
        )

    if class_name == "WasteAgent":
        palette = {"green": "#22c55e", "yellow": "#eab308", "red": "#ef4444"}
        return AgentPortrayalStyle(
            color=palette.get(agent.color, agent.color),
            marker="o",
            size=70,
            edgecolors="#0f172a",
            linewidths=0.9,
            alpha=1.0,
            zorder=1,
        )

    if hasattr(agent, "target_waste"):
        role_color = {
            "green": "#166534",
            "yellow": "#a16207",
            "red": "#991b1b",
        }
        return AgentPortrayalStyle(
            color=role_color.get(getattr(agent, "target_waste", "green"), "#334155"),
            marker="o",
            size=200,
            edgecolors="#ffffff",
            linewidths=1.6,
            alpha=1.0,
            zorder=1,
        )

    return None


SpaceGraph = make_space_component(agent_portrayal, post_process=style_space, draw_grid=False)
WastePlot = make_plot_component(["Green Waste", "Yellow Waste", "Red Waste", "Total Waste"])
DisposedPlot = make_plot_component(["Disposed Red Waste"])
MessageTotalsPlot = make_plot_component(["Messages Sent", "Messages Expired", "Messages Consumed", "Active Messages"])
CommChannelsPlot = make_plot_component(["Comm 1 Sent", "Comm 2 Sent", "Comm 1 Consumed", "Comm 2 Consumed"])
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
    components=[SpaceGraph, WastePlot, DisposedPlot, MessageTotalsPlot, CommChannelsPlot, ScorePlot],
    model_params=model_params,
    name="Robot Waste Cleanup Mission",
)
