# MAS Project 13 - Robot Mission 2026

Multi-agent simulation (Mesa + Solara) for waste collection and transformation in a 3-zone hostile environment.

## Objective

Maximize red waste disposed in the black disposal tile (z3), while minimizing:

- cleanup time
- remaining waste
- communication cost

Objective score:

`score = 100 * disposed_red_waste - 10 * remaining_waste - current_step - 0.2 * messages_sent`

## Zones and Roles

- `z1` (green): source of green waste
- `z2` (yellow): intermediate processing area
- `z3` (red): most hostile area + final disposal tile

Robot roles:

- `GreenRobot*`: collects `green`, transforms `2 green -> 1 yellow`, drops near `z1 -> z2` border.
- `YellowRobot*`: collects `yellow`, transforms `2 yellow -> 1 red`, drops near `z2 -> z3` border.
- `RedRobot*`: collects `red` and transports it to the black disposal tile.

## Refactored Architecture

- `model.py`: global orchestration, action validation, environment, metrics, datacollector.
- `actions.py`: action primitives (`move`, `pick_up`, `transform`, `put_down`).
- `agents_base.py`: local memory, perception update, navigation helpers, anti-deadlock helpers.
- `agents_no_comm.py`: no-communication logic (random/memory + anti-deadlock).
- `agents_with_comm.py`: communication logic with explicit protocol.
- `experiments.py`: batch experiments and CSV export.
- `analyze_results.py`: automated CSV analysis and plot generation.

### Architecture Diagram:

```mermaid
classDiagram
    class RobotMission {
      +grid: MultiGrid
      +strategy: str
      +messages: list
      +channel_stats: dict
      +step()
      +do(agent, action)
      +_emit_message(sender, receiver, performative, content, channel)
      +_consume_message(message_id)
      +_age_messages()
      +objective_score()
    }

    class Actions {
      +next_position(pos, direction)
      +do_move(grid, agent, target_pos)
      +do_pick_up(grid, agent, color)
      +do_transform(inventory, from_color, to_color)
      +do_put_down(grid, agent, color)
    }

    class BaseRobot {
      +knowledge
      +percepts
      +step()
      +update(knowledge, percepts)
      +deliberate(knowledge)
      +_refresh_known_wastes()
      +_refresh_known_wastes_from_messages()
      +_advance_hold_timer()
      +_decay_recent_drop_cooldowns()
      +_build_message(receiver, performative, content, channel)
    }

    class GreenRobotBase
    class YellowRobotBase
    class RedRobotBase

    class GreenRobotNoComm {
      +deliberate(knowledge)
    }
    class YellowRobotNoComm {
      +deliberate(knowledge)
    }
    class RedRobotNoComm {
      +deliberate(knowledge)
    }

    class GreenRobotWithComm {
      +deliberate(knowledge)
      +INFORM/PROPOSE/ACCEPT
    }
    class YellowRobotWithComm {
      +deliberate(knowledge)
      +INFORM/PROPOSE/ACCEPT
    }
    class RedRobotWithComm {
      +deliberate(knowledge)
      +INFORM/PROPOSE/ACCEPT
    }

    class RadioactivityAgent
    class WasteAgent
    class WasteDisposalZoneAgent

    BaseRobot <|-- GreenRobotBase
    BaseRobot <|-- YellowRobotBase
    BaseRobot <|-- RedRobotBase

    GreenRobotBase <|-- GreenRobotNoComm
    YellowRobotBase <|-- YellowRobotNoComm
    RedRobotBase <|-- RedRobotNoComm

    GreenRobotBase <|-- GreenRobotWithComm
    YellowRobotBase <|-- YellowRobotWithComm
    RedRobotBase <|-- RedRobotWithComm

    RobotMission --> Actions : orchestrates
    RobotMission --> BaseRobot : generates percepts / executes actions
    RobotMission --> RadioactivityAgent : environment
    RobotMission --> WasteAgent : waste entities
    RobotMission --> WasteDisposalZoneAgent : disposal tile
```

## Strategies

- `0` / `random_no_comm`: random moves, no messages.
- `10` / `memory_no_comm`: no messages, but local memory guided movement.
- `20` / `comm`: communication enabled.

## Communication Protocol

Structured message fields:

- `sender`
- `receiver` (`broadcast`, team, or specific agent)
- `performative` (`INFORM`, `PROPOSE`, `ACCEPT`)
- `content`
- `timestamp`
- `ttl`
- `channel` (`comm_1`, `comm_2`)

Channels:

- `comm_1`: environment information (`INFORM`, e.g. waste spotted)
- `comm_2`: coordination (`PROPOSE`, `ACCEPT`)

### Protocol Sequence:

```mermaid
sequenceDiagram
    participant A as Robot A (comm mode)
    participant M as RobotMission (message bus)
    participant B as Robot B (comm mode)

    A->>A: Perceive current + adjacent tiles
    A->>A: update() memory (known_wastes, hold_timer, cooldowns)
    A->>A: deliberate()

    alt Waste spotted locally
      A->>M: messages[]: INFORM {waste_color, position, zone} on comm_1
      M->>M: _emit_message() + de-dup/cooldown checks
      M->>M: store {sender, receiver, performative, content, timestamp, ttl, channel}
    end

    alt Need partner to combine (holds one unit too long)
      A->>M: messages[]: PROPOSE {kind=need_partner, meeting_pos} on comm_2
      M-->>B: percepts include active messages
      B->>B: _handle_incoming_coordination()
      B->>M: messages[]: ACCEPT {meeting_pos} on comm_2
      M-->>A: ACCEPT visible in next percept
      A->>A: collab active, move to meeting point
    end

    A->>M: action {move/pick_up/transform/put_down, consume_message_id?}
    M->>M: do() validates and executes via actions.py
    M->>M: if consume_message_id -> _consume_message() and channel counters++

    loop Each model step
      M->>M: _age_messages(), ttl -= 1
      alt ttl <= 0
        M->>M: remove message, expired counters++ (global + channel)
      end
    end
```

## Anti-Deadlock in No-Comm

Agent memory includes:

- `hold_timer` per waste type
- `held_origin`
- `recent_drop_pos` with cooldown

Rules:

- if a robot holds one waste too long, it drops at origin or border
- immediate re-pick at the same tile is blocked during cooldown

## Installation

```bash
pip install mesa solara matplotlib pandas
```

## Run UI

```bash
python run.py
```

Then open the Solara URL (usually `http://localhost:8765`).

When you change sliders, click `RESET` so the model is rebuilt with the new parameters.

## Batch Experiments

```bash
python experiments.py --runs 20 --steps 500 --output results/strategy_benchmark.csv
```

CSV includes:

- performance (`cleanup_time_step`, `objective_score`, `disposed_red_waste`)
- total communication (`messages_sent`, `messages_expired`, `messages_consumed`)
- per-channel communication (`comm_1_*`, `comm_2_*`)

## Analyze CSV + Plots

```bash
python analyze_results.py --input results/strategy_benchmark.csv --output-dir results/analysis
```

Generated outputs:

- `summary_by_strategy.csv` (mean/std + termination rate)
- `objective_boxplot.png`
- `cleanup_boxplot.png`
- `messages_vs_score.png`
- `channel_breakdown.png`

## Conceptual Choices

- clear perception / decision / action separation
- distributed agents with local view and bounded memory
- explicit comparison of no-comm vs comm strategies
- quantified trade-off between coordination gains and message overhead
