"""
Group: 13
Date: 2026-04-03
Members: Aymane Chalh, Adham Noureldin, Mohamed Benkirane, Team MAS 13
"""
from objects import WasteAgent


def next_position(pos, direction):
    """Return the adjacent position reached by moving in one cardinal direction."""
    x, y = pos
    if direction == "north":
        return (x, y + 1)
    if direction == "south":
        return (x, y - 1)
    if direction == "east":
        return (x + 1, y)
    if direction == "west":
        return (x - 1, y)
    return pos


def do_move(grid, agent, target_pos):
    """Move an agent to a validated target position."""
    grid.move_agent(agent, target_pos)


def do_pick_up(grid, agent, color):
    """Pick one waste of the requested color from the current tile if present."""
    contents = grid.get_cell_list_contents([agent.pos])
    for obj in contents:
        if isinstance(obj, WasteAgent) and obj.color == color:
            grid.remove_agent(obj)
            obj.remove()
            agent.knowledge["inventory"].append(color)
            return True
    return False


def do_transform(inventory, from_color, to_color):
    """Transform two wastes of one color into one waste of another color."""
    if inventory.count(from_color) < 2:
        return False
    inventory.remove(from_color)
    inventory.remove(from_color)
    inventory.append(to_color)
    return True


def do_put_down(grid, agent, color):
    """Drop one waste from inventory to the current grid cell."""
    inventory = agent.knowledge.get("inventory", [])
    if color not in inventory:
        return False
    inventory.remove(color)
    grid.place_agent(WasteAgent(agent.model, color), agent.pos)
    return True
