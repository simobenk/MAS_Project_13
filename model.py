"""
Group: 13
Date: 2026-03-23
Members: Aymane Chalh, Team MAS 13
"""
import random
from mesa import Model
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector

from objects import RadioactivityAgent, WasteAgent, WasteDisposalZoneAgent
from agents import GreenAgent, YellowAgent, RedAgent

class RobotMission(Model):
    """Main MAS model with environment, action execution, and communication."""

    def __init__(self, width=15, height=10, initial_green_wastes=10,
                 num_green_robots=2, num_yellow_robots=2, num_red_robots=1,
                 message_ttl=10, strategy="comm", seed=None):
        super().__init__()
        if seed is not None:
            random.seed(seed)

        self.grid = MultiGrid(width, height, torus=False)
        self.message_ttl = message_ttl
        self.strategy = self._normalize_strategy(strategy)
        self.messages = []
        self._message_id_seq = 0
        self.disposed_red_waste = 0
        self.messages_sent_total = 0
        self.messages_expired_total = 0
        self.messages_consumed_total = 0
        self.current_step = 0
        self.cleanup_time_step = None
        self.message_cooldown_steps = 4

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

                # Mesa 3.x: No unique_id argument — it is assigned automatically
                rad_agent = RadioactivityAgent(self, zone)
                self.grid.place_agent(rad_agent, (x, y))

        far_east_x = width - 1
        random_y = random.randrange(height)
        disposal_zone = WasteDisposalZoneAgent(self)
        self.disposal_zone_pos = (far_east_x, random_y)
        self.grid.place_agent(disposal_zone, self.disposal_zone_pos)

        for _ in range(initial_green_wastes):
            x = random.randrange(z1_bound)
            y = random.randrange(height)
            waste = WasteAgent(self, "green")
            self.grid.place_agent(waste, (x, y))

        self._spawn_robots(GreenAgent, num_green_robots, z1_bound, height)
        self._spawn_robots(YellowAgent, num_yellow_robots, z1_bound, height)
        self._spawn_robots(RedAgent, num_red_robots, z1_bound, height)

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
                "Active Messages": lambda m: len(m.messages),
                "Cleanup Time (step)": lambda m: m.cleanup_time_step if m.cleanup_time_step is not None else -1,
                "Objective Score": lambda m: m.objective_score(),
            }
        )
        self.datacollector.collect(self)

    def _spawn_robots(self, RobotClass, count, z1_bound, height):
        """Helper method to place robots on the grid and initialize their first percepts."""
        for _ in range(count):
            x = random.randrange(z1_bound)
            y = random.randrange(height)
            robot = RobotClass(self)
            self.grid.place_agent(robot, (x, y))
            robot.percepts = self._generate_percepts(robot)

    def step(self):
        """Advances the simulation by one step."""
        self.current_step += 1

        if GreenAgent in self.agents_by_type:
            self.agents_by_type[GreenAgent].do("step")
        if YellowAgent in self.agents_by_type:
            self.agents_by_type[YellowAgent].do("step")
        if RedAgent in self.agents_by_type:
            self.agents_by_type[RedAgent].do("step")

        self._age_messages()
        if self.cleanup_time_step is None and self.remaining_waste() == 0:
            self.cleanup_time_step = self.current_step
        self.datacollector.collect(self)

    def do(self, agent, action):
        """Model executor: validates actions, applies effects, returns percepts."""
        if not isinstance(action, dict):
            action = {"type": "wait"}

        consumed_message_id = action.get("consume_message_id")
        if isinstance(consumed_message_id, int):
            self._consume_message(consumed_message_id)

        broadcast = action.get("broadcast")
        if self.strategy == "comm" and isinstance(broadcast, dict):
            self._store_broadcast(agent, broadcast)

        action_type = action.get("type")

        if action_type == "move":
            direction = action.get("direction")
            target_pos = self._get_target_pos(agent.pos, direction)

            if not self.grid.out_of_bounds(target_pos):
                if self._is_move_legal(agent, target_pos):
                    self.grid.move_agent(agent, target_pos)

        elif action_type == "pick_up":
            target_color = action.get("color")
            if self._can_pick_up(agent, target_color):
                cell_contents = self.grid.get_cell_list_contents([agent.pos])

                for obj in cell_contents:
                    if isinstance(obj, WasteAgent) and obj.color == target_color:
                        self.grid.remove_agent(obj)
                        obj.remove()
                        agent.knowledge["inventory"].append(target_color)
                        break

        elif action_type == "transform":
            from_color = action.get("from")
            to_color = action.get("to")
            if self._can_transform(agent, from_color, to_color):
                inventory = agent.knowledge.get("inventory", [])
                inventory.remove(from_color)
                inventory.remove(from_color)
                inventory.append(to_color)

        elif action_type == "put_down":
            color = action.get("color")
            inventory = agent.knowledge.get("inventory", [])
            if color in inventory and self._can_put_down(agent, color):
                cell_contents = self.grid.get_cell_list_contents([agent.pos])
                is_disposal_zone = any(
                    getattr(obj, "is_disposal_zone", False) for obj in cell_contents
                )
                inventory.remove(color)
                if color == "red" and is_disposal_zone:
                    self.disposed_red_waste += 1
                else:
                    self.grid.place_agent(WasteAgent(self, color), agent.pos)
                    if color == "red" and self.strategy == "comm":
                        self._emit_message(
                            sender=f"{type(agent).__name__}-{agent.unique_id}",
                            performative="inform",
                            content={
                                "waste_color": "red",
                                "position": agent.pos,
                                "zone": self._zone_from_contents(cell_contents),
                                "kind": "dropped_waste",
                            },
                        )

        return self._generate_percepts(agent)

    def _get_target_pos(self, current_pos, direction):
        x, y = current_pos
        if direction == "north": return (x, y + 1)
        if direction == "south": return (x, y - 1)
        if direction == "east":  return (x + 1, y)
        if direction == "west":  return (x - 1, y)
        return current_pos

    def _is_move_legal(self, agent, target_pos):
        target_x, _ = target_pos
        z1_bound = self.grid.width // 3
        z2_bound = 2 * (self.grid.width // 3)

        if isinstance(agent, GreenAgent):
            return target_x < z1_bound
        elif isinstance(agent, YellowAgent):
            return target_x < z2_bound
        elif isinstance(agent, RedAgent):
            return True
        return False

    def _can_pick_up(self, agent, color):
        if isinstance(agent, GreenAgent):
            return color == "green"
        if isinstance(agent, YellowAgent):
            return color == "yellow"
        if isinstance(agent, RedAgent):
            return color == "red"
        return False

    def _can_transform(self, agent, from_color, to_color):
        inventory = agent.knowledge.get("inventory", [])
        if isinstance(agent, GreenAgent):
            return from_color == "green" and to_color == "yellow" and inventory.count("green") >= 2
        if isinstance(agent, YellowAgent):
            return from_color == "yellow" and to_color == "red" and inventory.count("yellow") >= 2
        return False

    def _can_put_down(self, agent, color):
        if isinstance(agent, GreenAgent):
            return color == "yellow"
        if isinstance(agent, YellowAgent):
            return color == "red"
        if isinstance(agent, RedAgent):
            return color == "red"
        return False

    def _store_broadcast(self, agent, payload):
        position = payload.get("position")
        waste_color = payload.get("waste_color")
        if not (isinstance(position, (list, tuple)) and len(position) == 2):
            return
        if waste_color not in {"green", "yellow", "red"}:
            return

        self._emit_message(
            sender=f"{type(agent).__name__}-{agent.unique_id}",
            performative="inform",
            content={
                "waste_color": waste_color,
                "position": (position[0], position[1]),
                "zone": payload.get("zone"),
                "kind": "waste_spotted",
            },
        )

    def _age_messages(self):
        alive = []
        for message in self.messages:
            message["ttl"] -= 1
            if message["ttl"] > 0:
                alive.append(message)
            else:
                self.messages_expired_total += 1
        self.messages = alive

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
        for robot_type in (GreenAgent, YellowAgent, RedAgent):
            if robot_type not in self.agents_by_type:
                continue
            for robot in self.agents_by_type[robot_type]:
                total += len(robot.knowledge.get("inventory", []))
        return total

    def remaining_waste(self):
        return self._count_waste() + self._count_inventory_waste()

    def objective_score(self):
        # Higher is better: dispose more while minimizing time and communication overhead.
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

    def _emit_message(self, sender, performative, content):
        if self._should_skip_message(sender, performative, content):
            return

        self._message_id_seq += 1
        message = {
            "id": self._message_id_seq,
            "performative": performative,
            "sender": sender,
            "receivers": "broadcast",
            "content": dict(content),
            # Compatibility fields consumed by existing behaviors:
            "waste_color": content.get("waste_color"),
            "position": content.get("position"),
            "zone": content.get("zone"),
            "timestamp": self.current_step,
            "ttl": self.message_ttl,
            "used": False,
        }
        self.messages.append(message)
        self.messages_sent_total += 1

    def _should_skip_message(self, sender, performative, content):
        waste_color = content.get("waste_color")
        position = content.get("position")
        kind = content.get("kind")

        for message in self.messages:
            existing_content = message.get("content", {})
            # 1) Global de-duplication: avoid flooding identical active messages.
            if (
                message.get("performative") == performative
                and existing_content.get("kind") == kind
                and existing_content.get("waste_color") == waste_color
                and existing_content.get("position") == position
            ):
                return True

            # 2) Sender-level cooldown: avoid repeated broadcasts every step.
            if (
                message.get("sender") == sender
                and existing_content.get("kind") == kind
                and existing_content.get("waste_color") == waste_color
                and existing_content.get("position") == position
                and self.current_step - message.get("timestamp", -10**9) < self.message_cooldown_steps
            ):
                return True
        return False

    def _consume_message(self, message_id):
        for message in self.messages:
            if message.get("id") == message_id and not message.get("used", False):
                message["used"] = True
                self.messages_consumed_total += 1
                break

    @staticmethod
    def _zone_from_contents(contents):
        for obj in contents:
            radioactivity = getattr(obj, "radioactivity", None)
            if radioactivity is None:
                continue
            if radioactivity < 0.33:
                return "z1"
            if radioactivity < 0.66:
                return "z2"
            return "z3"
        return None

    def _generate_percepts(self, agent):
        percepts = {
            "current_pos": agent.pos,
            "current_tile": [],
            "adjacent_tiles": {},
            "adjacent_by_direction": {},
            "messages": [dict(message) for message in self.messages],
            "disposal_zone_pos": self.disposal_zone_pos,
            "strategy": self.strategy,
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
