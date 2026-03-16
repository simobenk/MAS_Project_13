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
        
        # --- 1. SET UP THE GRID AND SCHEDULER ---
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
                
                rad_agent = RadioactivityAgent(self.next_id(), self, zone)
                self.grid.place_agent(rad_agent, (x, y))

        # --- 3. PLACE THE WASTE DISPOSAL ZONE ---
        # "located as far to the east as possible... chosen randomly among the eastern cells" 
        far_east_x = width - 1
        random_y = random.randrange(height)
        disposal_zone = WasteDisposalZoneAgent(self.next_id(), self)
        self.grid.place_agent(disposal_zone, (far_east_x, random_y))

        # --- 4. SPAWN INITIAL GREEN WASTE ---
        # "Z1 area... containing a random number of initial (green) waste" 
        for _ in range(initial_green_wastes):
            # Pick a random cell strictly inside z1 bounds
            x = random.randrange(z1_bound)
            y = random.randrange(height)
            waste = WasteAgent(self.next_id(), self, "green")
            self.grid.place_agent(waste, (x, y))

        # --- 5. DEPLOY THE ROBOTS ---
        # We'll spawn all robots in Z1 to start, so they are near the initial waste.
        self._spawn_robots(GreenAgent, num_green_robots, z1_bound, height)
        self._spawn_robots(YellowAgent, num_yellow_robots, z1_bound, height)
        self._spawn_robots(RedAgent, num_red_robots, z1_bound, height)
        
        self.running = True 

        self.datacollector = DataCollector(
            {"Total Waste": lambda m: sum(1 for agent in m.schedule.agents if type(agent).__name__ == "WasteAgent")}
        )

    def _spawn_robots(self, RobotClass, count, z1_bound, height):
        """Helper method to place robots on the grid and add them to the scheduler."""
        for _ in range(count):
            x = random.randrange(z1_bound)
            y = random.randrange(height)
            robot = RobotClass(self.next_id(), self)
            self.grid.place_agent(robot, (x, y))
            self.schedule.add(robot)

    def step(self):
        """Advances the simulation by one step."""
        self.schedule.step()
        self.datacollector.collect(self)

    def do(self, agent, action):
        """
        The referee method. Checks feasibility, executes, and returns percepts.
        """
        action_type = action.get("type")

        # --- EVALUATE: MOVE ---
        if action_type == "move":
            direction = action.get("direction")
            target_pos = self._get_target_pos(agent.pos, direction) # Helper to get new (x,y)

            # 1. Check if the target is still on the board
            if not self.grid.out_of_bounds(target_pos):
                
                # 2. Referee Check: Is the robot allowed in this zone?
                if self._is_move_legal(agent, target_pos):
                    # The action is feasible! Move the agent.
                    self.grid.move_agent(agent, target_pos)
        
        # --- EVALUATE: PICK UP ---
        elif action_type == "pick_up":
            target_color = action.get("color")
            cell_contents = self.grid.get_cell_list_contents([agent.pos])
            
            # Check if the specific waste actually exists on this tile
            for obj in cell_contents:
                if isinstance(obj, WasteAgent) and obj.color == target_color:
                    # Feasible! Remove from the grid and add to the robot's inventory
                    self.grid.remove_agent(obj)
                    agent.knowledge["inventory"].append(target_color)
                    break  # Only pick up one per turn
        
        # --- EVALUATE: TRANSFORM ---
        elif action_type == "transform":
            from_color = action.get("from")
            to_color = action.get("to")
            inventory = agent.knowledge.get("inventory", [])
            
            # Check if the agent actually has 2 of the required raw materials
            if inventory.count(from_color) >= 2:
                # Remove 2 raw materials
                inventory.remove(from_color)
                inventory.remove(from_color)
                # Add 1 completely transformed product
                inventory.append(to_color)

        # --- EVALUATE: PUT DOWN / DISPOSE ---
        elif action_type == "put_down":
            color = action.get("color")
            inventory = agent.knowledge.get("inventory", [])
            
            # Check if the agent has the red waste and is standing on the disposal zone
            if color in inventory:
                cell_contents = self.grid.get_cell_list_contents([agent.pos])
                for obj in cell_contents:
                    if getattr(obj, "is_disposal_zone", False):
                        # Feasible! The waste is "put away" 
                        inventory.remove(color)
                        break

        # --- GENERATE PERCEPTS ---
        # Return a dictionary containing information about adjacent tiles and their content.
        return self._generate_percepts(agent)
    
    def _get_target_pos(self, current_pos, direction):
        """Helper to calculate the new (x, y) coordinate based on direction."""
        x, y = current_pos
        if direction == "north": return (x, y + 1)
        if direction == "south": return (x, y - 1)
        if direction == "east":  return (x + 1, y)
        if direction == "west":  return (x - 1, y)
        return current_pos

    def _is_move_legal(self, agent, target_pos):
        """Checks if a specific robot type is allowed to enter the target column (x)."""
        target_x, target_y = target_pos
        z1_bound = self.grid.width // 3
        z2_bound = 2 * (self.grid.width // 3)

        # Check Green Robot limits
        if isinstance(agent, GreenAgent):
            return target_x < z1_bound  # True if inside z1, False if it tries to leave
            
        # Check Yellow Robot limits
        elif isinstance(agent, YellowAgent):
            return target_x < z2_bound  # True if inside z1 or z2
            
        # Red Robots can go anywhere
        elif isinstance(agent, RedAgent):
            return True 
            
        return False

    def _generate_percepts(self, agent):
        """
        Acts as the robot's sensors. 
        Gathers data about the current tile and adjacent tiles.
        """
        percepts = {
            "current_pos": agent.pos,
            "current_tile": [],
            "adjacent_tiles": {}
        }

        # Safety check to ensure the agent is actually on the board
        if agent.pos is not None:
            
            # 1. Read the current tile (Mesa gives us a list of all objects here)
            current_contents = self.grid.get_cell_list_contents([agent.pos])
            percepts["current_tile"] = current_contents

            # 2. Find the coordinates for North, South, East, West
            # moore=False means no diagonals. include_center=False excludes the tile we are standing on.
            neighbors = self.grid.get_neighborhood(agent.pos, moore=False, include_center=False)
            
            # 3. Read the contents of each adjacent tile
            for pos in neighbors:
                contents = self.grid.get_cell_list_contents([pos])
                percepts["adjacent_tiles"][pos] = contents

        return percepts