"""Odds collection utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests


@dataclass(frozen=True)
class OddsQuote:
    """Normalized odds representation for a market."""

    match: str
    line: float
    over_odds: float
    under_odds: float


def _parse_api_data(api_data: dict) -> pd.DataFrame:
    """Parse dictionary data from JSON into a DataFrame."""
    try:
        odds_data = []
        for item in api_data["data"]:
            odds_data.append(
                {
                    "match": item["match_name"],
                    "line": item["market"]["line"],
                    "over_odds": item["market"]["prices"]["over"],
                    "under_odds": item["market"]["prices"]["under"],
                }
            )
        return pd.DataFrame(odds_data)
    except (KeyError, TypeError) as e:
        raise ValueError("API response format is not as expected.") from e


def fetch_odds(provider_url: str) -> pd.DataFrame:
    """Fetch odds from a provider API or a local file.

    Args:
        provider_url: The URL of the odds provider API or path to a local JSON file.

    Returns:
        A DataFrame with normalized odds data.

    Raises:
        requests.exceptions.RequestException: For network errors.
        ValueError: If the API response or file format is not as expected.
        FileNotFoundError: If the local file path does not exist.
    """
    if provider_url.lower().startswith("http"):
        response = requests.get(provider_url)
        response.raise_for_status()  # Raise an exception for bad status codes
        api_data = response.json()
    else:
        filepath = Path(provider_url)
        with open(filepath, "r") as f:
            api_data = json.load(f)

    return _parse_api_data(api_data)