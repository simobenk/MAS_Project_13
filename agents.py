"""Compatibility exports for robot agent classes."""

from agents_base import BaseRobot, GreenRobotBase, YellowRobotBase, RedRobotBase
from agents_no_comm import GreenRobotNoComm, YellowRobotNoComm, RedRobotNoComm
from agents_with_comm import GreenRobotWithComm, YellowRobotWithComm, RedRobotWithComm

# Backward-compatible aliases.
GreenAgent = GreenRobotWithComm
YellowAgent = YellowRobotWithComm
RedAgent = RedRobotWithComm

__all__ = [
    "BaseRobot",
    "GreenRobotBase",
    "YellowRobotBase",
    "RedRobotBase",
    "GreenRobotNoComm",
    "YellowRobotNoComm",
    "RedRobotNoComm",
    "GreenRobotWithComm",
    "YellowRobotWithComm",
    "RedRobotWithComm",
    "GreenAgent",
    "YellowAgent",
    "RedAgent",
]
