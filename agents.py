"""
Group: 13
Date: 2026-03-23
Members: Aymane Chalh, Team MAS 13
"""
import random
from mesa import Agent


class BaseRobot(Agent):
    """Common robot loop and pure helper functions used by all robot types."""

    def __init__(self, model):
        super().__init__(model)
        self.knowledge = {
            "time_steps": [],
            "inventory": [],
            "messages_seen": [],
        }
        self.percepts = {}

    def update(self, knowledge, percepts):
        """Updates knowledge with the latest percepts while preventing memory leaks."""
        knowledge["time_steps"].append({"percepts": percepts, "action": None})
        
        # FIX: Cap the memory to the last 5 steps to prevent unbounded memory growth
        knowledge["time_steps"] = knowledge["time_steps"][-5:]
        
        if percepts.get("messages"):
            knowledge["messages_seen"].extend(percepts["messages"])
            # FIX: Cap the message history too
            knowledge["messages_seen"] = knowledge["messages_seen"][-50:]

    def deliberate(self, knowledge):
        """The reasoning step. Must only depend on `knowledge`."""
        return {"type": "wait"}

    @staticmethod
    def _tile_zone(contents):
        for obj in contents:
            radioactivity = getattr(obj, "radioactivity", None)
            if radioactivity is None:
                continue
            # FIX: Use <= to ensure exact boundary values (0.33, 0.66) are categorized correctly
            if radioactivity <= 0.33:
                return "z1"
            if radioactivity <= 0.66:
                return "z2"
            return "z3"
        return None

    @staticmethod
    def _message_from_local_percepts(percepts, color):
        current_pos = percepts.get("current_pos")
        current_tile = percepts.get("current_tile", [])
        adjacent = percepts.get("adjacent_tiles", {})

        for obj in current_tile:
            if getattr(obj, "color", None) == color:
                return {
                    "waste_color": color,
                    "position": current_pos,
                    "zone": BaseRobot._tile_zone(current_tile),
                }

        for pos, contents in adjacent.items():
            for obj in contents:
                if getattr(obj, "color", None) == color:
                    return {
                        "waste_color": color,
                        "position": pos,
                        "zone": BaseRobot._tile_zone(contents),
                    }
        return None

    @staticmethod
    def _choose_target_from_messages(messages, color, allowed_zones=None):
        for message in reversed(messages):
            content = message.get("content", {})
            waste_color = message.get("waste_color", content.get("waste_color"))
            zone = message.get("zone", content.get("zone"))
            if waste_color != color:
                continue
            if allowed_zones and zone not in allowed_zones:
                continue
            position = message.get("position", content.get("position"))
            if isinstance(position, (list, tuple)) and len(position) == 2:
                return {
                    "id": message.get("id"),
                    "position": tuple(position),
                }
        return None

    @staticmethod
    def _direction_towards(current_pos, target_pos):
        if not current_pos or not target_pos:
            return None
        x, y = current_pos
        tx, ty = target_pos
        options = []
        if tx > x:
            options.append("east")
        elif tx < x:
            options.append("west")
        if ty > y:
            options.append("north")
        elif ty < y:
            options.append("south")
        return options[0] if options else None

    @staticmethod
    def _strategy_from_percepts(percepts):
        strategy = percepts.get("strategy", "comm")
        if strategy in {"random_no_comm", "memory_no_comm", "comm"}:
            return strategy
        return "comm"

    @staticmethod
    def _direction_to_adjacent_waste(percepts, color):
        adjacent_by_direction = percepts.get("adjacent_by_direction", {})
        for direction, contents in adjacent_by_direction.items():
            for obj in contents:
                if getattr(obj, "color", None) == color:
                    return direction
        return None

    def step(self):
        """Percepts -> deliberate -> model.do."""
        self.update(self.knowledge, self.percepts)
        action = self.deliberate(self.knowledge)
        self.knowledge["time_steps"][-1]["action"] = action
        self.percepts = self.model.do(self, action)

    def step_agent(self):
        """Alias kept for strict alignment with the project handout."""
        self.step()


class GreenAgent(BaseRobot):
    """Moves only in z1. Collects 2 green, transforms to 1 yellow."""

    @staticmethod
    def deliberate(knowledge):
        inventory = knowledge.get("inventory", [])
        latest_step = knowledge["time_steps"][-1] if knowledge["time_steps"] else {}
        percepts = latest_step.get("percepts", {})
        current_tile = percepts.get("current_tile", [])
        adjacent_by_direction = percepts.get("adjacent_by_direction", {})
        strategy = BaseRobot._strategy_from_percepts(percepts)

        broadcast = None
        if strategy == "comm":
            broadcast = BaseRobot._message_from_local_percepts(percepts, "green")
        action = None

        if "yellow" in inventory:
            current_zone = BaseRobot._tile_zone(current_tile)
            east_zone = BaseRobot._tile_zone(adjacent_by_direction.get("east", []))
            if current_zone == "z1" and east_zone == "z2":
                action = {"type": "put_down", "color": "yellow"}
            else:
                action = {"type": "move", "direction": "east"}

        elif inventory.count("green") >= 2:
            action = {"type": "transform", "from": "green", "to": "yellow"}

        else:
            for obj in current_tile:
                if getattr(obj, "color", None) == "green":
                    action = {"type": "pick_up", "color": "green"}
                    break

            if action is None:
                current_pos = percepts.get("current_pos")
                if strategy == "comm":
                    messages = percepts.get("messages", [])
                    target = BaseRobot._choose_target_from_messages(messages, "green", {"z1"})
                    direction = BaseRobot._direction_towards(
                        current_pos, target["position"] if target else None
                    )
                    if direction:
                        action = {"type": "move", "direction": direction}
                        if target.get("id") is not None:
                            action["consume_message_id"] = target["id"]
                elif strategy == "memory_no_comm":
                    direction = BaseRobot._direction_to_adjacent_waste(percepts, "green")
                    if direction:
                        action = {"type": "move", "direction": direction}

                if action is None:
                    directions = ["north", "south", "east", "west"]
                    if strategy == "memory_no_comm":
                        directions = ["east", "east", "north", "south", "west"]
                    action = {"type": "move", "direction": random.choice(directions)}

        if broadcast:
            action["broadcast"] = broadcast
        return action


