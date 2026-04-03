"""
Group: 13
Date: 2026-03-23
Members: Aymane Chalh, Adham Noureldin, Mohamed Benkirane, Team MAS 13
"""
import random
from mesa import Agent

class RadioactivityAgent(Agent):
    """
    Static agent representing the radioactivity level of a grid cell.
    """
    def __init__(self, model, zone):
        super().__init__(model)
        self.zone = zone
        self.radioactivity = self._generate_radioactivity()

    def _generate_radioactivity(self):
        if self.zone == "z1":
            return random.uniform(0.0, 0.33)
        elif self.zone == "z2":
            return random.uniform(0.33, 0.66)
        elif self.zone == "z3":
            return random.uniform(0.66, 1.0)
        return 0.0

class WasteAgent(Agent):
    """
    Static agent representing a piece of waste on the grid.
    """
    def __init__(self, model, color):
        super().__init__(model)
        self.color = color

class WasteDisposalZoneAgent(Agent):
    """
    Static agent representing the final destination for red waste.
    """
    def __init__(self, model):
        super().__init__(model)
        self.is_disposal_zone = True
