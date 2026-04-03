"""
Group: 13
Date: 2026-04-03
Members: Aymane Chalh, Team MAS 13
"""
import random

from mesa import Model
from mesa.datacollection import DataCollector
from mesa.space import MultiGrid

from actions import do_move, do_pick_up, do_put_down, do_transform, next_position
from agents_base import GreenRobotBase, RedRobotBase, YellowRobotBase
from agents_no_comm import GreenRobotNoComm, RedRobotNoComm, YellowRobotNoComm
from agents_with_comm import GreenRobotWithComm, RedRobotWithComm, YellowRobotWithComm
from objects import RadioactivityAgent, WasteAgent, WasteDisposalZoneAgent


class RobotMission(Model):
    """Main MAS model with environment dynamics, orchestration, and communication."""

    VALID_PERFORMATIVES = {"INFORM", "PROPOSE", "ACCEPT"}
    VALID_CHANNELS = {"comm_1", "comm_2"}

    def __init__(
        self,
        width=15,
        height=10,
        initial_green_wastes=10,
        num_green_robots=2,
        num_yellow_robots=2,
        num_red_robots=1,
        message_ttl=10,
        strategy="comm",
        seed=None,
    ):
        super().__init__()
        if seed is not None:
            random.seed(seed)

        self.grid = MultiGrid(width, height, torus=False)
        self.message_ttl = message_ttl
        self.strategy = self._normalize_strategy(strategy)

        self.messages = []
        self._message_id_seq = 0
        self.message_cooldown_steps = 4

        self.disposed_red_waste = 0
        self.current_step = 0
        self.cleanup_time_step = None

        self.messages_sent_total = 0
        self.messages_expired_total = 0
        self.messages_consumed_total = 0

        self.channel_stats = {
            "comm_1": {"sent": 0, "expired": 0, "consumed": 0},
            "comm_2": {"sent": 0, "expired": 0, "consumed": 0},
        }

        z1_bound = width // 3
        z2_bound = 2 * (width // 3)

        for x in range(width):
            for y in range(height):
                if x < z1_bound:
                    zone = "z1"
                elif x < z2_bound:
                    zone = "z2"
                else:
                    zone = "z3"
                self.grid.place_agent(RadioactivityAgent(self, zone), (x, y))

        self.disposal_zone_pos = (width - 1, random.randrange(height))
        self.grid.place_agent(WasteDisposalZoneAgent(self), self.disposal_zone_pos)

        for _ in range(initial_green_wastes):
            x = random.randrange(z1_bound)
            y = random.randrange(height)
            self.grid.place_agent(WasteAgent(self, "green"), (x, y))

        self.robot_classes = self._resolve_robot_classes()
        self._spawn_robots(self.robot_classes[0], num_green_robots, z1_bound, height)
        self._spawn_robots(self.robot_classes[1], num_yellow_robots, z1_bound, height)
        self._spawn_robots(self.robot_classes[2], num_red_robots, z1_bound, height)

        self.running = True

        self.datacollector = DataCollector(
            {
                "Total Waste": lambda m: m._count_waste(),
                "Green Waste": lambda m: m._count_waste("green"),
                "Yellow Waste": lambda m: m._count_waste("yellow"),
                "Red Waste": lambda m: m._count_waste("red"),
                "Waste In Robots": lambda m: m._count_inventory_waste(),
                "Disposed Red Waste": lambda m: m.disposed_red_waste,
                "Messages Sent": lambda m: m.messages_sent_total,
                "Messages Expired": lambda m: m.messages_expired_total,
                "Messages Consumed": lambda m: m.messages_consumed_total,
                "Comm 1 Sent": lambda m: m.channel_stats["comm_1"]["sent"],
                "Comm 2 Sent": lambda m: m.channel_stats["comm_2"]["sent"],
                "Comm 1 Expired": lambda m: m.channel_stats["comm_1"]["expired"],
                "Comm 2 Expired": lambda m: m.channel_stats["comm_2"]["expired"],
                "Comm 1 Consumed": lambda m: m.channel_stats["comm_1"]["consumed"],
                "Comm 2 Consumed": lambda m: m.channel_stats["comm_2"]["consumed"],
                "Active Messages": lambda m: len(m.messages),
                "Cleanup Time (step)": lambda m: m.cleanup_time_step if m.cleanup_time_step is not None else -1,
                "Objective Score": lambda m: m.objective_score(),
            }
        )
        self.datacollector.collect(self)

    def _resolve_robot_classes(self):
        if self.strategy == "comm":
            return (GreenRobotWithComm, YellowRobotWithComm, RedRobotWithComm)
        return (GreenRobotNoComm, YellowRobotNoComm, RedRobotNoComm)

    def _spawn_robots(self, robot_class, count, z1_bound, height):
        """Place robots and initialize their initial percepts."""
        for _ in range(count):
            x = random.randrange(z1_bound)
            y = random.randrange(height)
            robot = robot_class(self)
            self.grid.place_agent(robot, (x, y))
            robot.percepts = self._generate_percepts(robot)

    def step(self):
        """Advance the simulation by one global step."""
        self.current_step += 1

        for robot_class in self.robot_classes:
            if robot_class in self.agents_by_type:
                self.agents_by_type[robot_class].do("step")

        self._age_messages()

        if self.cleanup_time_step is None and self.remaining_waste() == 0:
            self.cleanup_time_step = self.current_step

        self.datacollector.collect(self)

    def do(self, agent, action):
        """Model executor: validate and apply one robot action."""
        if not isinstance(action, dict):
            action = {"type": "wait"}

        consume_id = action.get("consume_message_id")
        if isinstance(consume_id, int):
            self._consume_message(consume_id)
        elif isinstance(consume_id, list):
            for message_id in consume_id:
                if isinstance(message_id, int):
                    self._consume_message(message_id)

        if self.strategy == "comm":
            self._store_outgoing_messages(agent, action.get("messages", []))

        action_type = action.get("type")
        success = False

        if action_type == "move":
            direction = action.get("direction")
            target_pos = next_position(agent.pos, direction)
            if not self.grid.out_of_bounds(target_pos) and self._is_move_legal(agent, target_pos):
                do_move(self.grid, agent, target_pos)
                success = True

        elif action_type == "pick_up":
            color = action.get("color")
            if self._can_pick_up(agent, color):
                success = do_pick_up(self.grid, agent, color)

        elif action_type == "transform":
            from_color = action.get("from")
            to_color = action.get("to")
            if self._can_transform(agent, from_color, to_color):
                success = do_transform(agent.knowledge.get("inventory", []), from_color, to_color)

        elif action_type == "put_down":
            color = action.get("color")
            if self._can_put_down(agent, color):
                inventory = agent.knowledge.get("inventory", [])
                if color in inventory:
                    is_disposal = self._is_disposal_tile(agent.pos)
                    if color == "red" and is_disposal:
                        inventory.remove("red")
                        self.disposed_red_waste += 1
                        success = True
                    else:
                        success = do_put_down(self.grid, agent, color)

        percepts = self._generate_percepts(agent)
        percepts["last_action_success"] = success
        return percepts

    def _store_outgoing_messages(self, agent, outbox):
        """Store structured robot messages emitted during one decision step."""
        if not isinstance(outbox, list):
            return

        sender = agent.agent_name() if hasattr(agent, "agent_name") else f"{type(agent).__name__}_{agent.unique_id}"

        for envelope in outbox:
            if not isinstance(envelope, dict):
                continue
            performative = str(envelope.get("performative", "")).upper()
            receiver = envelope.get("receiver", "broadcast")
            content = envelope.get("content", {})
            channel = envelope.get("channel", "comm_1")
            if not isinstance(content, dict):
                continue
            self._emit_message(
                sender=sender,
                receiver=receiver,
                performative=performative,
                content=content,
                channel=channel,
            )

    def _emit_message(self, sender, receiver, performative, content, channel):
        """Create and store one message with de-duplication and per-channel accounting."""
        if performative not in self.VALID_PERFORMATIVES:
            return
        if channel not in self.VALID_CHANNELS:
            channel = "comm_1"
        if self._should_skip_message(sender, receiver, performative, content, channel):
            return

        self._message_id_seq += 1
        message = {
            "id": self._message_id_seq,
            "sender": sender,
            "receiver": receiver,
            "performative": performative,
            "content": dict(content),
            "timestamp": self.current_step,
            "ttl": self.message_ttl,
            "channel": channel,
            "used": False,
        }
        self.messages.append(message)
        self.messages_sent_total += 1
        self.channel_stats[channel]["sent"] += 1

    def _should_skip_message(self, sender, receiver, performative, content, channel):
        """Suppress duplicate / spammy messages while preserving the protocol semantics."""
        for msg in self.messages:
            if (
                msg.get("sender") == sender
                and msg.get("receiver") == receiver
                and msg.get("performative") == performative
                and msg.get("channel") == channel
                and msg.get("content") == content
                and self.current_step - msg.get("timestamp", -10**9) < self.message_cooldown_steps
            ):
                return True
        return False

    def _age_messages(self):
        """Age active messages and remove expired ones."""
        alive = []
        for message in self.messages:
            message["ttl"] -= 1
            if message["ttl"] > 0:
                alive.append(message)
            else:
                channel = message.get("channel", "comm_1")
                if channel in self.channel_stats:
                    self.channel_stats[channel]["expired"] += 1
                self.messages_expired_total += 1
        self.messages = alive

    def _consume_message(self, message_id):
        """Consume one message id (used by target-selection logic)."""
        for idx, message in enumerate(self.messages):
            if message.get("id") != message_id:
                continue
            channel = message.get("channel", "comm_1")
            if channel in self.channel_stats:
                self.channel_stats[channel]["consumed"] += 1
            self.messages_consumed_total += 1
            self.messages.pop(idx)
            return

    def _is_move_legal(self, agent, target_pos):
        target_x, _ = target_pos
        z1_bound = self.grid.width // 3
        z2_bound = 2 * (self.grid.width // 3)

        if isinstance(agent, GreenRobotBase):
            return target_x < z1_bound
        if isinstance(agent, YellowRobotBase):
            return target_x < z2_bound
        if isinstance(agent, RedRobotBase):
            return True
        return False

    def _can_pick_up(self, agent, color):
        if isinstance(agent, GreenRobotBase):
            return color == "green"
        if isinstance(agent, YellowRobotBase):
            return color == "yellow"
        if isinstance(agent, RedRobotBase):
            return color == "red"
        return False

    def _can_transform(self, agent, from_color, to_color):
        inventory = agent.knowledge.get("inventory", [])
        if isinstance(agent, GreenRobotBase):
            return from_color == "green" and to_color == "yellow" and inventory.count("green") >= 2
        if isinstance(agent, YellowRobotBase):
            return from_color == "yellow" and to_color == "red" and inventory.count("yellow") >= 2
        return False

    def _can_put_down(self, agent, color):
        if isinstance(agent, GreenRobotBase):
            return color == "yellow"
        if isinstance(agent, YellowRobotBase):
            return color == "red"
        if isinstance(agent, RedRobotBase):
            return color == "red"
        return False

    def _is_disposal_tile(self, pos):
        contents = self.grid.get_cell_list_contents([pos])
        return any(getattr(obj, "is_disposal_zone", False) for obj in contents)

    def _count_waste(self, color=None):
        count = 0
        for agent in self.agents:
            if not isinstance(agent, WasteAgent):
                continue
            if color is None or agent.color == color:
                count += 1
        return count

    def _count_inventory_waste(self):
        total = 0
        for agent in self.agents:
            knowledge = getattr(agent, "knowledge", None)
            if isinstance(knowledge, dict):
                total += len(knowledge.get("inventory", []))
        return total

    def remaining_waste(self):
        return self._count_waste() + self._count_inventory_waste()

    def objective_score(self):
        """Scalar objective balancing disposal, cleanup and communication cost."""
        return (
            100 * self.disposed_red_waste
            - 10 * self.remaining_waste()
            - self.current_step
            - 0.2 * self.messages_sent_total
        )

    @staticmethod
    def _normalize_strategy(strategy):
        mapping = {
            "0": "random_no_comm",
            "1": "memory_no_comm",
            "2": "comm",
            "10": "memory_no_comm",
            "20": "comm",
            0: "random_no_comm",
            1: "memory_no_comm",
            2: "comm",
            10: "memory_no_comm",
            20: "comm",
        }
        if strategy in mapping:
            return mapping[strategy]
        if strategy in {"random_no_comm", "memory_no_comm", "comm"}:
            return strategy
        return "comm"

    def _generate_percepts(self, agent):
        percepts = {
            "current_pos": agent.pos,
            "current_tile": [],
            "adjacent_tiles": {},
            "adjacent_by_direction": {},
            "messages": [dict(message) for message in self.messages],
            "disposal_zone_pos": self.disposal_zone_pos,
            "strategy": self.strategy,
            "step": self.current_step,
        }

        if agent.pos is not None:
            current_contents = self.grid.get_cell_list_contents([agent.pos])
            percepts["current_tile"] = current_contents

            neighbors = self.grid.get_neighborhood(agent.pos, moore=False, include_center=False)
            for pos in neighbors:
                contents = self.grid.get_cell_list_contents([pos])
                percepts["adjacent_tiles"][pos] = contents
                direction = self._direction_from_positions(agent.pos, pos)
                if direction:
                    percepts["adjacent_by_direction"][direction] = contents

        return percepts

    @staticmethod
    def _direction_from_positions(origin, target):
        ox, oy = origin
        tx, ty = target
        if tx == ox and ty == oy + 1:
            return "north"
        if tx == ox and ty == oy - 1:
            return "south"
        if tx == ox + 1 and ty == oy:
            return "east"
        if tx == ox - 1 and ty == oy:
            return "west"
        return None
