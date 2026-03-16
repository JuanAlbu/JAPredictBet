"""Agent registry utilities."""

from __future__ import annotations

from typing import Dict, Type

from .base import BaseAgent


class AgentRegistry:
    """Register and retrieve agent implementations."""

    def __init__(self) -> None:
        self._agents: Dict[str, Type[BaseAgent]] = {}

    def register(self, agent_cls: Type[BaseAgent]) -> None:
        name = agent_cls.name
        if name in self._agents:
            raise ValueError(f"Agent already registered: {name}")
        self._agents[name] = agent_cls

    def get(self, name: str) -> Type[BaseAgent]:
        if name not in self._agents:
            raise KeyError(f"Unknown agent: {name}")
        return self._agents[name]