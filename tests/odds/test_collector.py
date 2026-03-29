"""Tests for odds collection utilities."""

from __future__ import annotations
import json
from pathlib import Path

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from japredictbet.odds.collector import fetch_odds


@patch("requests.get")
def test_fetch_odds_from_http(mock_get: MagicMock):
    """Test fetching and normalizing odds from a mocked HTTP API."""
    # 1. Setup Mock
    mock_api_response = {
        "data": [
            {
                "match_name": "Team A vs Team B",
                "market": {"line": 9.5, "prices": {"over": 1.90, "under": 1.90}},
            },
        ]
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_api_response
    mock_get.return_value = mock_response

    # 2. Execution
    df = fetch_odds("http://fake-api.com/odds")

    # 3. Assertions
    mock_get.assert_called_once_with("http://fake-api.com/odds")
    assert isinstance(df, pd.DataFrame)
    assert df.loc[0, "match"] == "Team A vs Team B"


def test_fetch_odds_from_local_file(tmp_path: Path):
    """Test fetching and normalizing odds from a local JSON file."""
    # 1. Setup
    mock_api_response = {
        "data": [
            {
                "match_name": "Team C vs Team D",
                "market": {"line": 10.5, "prices": {"over": 2.10, "under": 1.75}},
            },
        ]
    }
    # Create a temporary file with the mock content
    file_path = tmp_path / "test_odds.json"
    with open(file_path, "w") as f:
        json.dump(mock_api_response, f)

    # 2. Execution
    df = fetch_odds(str(file_path))

    # 3. Assertions
    assert isinstance(df, pd.DataFrame)
    expected_columns = ["match", "line", "over_odds", "under_odds"]
    assert df.columns.tolist() == expected_columns
    assert len(df) == 1
    assert df.loc[0, "match"] == "Team C vs Team D"
    assert df.loc[0, "line"] == 10.5
    assert df.loc[0, "over_odds"] == 2.10
