"""
Group: 13
Date: 2026-04-03
Members: Aymane Chalh, Team MAS 13
"""
import random
from mesa import Agent


class BaseRobot(Agent):
    """Base robot implementing shared memory management and helper utilities."""

    MAX_TIME_STEPS = 40
    MAX_MESSAGES_SEEN = 120
    MAX_HOLD_STEPS = 30
    DROP_COOLDOWN = 15
    INFORM_PERIOD = 8
    COLLAB_TIMEOUT = 8

    target_waste = None
    combined_waste = None
    allowed_message_zones = None

    def __init__(self, model):
        super().__init__(model)
        self.knowledge = {
            "time_steps": [],
            "inventory": [],
            "messages_seen": [],
            "hold_timer": {},
            "held_origin": {},
            "recent_drop_pos": {},
            "known_wastes": {"green": set(), "yellow": set(), "red": set()},
            "step_index": 0,
            "next_partner_broadcast_step": 0,
            "collab": {
                "active": False,
                "waiting_accept": False,
                "role": None,
                "partner": None,
                "meeting_pos": None,
                "timeout": 0,
            },
        }
        self.percepts = {}

    def step(self):
        """Perceive -> deliberate -> act procedural loop."""
        self.update(self.knowledge, self.percepts)
        action = self.deliberate(self.knowledge)
        self.knowledge["time_steps"][-1]["action"] = action
        new_percepts = self.model.do(self, action)
        self._post_action_update(action, new_percepts)
        self.percepts = new_percepts

    def step_agent(self):
        """Alias kept for strict compatibility with project handout wording."""
        self.step()

    def update(self, knowledge, percepts):
        """Update bounded memory and timers before decision."""
        knowledge["step_index"] += 1
        knowledge["time_steps"].append({"percepts": percepts, "action": None})
        knowledge["time_steps"] = knowledge["time_steps"][-self.MAX_TIME_STEPS :]

        if percepts.get("messages"):
            knowledge["messages_seen"].extend(percepts["messages"])
            knowledge["messages_seen"] = knowledge["messages_seen"][-self.MAX_MESSAGES_SEEN :]

        self._decay_recent_drop_cooldowns()
        self._tick_collaboration_timeout()
        self._refresh_known_wastes(percepts)
        self._refresh_known_wastes_from_messages(percepts)
        self._advance_hold_timer()

    def deliberate(self, knowledge):
        """Default fallback action."""
        return {"type": "wait"}

    def _post_action_update(self, action, percepts):
        """Update local state based on action execution feedback."""
        if not isinstance(action, dict):
            return
        if not percepts.get("last_action_success", False):
            return

        action_type = action.get("type")
        current_pos = percepts.get("current_pos")

        if action_type == "pick_up":
            color = action.get("color")
            if color:
                self.knowledge["known_wastes"][color].discard(current_pos)
            if color == self.target_waste:
                self.knowledge["hold_timer"][color] = 0
                self.knowledge["held_origin"][color] = current_pos

        elif action_type == "put_down":
            color = action.get("color")
            if color == self.target_waste:
                self.knowledge["hold_timer"].pop(color, None)
                if current_pos is not None:
                    self.knowledge["recent_drop_pos"][current_pos] = self.DROP_COOLDOWN

        elif action_type == "transform":
            from_color = action.get("from")
            if from_color:
                self.knowledge["hold_timer"].pop(from_color, None)
                self.knowledge["held_origin"].pop(from_color, None)

    def _refresh_known_wastes(self, percepts):
        """Keep a lightweight local map of recently seen wastes."""
        current_pos = percepts.get("current_pos")
        current_tile = percepts.get("current_tile", [])
        adjacent = percepts.get("adjacent_tiles", {})

        local_seen = {"green": set(), "yellow": set(), "red": set()}

        if current_pos is not None:
            for obj in current_tile:
                color = getattr(obj, "color", None)
                if color in local_seen:
                    local_seen[color].add(current_pos)

        for pos, contents in adjacent.items():
            for obj in contents:
                color = getattr(obj, "color", None)
                if color in local_seen:
                    local_seen[color].add(pos)

        for color in local_seen:
            self.knowledge["known_wastes"][color].update(local_seen[color])
            if current_pos is not None and current_pos not in local_seen[color]:
                self.knowledge["known_wastes"][color].discard(current_pos)

    def _refresh_known_wastes_from_messages(self, percepts):
        """In communication mode, integrate reported waste positions into local memory."""
        if self._strategy_from_percepts(percepts) != "comm":
            return

        for msg in self._messages_for_me(percepts):
            if msg.get("performative") != "INFORM":
                continue
            content = msg.get("content", {})
            waste_color = content.get("waste_color")
            position = content.get("position")
            if waste_color in self.knowledge["known_wastes"] and isinstance(position, (tuple, list)) and len(position) == 2:
                self.knowledge["known_wastes"][waste_color].add(tuple(position))

    def _message_from_local_percepts(self, percepts, color):
        """Build a local INFORM payload when target waste is seen around the robot."""
        current_pos = percepts.get("current_pos")
        current_tile = percepts.get("current_tile", [])
        adjacent = percepts.get("adjacent_tiles", {})

        for obj in current_tile:
            if getattr(obj, "color", None) == color:
                return {
                    "waste_color": color,
                    "position": current_pos,
                    "zone": self._tile_zone(current_tile),
                }

        for pos, contents in adjacent.items():
            for obj in contents:
                if getattr(obj, "color", None) == color:
                    return {
                        "waste_color": color,
                        "position": pos,
                        "zone": self._tile_zone(contents),
                    }
        return None

    def _advance_hold_timer(self):
        """Increase hold timer when one uncombined target waste is carried."""
        if self.target_waste is None:
            return

        inventory = self.knowledge.get("inventory", [])
        target_count = inventory.count(self.target_waste)
        has_combined = self.combined_waste is not None and self.combined_waste in inventory

        if target_count == 1 and not has_combined:
            self.knowledge["hold_timer"][self.target_waste] = self.knowledge["hold_timer"].get(self.target_waste, 0) + 1
        else:
            self.knowledge["hold_timer"].pop(self.target_waste, None)

    def _decay_recent_drop_cooldowns(self):
        """Decrease cooldown values used to avoid immediate re-pick after a drop."""
        to_remove = []
        for pos, cooldown in self.knowledge["recent_drop_pos"].items():
            if cooldown <= 1:
                to_remove.append(pos)
            else:
                self.knowledge["recent_drop_pos"][pos] = cooldown - 1
        for pos in to_remove:
            del self.knowledge["recent_drop_pos"][pos]

    def _tick_collaboration_timeout(self):
        """Expire pending collaboration states after timeout."""
        collab = self.knowledge["collab"]
        if collab["timeout"] > 0:
            collab["timeout"] -= 1
        if collab["timeout"] == 0 and (collab["active"] or collab["waiting_accept"]):
            self._reset_collaboration()

    def _reset_collaboration(self):
        """Reset collaboration state machine."""
        self.knowledge["collab"] = {
            "active": False,
            "waiting_accept": False,
            "role": None,
            "partner": None,
            "meeting_pos": None,
            "timeout": 0,
        }

    def _holds_one_target(self):
        """Return True when the robot carries exactly one target waste."""
        return self.knowledge.get("inventory", []).count(self.target_waste) == 1

    def _is_disposal_tile(self, percepts):
        """Return True if current tile contains a disposal zone marker."""
        return any(getattr(obj, "is_disposal_zone", False) for obj in percepts.get("current_tile", []))

    def _at_handoff_border(self, percepts):
        """Return True when standing on the right border of the robot operational zone."""
        if self.combined_waste is None:
            return False
        current_zone = self._tile_zone(percepts.get("current_tile", []))
        east_zone = self._tile_zone(percepts.get("adjacent_by_direction", {}).get("east", []))
        if self.target_waste == "green":
            return current_zone == "z1" and east_zone == "z2"
        if self.target_waste == "yellow":
            return current_zone == "z2" and east_zone == "z3"
        return False

    def _at_origin_or_border(self, percepts):
        """Return True when current position is either origin of held waste or border."""
        current_pos = percepts.get("current_pos")
        origin = self.knowledge["held_origin"].get(self.target_waste)
        return current_pos == origin or self._at_handoff_border(percepts)

    def _can_pick_from_current_tile(self, percepts, color):
        """Return True when target color is present and not blocked by local cooldown."""
        current_pos = percepts.get("current_pos")
        if color == self.target_waste and current_pos in self.knowledge["recent_drop_pos"]:
            return False
        return any(getattr(obj, "color", None) == color for obj in percepts.get("current_tile", []))

    def _nearest_known_waste(self, color, current_pos, allowed_zones=None):
        """Return nearest known waste position by Manhattan distance."""
        candidates = []
        for pos in self.knowledge["known_wastes"].get(color, set()):
            zone = self._zone_from_pos(pos)
            if allowed_zones and zone not in allowed_zones:
                continue
            candidates.append(pos)
        if not candidates:
            return None
        return min(candidates, key=lambda p: abs(p[0] - current_pos[0]) + abs(p[1] - current_pos[1]))

    def _zone_from_pos(self, pos):
        """Map an x coordinate to z1/z2/z3."""
        z1_bound = self.model.grid.width // 3
        z2_bound = 2 * (self.model.grid.width // 3)
        x, _ = pos
        if x < z1_bound:
            return "z1"
        if x < z2_bound:
            return "z2"
        return "z3"

    @staticmethod
    def _tile_zone(contents):
        """Infer zone label from radioactivity values present in one tile."""
        for obj in contents:
            radioactivity = getattr(obj, "radioactivity", None)
            if radioactivity is None:
                continue
            if radioactivity <= 0.33:
                return "z1"
            if radioactivity <= 0.66:
                return "z2"
            return "z3"
        return None

    @staticmethod
    def _direction_towards(current_pos, target_pos):
        """Pick one cardinal direction that gets closer to target."""
        if not current_pos or not target_pos:
            return None
        x, y = current_pos
        tx, ty = target_pos
        if tx > x:
            return "east"
        if tx < x:
            return "west"
        if ty > y:
            return "north"
        if ty < y:
            return "south"
        return None

    @staticmethod
    def _strategy_from_percepts(percepts):
        """Normalize strategy from percept payload."""
        strategy = percepts.get("strategy", "comm")
        if strategy in {"random_no_comm", "memory_no_comm", "comm"}:
            return strategy
        return "comm"

    @staticmethod
    def _direction_to_adjacent_waste(percepts, color):
        """Return direction of adjacent tile containing the requested waste color."""
        for direction, contents in percepts.get("adjacent_by_direction", {}).items():
            for obj in contents:
                if getattr(obj, "color", None) == color:
                    return direction
        return None

    def _messages_for_me(self, percepts):
        """Filter message list by receiver scope."""
        messages = []
        for msg in percepts.get("messages", []):
            receiver = msg.get("receiver", "broadcast")
            if isinstance(receiver, (list, tuple, set)):
                if "broadcast" in receiver or self.team_name() in receiver or self.agent_name() in receiver:
                    messages.append(msg)
                continue
            if receiver in {"broadcast", self.team_name(), self.agent_name()}:
                messages.append(msg)
        return messages

    def _choose_target_from_messages(self, percepts, color, allowed_zones=None):
        """Choose latest compatible INFORM target from visible messages."""
        for message in reversed(self._messages_for_me(percepts)):
            if message.get("performative") != "INFORM":
                continue
            content = message.get("content", {})
            waste_color = content.get("waste_color")
            zone = content.get("zone")
            if waste_color != color:
                continue
            if allowed_zones and zone not in allowed_zones:
                continue
            position = content.get("position")
            if isinstance(position, (tuple, list)) and len(position) == 2:
                return {"id": message.get("id"), "position": tuple(position)}
        return None

    def _default_random_direction(self, strategy):
        """Draw one random direction with role-specific bias."""
        if self.target_waste == "green":
            directions = ["north", "south", "east", "west"]
            if strategy == "memory_no_comm":
                directions = ["east", "east", "north", "south", "west"]
            return random.choice(directions)

        if self.target_waste == "yellow":
            directions = ["north", "south", "east", "west"]
            if strategy == "memory_no_comm":
                directions = ["east", "east", "north", "south", "west"]
            return random.choice(directions)

        directions = ["east", "east", "north", "south", "west"]
        if strategy == "random_no_comm":
            directions = ["north", "south", "east", "west", "west"]
        return random.choice(directions)

    def _build_message(self, receiver, performative, content, channel="comm_1"):
        """Build one outgoing message envelope."""
        return {
            "sender": self.agent_name(),
            "receiver": receiver,
            "performative": performative,
            "content": dict(content),
            "channel": channel,
        }

    def team_name(self):
        """Return logical team name used by communication routing."""
        return self.target_waste

    def agent_name(self):
        """Return deterministic agent identifier."""
        return f"{type(self).__name__}_{self.unique_id}"


class GreenRobotBase(BaseRobot):
    """Shared green robot capabilities."""

    target_waste = "green"
    combined_waste = "yellow"
    allowed_message_zones = {"z1"}


class YellowRobotBase(BaseRobot):
    """Shared yellow robot capabilities."""

    target_waste = "yellow"
    combined_waste = "red"
    allowed_message_zones = {"z1", "z2"}


class RedRobotBase(BaseRobot):
    """Shared red robot capabilities."""

    target_waste = "red"
    combined_waste = None
    allowed_message_zones = {"z2", "z3"}
