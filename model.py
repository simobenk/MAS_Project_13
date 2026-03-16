"""
Group: [Insert Group Number]
Date: 2026-03-16
Members: [Name 1], [Name 2], [Name 3]
"""
import random
from mesa import Model
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector

from objects import RadioactivityAgent, WasteAgent, WasteDisposalZoneAgent
from agents import GreenAgent, YellowAgent, RedAgent

class RobotMission(Model):
    """
    The main model that uses the agents and the environment.
    """
    def __init__(self, width=15, height=10, initial_green_wastes=10,
                 num_green_robots=2, num_yellow_robots=2, num_red_robots=1):
        super().__init__()

        # --- 1. SET UP THE GRID ---
        self.grid = MultiGrid(width, height, torus=False)

        z1_bound = width // 3
        z2_bound = 2 * (width // 3)

        # --- 2. LAY DOWN THE FLOOR (RADIOACTIVITY AGENTS) ---
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

        # --- 3. PLACE THE WASTE DISPOSAL ZONE ---
        far_east_x = width - 1
        random_y = random.randrange(height)
        disposal_zone = WasteDisposalZoneAgent(self)
        self.grid.place_agent(disposal_zone, (far_east_x, random_y))

        # --- 4. SPAWN INITIAL GREEN WASTE ---
        for _ in range(initial_green_wastes):
            x = random.randrange(z1_bound)
            y = random.randrange(height)
            waste = WasteAgent(self, "green")
            self.grid.place_agent(waste, (x, y))

        # --- 5. DEPLOY THE ROBOTS ---
        self._spawn_robots(GreenAgent, num_green_robots, z1_bound, height)
        self._spawn_robots(YellowAgent, num_yellow_robots, z1_bound, height)
        self._spawn_robots(RedAgent, num_red_robots, z1_bound, height)

        self.running = True

        self.datacollector = DataCollector(
            {"Total Waste": lambda m: sum(1 for a in m.agents if type(a).__name__ == "WasteAgent")}
        )

    def _spawn_robots(self, RobotClass, count, z1_bound, height):
        """Helper method to place robots on the grid."""
        for _ in range(count):
            x = random.randrange(z1_bound)
            y = random.randrange(height)
            robot = RobotClass(self)
            self.grid.place_agent(robot, (x, y))
            # Mesa 3.x: No schedule.add() — robots are auto-tracked in self.agents

    def step(self):
        """Advances the simulation by one step."""
        # Mesa 3.x: Replace self.schedule.step() with self.agents.do("step")
        # Only step actual robot agents, not static floor/waste objects
        self.agents_by_type[GreenAgent].do("step")
        self.agents_by_type[YellowAgent].do("step")
        self.agents_by_type[RedAgent].do("step")
        self.datacollector.collect(self)

    def do(self, agent, action):
        """
        The referee method. Checks feasibility, executes, and returns percepts.
        """
        action_type = action.get("type")

        # --- EVALUATE: MOVE ---
        if action_type == "move":
            direction = action.get("direction")
            target_pos = self._get_target_pos(agent.pos, direction)

            if not self.grid.out_of_bounds(target_pos):
                if self._is_move_legal(agent, target_pos):
                    self.grid.move_agent(agent, target_pos)

        # --- EVALUATE: PICK UP ---
        elif action_type == "pick_up":
            target_color = action.get("color")
            cell_contents = self.grid.get_cell_list_contents([agent.pos])

            for obj in cell_contents:
                if isinstance(obj, WasteAgent) and obj.color == target_color:
                    self.grid.remove_agent(obj)
                    obj.remove()  # Mesa 3.x: must call agent.remove() to deregister
                    agent.knowledge["inventory"].append(target_color)
                    break

        # --- EVALUATE: TRANSFORM ---
        elif action_type == "transform":
            from_color = action.get("from")
            to_color = action.get("to")
            inventory = agent.knowledge.get("inventory", [])

            if inventory.count(from_color) >= 2:
                inventory.remove(from_color)
                inventory.remove(from_color)
                inventory.append(to_color)

        # --- EVALUATE: PUT DOWN / DISPOSE ---
        elif action_type == "put_down":
            color = action.get("color")
            inventory = agent.knowledge.get("inventory", [])

            if color in inventory:
                cell_contents = self.grid.get_cell_list_contents([agent.pos])
                for obj in cell_contents:
                    if getattr(obj, "is_disposal_zone", False):
                        inventory.remove(color)
                        break

        # --- GENERATE PERCEPTS ---
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

    def _generate_percepts(self, agent):
        percepts = {
            "current_pos": agent.pos,
            "current_tile": [],
            "adjacent_tiles": {}
        }

        if agent.pos is not None:
            current_contents = self.grid.get_cell_list_contents([agent.pos])
            percepts["current_tile"] = current_contents

            neighbors = self.grid.get_neighborhood(agent.pos, moore=False, include_center=False)
            for pos in neighbors:
                contents = self.grid.get_cell_list_contents([pos])
                percepts["adjacent_tiles"][pos] = contents

        return percepts