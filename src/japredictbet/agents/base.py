"""Base agent definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AgentContext:
    """Context passed to agents during orchestration."""

    payload: Dict[str, Any]


class BaseAgent:
    """Base class for action-oriented agents."""

    name: str = "base"

    def run(self, context: AgentContext) -> Dict[str, Any]:
        """Execute the agent action."""

        raise NotImplementedError("Agent execution not implemented.")