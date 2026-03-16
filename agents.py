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
    def __init__(self, unique_id, model):
        super().__init__(model)
        self.knowledge = {
            "time_steps": [], # Will store dictionaries of {"percepts": ..., "action": ...}
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
        # Store the chosen action in our knowledge history
        self.knowledge["time_steps"][-1]["action"] = action 
        # The environment (model) performs the action and returns new percepts
        self.percepts = self.model.do(self, action)


class GreenAgent(BaseRobot):
    """Moves only in z1. Collects 2 green, transforms to 1 yellow."""
    
    @staticmethod
    def deliberate(knowledge):
        inventory = knowledge.get("inventory", [])
        latest_step = knowledge["time_steps"][-1] if knowledge["time_steps"] else {}
        percepts = latest_step.get("percepts", {})
        current_tile = percepts.get("current_tile", [])

        # Priority 1: If possession of 1 yellow waste, transport it further east
        if "yellow" in inventory:
            return {"type": "move", "direction": "east"}
            
        # Priority 2: If possession of 2 green wastes then transformation into 1 yellow waste
        if inventory.count("green") >= 2:
            return {"type": "transform", "from": "green", "to": "yellow"}
            
        # Priority 3: Walk to pick up 2 initial wastes (i.e. green)
        for obj in current_tile:
            if getattr(obj, "color", None) == "green":
                return {"type": "pick_up", "color": "green"}
                
        # Priority 4: Explore to find waste
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

        # Priority 1: If possession of 1 red waste, transport it further east
        if "red" in inventory:
            return {"type": "move", "direction": "east"}
            
        # Priority 2: If possession of 2 yellow wastes then transformation into 1 red waste
        if inventory.count("yellow") >= 2:
            return {"type": "transform", "from": "yellow", "to": "red"}
            
        # Priority 3: Walk to pick up 2 initial yellow wastes
        for obj in current_tile:
            if getattr(obj, "color", None) == "yellow":
                return {"type": "pick_up", "color": "yellow"}
                
        # Priority 4: Explore
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

        # Priority 1: If possession of 1 red waste then transport it further east on the "waste disposal zone", the waste is then "put away"
        if "red" in inventory:
            # Check if we are standing on the disposal zone
            for obj in current_tile:
                if getattr(obj, "is_disposal_zone", False):
                    return {"type": "put_down", "color": "red"}
            # If not there yet, keep moving east
            return {"type": "move", "direction": "east"}
            
        # Priority 2: Walk to pick up 1 red waste
        for obj in current_tile:
            if getattr(obj, "color", None) == "red":
                return {"type": "pick_up", "color": "red"}
                
        # Priority 3: Explore
        directions = ["north", "south", "east", "west", "west"] # Bias west to find yellow robots passing the baton
        return {"type": "move", "direction": random.choice(directions)}