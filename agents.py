"""
Group: [Insert Group Number]
Date: 2026-03-16
Members: [Name 1], [Name 2], [Name 3]
"""
import random
from mesa import Agent

class BaseRobot(Agent):
    """
    A base class for all robots to handle the core logic loop.
    Green, Yellow, and Red robots will inherit from this.
    """
    # Mesa 3.x: No unique_id parameter — assigned automatically by the framework
    def __init__(self, model):
        super().__init__(model)
        self.knowledge = {
            "time_steps": [],
            "inventory": []
        }
        self.percepts = {}

    def update(self, knowledge, percepts):
        """Updates knowledge with the latest percepts."""
        knowledge["time_steps"].append({"percepts": percepts, "action": None})

    def deliberate(self, knowledge):
        """
        The reasoning step. Takes knowledge and returns an action.
        MUST NOT access any variable outside knowledge.
        """
        action = {"type": "wait"}
        return action

    def step(self):
        """
        Mesa uses 'step' by default to advance agents.
        We use it to run the assigned procedural loop.
        """
        self.update(self.knowledge, self.percepts)
        action = self.deliberate(self.knowledge)
        self.knowledge["time_steps"][-1]["action"] = action
        self.percepts = self.model.do(self, action)


class GreenAgent(BaseRobot):
    """Moves only in z1. Collects 2 green, transforms to 1 yellow."""

    @staticmethod
    def deliberate(knowledge):
        inventory = knowledge.get("inventory", [])
        latest_step = knowledge["time_steps"][-1] if knowledge["time_steps"] else {}
        percepts = latest_step.get("percepts", {})
        current_tile = percepts.get("current_tile", [])

        if "yellow" in inventory:
            return {"type": "move", "direction": "east"}

        if inventory.count("green") >= 2:
            return {"type": "transform", "from": "green", "to": "yellow"}

        for obj in current_tile:
            if getattr(obj, "color", None) == "green":
                return {"type": "pick_up", "color": "green"}

        directions = ["north", "south", "east", "west"]
        return {"type": "move", "direction": random.choice(directions)}


class YellowAgent(BaseRobot):
    """Moves in z1 and z2. Collects 2 yellow, transforms to 1 red."""

    @staticmethod
    def deliberate(knowledge):
        inventory = knowledge.get("inventory", [])
        latest_step = knowledge["time_steps"][-1] if knowledge["time_steps"] else {}
        percepts = latest_step.get("percepts", {})
        current_tile = percepts.get("current_tile", [])

        if "red" in inventory:
            return {"type": "move", "direction": "east"}

        if inventory.count("yellow") >= 2:
            return {"type": "transform", "from": "yellow", "to": "red"}

        for obj in current_tile:
            if getattr(obj, "color", None) == "yellow":
                return {"type": "pick_up", "color": "yellow"}

        directions = ["north", "south", "east", "west"]
        return {"type": "move", "direction": random.choice(directions)}


class RedAgent(BaseRobot):
    """Moves in z1, z2, z3. Collects 1 red, transports it east to dispose."""

    @staticmethod
    def deliberate(knowledge):
        inventory = knowledge.get("inventory", [])
        latest_step = knowledge["time_steps"][-1] if knowledge["time_steps"] else {}
        percepts = latest_step.get("percepts", {})
        current_tile = percepts.get("current_tile", [])

        if "red" in inventory:
            for obj in current_tile:
                if getattr(obj, "is_disposal_zone", False):
                    return {"type": "put_down", "color": "red"}
            return {"type": "move", "direction": "east"}

        for obj in current_tile:
            if getattr(obj, "color", None) == "red":
                return {"type": "pick_up", "color": "red"}

        directions = ["north", "south", "east", "west", "west"]
        return {"type": "move", "direction": random.choice(directions)}