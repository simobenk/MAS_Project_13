"""
Group: 13
Date: 2026-04-03
Members: Aymane Chalh, Adham Noureldin, Mohamed Benkirane, Team MAS 13
"""
from agents_base import GreenRobotBase, YellowRobotBase, RedRobotBase


class _NoCommMixin:
    """Shared no-communication decision logic with anti-deadlock safeguards."""

    def _deliberate_no_comm(self, knowledge, strategy):
        percepts = knowledge["time_steps"][-1]["percepts"] if knowledge["time_steps"] else {}
        inventory = knowledge.get("inventory", [])
        current_pos = percepts.get("current_pos")

        if self.combined_waste is not None and self.combined_waste in inventory:
            if self._at_handoff_border(percepts):
                return {"type": "put_down", "color": self.combined_waste}
            return {"type": "move", "direction": "east"}

        if self.combined_waste is None and "red" in inventory:
            if self._is_disposal_tile(percepts):
                return {"type": "put_down", "color": "red"}
            direction = self._direction_towards(current_pos, percepts.get("disposal_zone_pos"))
            return {"type": "move", "direction": direction or "east"}

        if self.combined_waste is not None and inventory.count(self.target_waste) >= 2:
            return {"type": "transform", "from": self.target_waste, "to": self.combined_waste}

        hold_steps = knowledge["hold_timer"].get(self.target_waste, 0)
        if self._holds_one_target() and hold_steps >= self.MAX_HOLD_STEPS and self._at_origin_or_border(percepts):
            return {"type": "put_down", "color": self.target_waste}

        if self._can_pick_from_current_tile(percepts, self.target_waste) and len(inventory) < 2:
            return {"type": "pick_up", "color": self.target_waste}

        if strategy == "memory_no_comm":
            adjacent_direction = self._direction_to_adjacent_waste(percepts, self.target_waste)
            if adjacent_direction:
                return {"type": "move", "direction": adjacent_direction}

            target_pos = self._nearest_known_waste(
                self.target_waste,
                current_pos,
                allowed_zones=self.allowed_message_zones,
            )
            direction = self._direction_towards(current_pos, target_pos)
            if direction:
                return {"type": "move", "direction": direction}

        return {"type": "move", "direction": self._default_random_direction(strategy)}


class GreenRobotNoComm(_NoCommMixin, GreenRobotBase):
    """Green robot for no-communication strategies."""

    def deliberate(self, knowledge):
        percepts = knowledge["time_steps"][-1]["percepts"] if knowledge["time_steps"] else {}
        strategy = self._strategy_from_percepts(percepts)
        if strategy == "comm":
            strategy = "memory_no_comm"
        return self._deliberate_no_comm(knowledge, strategy)


class YellowRobotNoComm(_NoCommMixin, YellowRobotBase):
    """Yellow robot for no-communication strategies."""

    def deliberate(self, knowledge):
        percepts = knowledge["time_steps"][-1]["percepts"] if knowledge["time_steps"] else {}
        strategy = self._strategy_from_percepts(percepts)
        if strategy == "comm":
            strategy = "memory_no_comm"
        return self._deliberate_no_comm(knowledge, strategy)


class RedRobotNoComm(_NoCommMixin, RedRobotBase):
    """Red robot for no-communication strategies."""

    def deliberate(self, knowledge):
        percepts = knowledge["time_steps"][-1]["percepts"] if knowledge["time_steps"] else {}
        strategy = self._strategy_from_percepts(percepts)
        if strategy == "comm":
            strategy = "memory_no_comm"
        return self._deliberate_no_comm(knowledge, strategy)
