"""Odds collection placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class OddsQuote:
    """Normalized odds representation for a market."""

    match: str
    line: float
    over_odds: float
    under_odds: float


def fetch_odds(provider_name: str) -> pd.DataFrame:
    """Fetch odds from a provider.

    This is a placeholder for future API integration.
    """

    raise NotImplementedError("Odds collection not implemented yet.")