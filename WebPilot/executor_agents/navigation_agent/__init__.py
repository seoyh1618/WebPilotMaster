# WebPilot/executor_agents/navigation_agent/__init__.py

from .agent import Navigation_Agent, NavigationAgentClass
from .state import (
    NavigationInput,
    NavigationOutput,
    NavigationAction,
    NavigationResult
)

__all__ = [
    "Navigation_Agent",
    "NavigationAgentClass",
    "NavigationInput",
    "NavigationOutput",
    "NavigationAction",
    "NavigationResult"
]