"""Base agent definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentContext:
    """Context passed to agents during orchestration."""

    payload: dict[str, Any]


class BaseAgent:
    """Base class for action-oriented agents."""

    name: str = "base"

    def run(self, context: AgentContext) -> dict[str, Any]:
        """Execute the agent action."""

        raise NotImplementedError("Agent execution not implemented.")