class YellowAgent(BaseRobot):
    """Moves in z1 and z2. Collects 2 yellow, transforms to 1 red."""

    @staticmethod
    def deliberate(knowledge):
        inventory = knowledge.get("inventory", [])
        latest_step = knowledge["time_steps"][-1] if knowledge["time_steps"] else {}
        percepts = latest_step.get("percepts", {})
        current_tile = percepts.get("current_tile", [])
        adjacent_by_direction = percepts.get("adjacent_by_direction", {})
        strategy = BaseRobot._strategy_from_percepts(percepts)

        broadcast = None
        if strategy == "comm":
            broadcast = BaseRobot._message_from_local_percepts(percepts, "yellow")
        action = None

        if "red" in inventory:
            current_zone = BaseRobot._tile_zone(current_tile)
            east_zone = BaseRobot._tile_zone(adjacent_by_direction.get("east", []))
            if current_zone == "z2" and east_zone == "z3":
                action = {"type": "put_down", "color": "red"}
            else:
                action = {"type": "move", "direction": "east"}

        elif inventory.count("yellow") >= 2:
            action = {"type": "transform", "from": "yellow", "to": "red"}

        else:
            for obj in current_tile:
                if getattr(obj, "color", None) == "yellow":
                    action = {"type": "pick_up", "color": "yellow"}
                    break

            if action is None:
                current_pos = percepts.get("current_pos")
                if strategy == "comm":
                    messages = percepts.get("messages", [])
                    target = BaseRobot._choose_target_from_messages(messages, "yellow", {"z1", "z2"})
                    direction = BaseRobot._direction_towards(
                        current_pos, target["position"] if target else None
                    )
                    if direction:
                        action = {"type": "move", "direction": direction}
                        if target.get("id") is not None:
                            action["consume_message_id"] = target["id"]
                elif strategy == "memory_no_comm":
                    direction = BaseRobot._direction_to_adjacent_waste(percepts, "yellow")
                    if direction:
                        action = {"type": "move", "direction": direction}

                if action is None:
                    directions = ["north", "south", "east", "west"]
                    if strategy == "memory_no_comm":
                        directions = ["east", "east", "north", "south", "west"]
                    action = {"type": "move", "direction": random.choice(directions)}

        if broadcast:
            action["broadcast"] = broadcast
        return action


class RedAgent(BaseRobot):
    """Moves in z1, z2, z3. Collects 1 red, transports it east to dispose."""

    @staticmethod
    def deliberate(knowledge):
        inventory = knowledge.get("inventory", [])
        latest_step = knowledge["time_steps"][-1] if knowledge["time_steps"] else {}
        percepts = latest_step.get("percepts", {})
        current_tile = percepts.get("current_tile", [])
        messages = percepts.get("messages", [])
        current_pos = percepts.get("current_pos")
        strategy = BaseRobot._strategy_from_percepts(percepts)
        broadcast = None
        if strategy == "comm":
            broadcast = BaseRobot._message_from_local_percepts(percepts, "red")
        action = None

        if "red" in inventory:
            for obj in current_tile:
                if getattr(obj, "is_disposal_zone", False):
                    action = {"type": "put_down", "color": "red"}
                    break
            if action is None:
                disposal_zone_pos = percepts.get("disposal_zone_pos")
                direction = BaseRobot._direction_towards(current_pos, disposal_zone_pos)
                action = {"type": "move", "direction": direction or "east"}

        else:
            for obj in current_tile:
                if getattr(obj, "color", None) == "red":
                    action = {"type": "pick_up", "color": "red"}
                    break

            if action is None:
                if strategy == "comm":
                    target = BaseRobot._choose_target_from_messages(messages, "red", {"z2", "z3"})
                    direction = BaseRobot._direction_towards(
                        current_pos, target["position"] if target else None
                    )
                    if direction:
                        action = {"type": "move", "direction": direction}
                        if target.get("id") is not None:
                            action["consume_message_id"] = target["id"]
                elif strategy == "memory_no_comm":
                    direction = BaseRobot._direction_to_adjacent_waste(percepts, "red")
                    if direction:
                        action = {"type": "move", "direction": direction}

                if action is None:
                    directions = ["east", "east", "north", "south", "west"]
                    if strategy == "random_no_comm":
                        directions = ["north", "south", "east", "west", "west"]
                    action = {"type": "move", "direction": random.choice(directions)}

        if broadcast:
            action["broadcast"] = broadcast
        return action