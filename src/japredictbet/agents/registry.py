"""Agent registry utilities."""

from __future__ import annotations

from .base import BaseAgent


class AgentRegistry:
    """Register and retrieve agent implementations."""

    def __init__(self) -> None:
        self._agents: dict[str, type[BaseAgent]] = {}

    def register(self, agent_cls: type[BaseAgent]) -> None:
        name = agent_cls.name
        if name in self._agents:
            raise ValueError(f"Agent already registered: {name}")
        self._agents[name] = agent_cls

    def get(self, name: str) -> type[BaseAgent]:
        if name not in self._agents:
            raise KeyError(f"Unknown agent: {name}")
        return self._agents[name]
