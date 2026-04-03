"""
Group: 13
Date: 2026-04-03
Members: Aymane Chalh, Team MAS 13
"""
from agents_base import GreenRobotBase, YellowRobotBase, RedRobotBase


class _WithCommMixin:
    """Communication-enabled decision logic using INFORM/PROPOSE/ACCEPT."""

    def _deliberate_with_comm(self, knowledge):
        percepts = knowledge["time_steps"][-1]["percepts"] if knowledge["time_steps"] else {}
        inventory = knowledge.get("inventory", [])
        current_pos = percepts.get("current_pos")
        outbox = []

        self._handle_incoming_coordination(percepts, outbox)
        self._maybe_emit_inform(percepts, outbox)

        if self.combined_waste is not None and self.combined_waste in inventory:
            self._reset_collaboration()
            if self._at_handoff_border(percepts):
                return self._with_outbox({"type": "put_down", "color": self.combined_waste}, outbox)
            return self._with_outbox({"type": "move", "direction": "east"}, outbox)

        if self.combined_waste is None and "red" in inventory:
            self._reset_collaboration()
            if self._is_disposal_tile(percepts):
                return self._with_outbox({"type": "put_down", "color": "red"}, outbox)
            direction = self._direction_towards(current_pos, percepts.get("disposal_zone_pos"))
            return self._with_outbox({"type": "move", "direction": direction or "east"}, outbox)

        if self.combined_waste is not None and inventory.count(self.target_waste) >= 2:
            self._reset_collaboration()
            return self._with_outbox(
                {"type": "transform", "from": self.target_waste, "to": self.combined_waste},
                outbox,
            )

        collab_action = self._coordination_action(percepts, outbox)
        if collab_action is not None:
            return self._with_outbox(collab_action, outbox)

        hold_steps = knowledge["hold_timer"].get(self.target_waste, 0)
        if self._holds_one_target() and hold_steps >= self.MAX_HOLD_STEPS and self._at_origin_or_border(percepts):
            self._reset_collaboration()
            return self._with_outbox({"type": "put_down", "color": self.target_waste}, outbox)

        if self._can_pick_from_current_tile(percepts, self.target_waste) and len(inventory) < 2:
            return self._with_outbox({"type": "pick_up", "color": self.target_waste}, outbox)

        target = self._choose_target_from_messages(
            percepts,
            self.target_waste,
            allowed_zones=self.allowed_message_zones,
        )
        direction = self._direction_towards(current_pos, target["position"] if target else None)
        if direction:
            action = {"type": "move", "direction": direction}
            if target and target.get("id") is not None:
                action["consume_message_id"] = target["id"]
            return self._with_outbox(action, outbox)

        adjacent_direction = self._direction_to_adjacent_waste(percepts, self.target_waste)
        if adjacent_direction:
            return self._with_outbox({"type": "move", "direction": adjacent_direction}, outbox)

        target_pos = self._nearest_known_waste(
            self.target_waste,
            current_pos,
            allowed_zones=self.allowed_message_zones,
        )
        fallback_direction = self._direction_towards(current_pos, target_pos)
        if fallback_direction:
            return self._with_outbox({"type": "move", "direction": fallback_direction}, outbox)

        return self._with_outbox({"type": "move", "direction": self._default_random_direction("memory_no_comm")}, outbox)

    def _coordination_action(self, percepts, outbox):
        if self.combined_waste is None:
            return None

        collab = self.knowledge["collab"]
        current_pos = percepts.get("current_pos")

        hold_steps = self.knowledge["hold_timer"].get(self.target_waste, 0)
        if (
            not collab["active"]
            and not collab["waiting_accept"]
            and self._holds_one_target()
            and hold_steps >= 10
        ):
            if self.knowledge["step_index"] >= self.knowledge.get("next_partner_broadcast_step", 0):
                outbox.append(
                    self._build_message(
                        receiver=self.team_name(),
                        performative="PROPOSE",
                        channel="comm_2",
                        content={
                            "kind": "need_partner",
                            "waste_color": self.target_waste,
                            "meeting_pos": current_pos,
                        },
                    )
                )
                collab["waiting_accept"] = True
                collab["timeout"] = self.COLLAB_TIMEOUT
                collab["meeting_pos"] = current_pos
                self.knowledge["next_partner_broadcast_step"] = self.knowledge["step_index"] + 20

        if not collab["active"]:
            return None

        meeting_pos = collab.get("meeting_pos")
        if meeting_pos is None:
            return None

        direction = self._direction_towards(current_pos, meeting_pos)
        if direction:
            return {"type": "move", "direction": direction}

        if collab.get("role") == "responder" and self._holds_one_target():
            self._reset_collaboration()
            return {"type": "put_down", "color": self.target_waste}

        if collab.get("role") == "initiator" and self._can_pick_from_current_tile(percepts, self.target_waste):
            return {"type": "pick_up", "color": self.target_waste}

        return None

    def _handle_incoming_coordination(self, percepts, outbox):
        if self.combined_waste is None:
            return

        collab = self.knowledge["collab"]

        for msg in self._messages_for_me(percepts):
            performative = msg.get("performative")
            sender = msg.get("sender")
            content = msg.get("content", {})
            if content.get("waste_color") not in {None, self.target_waste}:
                continue

            if performative == "PROPOSE" and content.get("kind") == "need_partner":
                if sender == self.agent_name():
                    continue
                if self._holds_one_target() and not collab["active"] and not collab["waiting_accept"]:
                    meeting_pos = tuple(content.get("meeting_pos", percepts.get("current_pos")))
                    outbox.append(
                        self._build_message(
                            receiver=sender,
                            performative="ACCEPT",
                            channel="comm_2",
                            content={
                                "kind": "accept_partner",
                                "waste_color": self.target_waste,
                                "meeting_pos": meeting_pos,
                            },
                        )
                    )
                    collab.update(
                        {
                            "active": True,
                            "waiting_accept": False,
                            "role": "responder",
                            "partner": sender,
                            "meeting_pos": meeting_pos,
                            "timeout": self.COLLAB_TIMEOUT,
                        }
                    )

            elif performative == "ACCEPT" and collab["waiting_accept"]:
                if msg.get("receiver") != self.agent_name():
                    continue
                meeting_pos = content.get("meeting_pos", collab.get("meeting_pos"))
                if isinstance(meeting_pos, (list, tuple)) and len(meeting_pos) == 2:
                    collab.update(
                        {
                            "active": True,
                            "waiting_accept": False,
                            "role": "initiator",
                            "partner": sender,
                            "meeting_pos": tuple(meeting_pos),
                            "timeout": self.COLLAB_TIMEOUT,
                        }
                    )

    def _maybe_emit_inform(self, percepts, outbox):
        if self.knowledge["step_index"] % self.INFORM_PERIOD != 0:
            return

        info = self._message_from_local_percepts(percepts, self.target_waste)
        if not info:
            return

        outbox.append(
            self._build_message(
                receiver="broadcast",
                performative="INFORM",
                channel="comm_1",
                content={
                    "kind": "waste_spotted",
                    "waste_color": info["waste_color"],
                    "position": info["position"],
                    "zone": info["zone"],
                },
            )
        )

    @staticmethod
    def _with_outbox(action, outbox):
        if outbox:
            action["messages"] = outbox
        return action


class GreenRobotWithComm(_WithCommMixin, GreenRobotBase):
    """Green robot with explicit communication protocol."""

    def deliberate(self, knowledge):
        return self._deliberate_with_comm(knowledge)


class YellowRobotWithComm(_WithCommMixin, YellowRobotBase):
    """Yellow robot with explicit communication protocol."""

    def deliberate(self, knowledge):
        return self._deliberate_with_comm(knowledge)


class RedRobotWithComm(_WithCommMixin, RedRobotBase):
    """Red robot with explicit communication protocol."""

    def deliberate(self, knowledge):
        return self._deliberate_with_comm(knowledge)
