"""Tests for the core betting engine."""

from __future__ import annotations
import math
import numpy as np
import pytest
from scipy.stats import poisson

from japredictbet.betting import engine


def test_poisson_over_prob():
    """Test P(X > line) calculation."""
    # For rate 10, P(X > 8.5) is P(X >= 9) = 1 - P(X <= 8)
    lambda_ = 10.0
    line = 8.5
    expected = 1 - poisson.cdf(8, lambda_)
    result = engine.poisson_over_prob(lambda_, line)
    assert np.isclose(result, expected)


def test_poisson_under_prob():
    """Test P(X < line) calculation."""
    # For rate 10, P(X < 8.5) is P(X <= 8)
    lambda_ = 10.0
    line = 8.5
    expected = poisson.cdf(8, lambda_)
    result = engine.poisson_under_prob(lambda_, line)
    assert np.isclose(result, expected)


@pytest.mark.parametrize("odds, expected", [(2.0, 0.5), (4.0, 0.25)])
def test_implied_probability(odds: float, expected: float):
    """Test odds to implied probability conversion."""
    assert np.isclose(engine.implied_probability(odds), expected)


def test_implied_probability_error():
    """Test error handling for invalid odds."""
    with pytest.raises(ValueError, match="Odds must be positive"):
        engine.implied_probability(0)


def test_remove_overround():
    """Test overround removal logic."""
    # E.g., Bookmaker probs add up to 1.05
    p_over = 0.55
    p_under = 0.50
    total_prob = p_over + p_under
    norm_over, norm_under = engine.remove_overround(p_over, p_under)
    assert np.isclose(norm_over + norm_under, 1.0)
    assert np.isclose(norm_over, p_over / total_prob)
    assert np.isclose(norm_under, p_under / total_prob)


def test_calculate_edge():
    """Test edge calculation."""
    # Edge = 55% model prob vs 50% odds prob (odds @ 2.0)
    edge = engine.calculate_edge(p_model=0.55, odds=2.0)
    assert np.isclose(edge, 0.05)


def test_expected_value():
    """Test EV calculation."""
    # Bet with 55% chance to win at odds of 2.0
    # EV = (0.55 * (2.0 - 1)) - (1 - 0.55) = 0.55 - 0.45 = 0.10
    ev = engine.expected_value(p_model=0.55, odds=2.0)
    assert np.isclose(ev, 0.10)


def test_should_bet():
    """Test the betting decision logic."""
    assert engine.should_bet(edge=0.06, threshold=0.05)
    assert engine.should_bet(edge=0.05, threshold=0.05)
    assert not engine.should_bet(edge=0.049, threshold=0.05)


def test_evaluate_bet():
    """Test the end-to-end evaluation for a single bet."""
    # Total corners ~ Poisson(11.1), line=10.5, odds=1.92
    result = engine.evaluate_bet(
        lambda_=11.1, line=10.5, odds=1.92, bet_type="over", edge_threshold=0.05
    )
    # p_model = P(X > 10.5) = 1 - P(X<=10) for lambda=11.1
    p_model_expected = 1 - poisson.cdf(10, 11.1)
    p_odds_expected = 1 / 1.92
    edge_expected = p_model_expected - p_odds_expected

    assert isinstance(result, dict)
    assert np.isclose(result["p_model"], p_model_expected)
    assert np.isclose(result["p_odds"], p_odds_expected)
    assert np.isclose(result["edge"], edge_expected)
    assert result["bet"] is (edge_expected >= 0.05)


def test_evaluate_result():
    """Test backtest helper for evaluating bet outcome."""
    # Over bet
    assert engine.evaluate_result(real_value=10, line=8.5, bet_type="over") is True
    assert engine.evaluate_result(real_value=8, line=8.5, bet_type="over") is False
    assert engine.evaluate_result(real_value=9, line=9.0, bet_type="over") is None # Push
    # Under bet
    assert engine.evaluate_result(real_value=7, line=8.5, bet_type="under") is True
    assert engine.evaluate_result(real_value=9, line=8.5, bet_type="under") is False


def test_compute_profit():
    """Test backtest helper for profit calculation."""
    assert np.isclose(engine.compute_profit(result=True, odds=2.5, stake=10), 15.0) # 10 * (2.5-1)
    assert np.isclose(engine.compute_profit(result=False, odds=2.5, stake=10), -10.0)
    assert np.isclose(engine.compute_profit(result=None, odds=2.5, stake=10), 0.0)


def test_consensus_engine_confirms_bet():
    """Consensus should confirm when agreement reaches threshold."""

    consensus = engine.ConsensusEngine(edge_threshold=0.05)
    predictions = [
        {"lambda_home": 7.0, "lambda_away": 4.0},
        {"lambda_home": 6.9, "lambda_away": 4.1},
        {"lambda_home": 7.2, "lambda_away": 3.9},
        {"lambda_home": 7.1, "lambda_away": 3.8},
    ]
    odds_data = {"line": 8.5, "odds": 2.0, "type": "over"}

    result = consensus.evaluate_with_consensus(
        predictions_list=predictions,
        odds_data=odds_data,
        threshold=0.75,
    )

    assert result["votes_positive"] == 4
    assert np.isclose(result["agreement"], 1.0)
    assert result["bet"] is True
    assert result["status_message"] == "Aposta confirmada (Agreement: 100%)"
    assert result["consensus_label"] == "Consenso: 4/4 - 100% | Status: Value Bet"
    assert result["decision_status"] == "Value Bet"
    assert result["model_votes"] == [1, 1, 1, 1]
    assert "ESTATISTICAS DO ENSEMBLE" in result["audit_report"]
    assert "CONCLUSAO: VALUE BET CONFIRMADA" in result["audit_report"]


def test_consensus_engine_discards_without_agreement():
    """Consensus should discard when agreement is below threshold."""

    consensus = engine.ConsensusEngine(edge_threshold=0.05)
    predictions = [
        {"lambda_total": 8.0},
        {"lambda_total": 8.2},
        {"lambda_total": 7.9},
        {"lambda_total": 8.1},
    ]
    odds_data = {"line": 10.5, "odds": 1.9, "type": "over"}

    result = consensus.evaluate_with_consensus(
        predictions_list=predictions,
        odds_data=odds_data,
        threshold=0.70,
    )

    assert result["votes_positive"] == 0
    assert np.isclose(result["agreement"], 0.0)
    assert result["bet"] is False
    assert result["status_message"] == (
        "Aposta descartada por falta de consenso (Agreement: 0%)"
    )
    assert result["consensus_label"] == "Consenso: 0/4 - 0% | Status: Insegura"
    assert result["decision_status"] == "Insegura"
    assert result["model_votes"] == [0, 0, 0, 0]
    assert "CONCLUSAO: ABSTENCAO (INSEGURA)" in result["audit_report"]


def test_report_consensus_generates_formatted_output():
    """Report helper should return standardized audit payload."""

    lambdas = [10.0, 10.3, 9.8, 10.5]
    report = engine.report_consensus(
        lambdas=lambdas,
        odds=2.0,
        line=9.5,
        threshold_edge=0.05,
        consensus_threshold=0.70,
    )

    assert "ESTATISTICAS DO ENSEMBLE (4 MODELOS)" in report["formatted_report"]
    assert "VOTACAO DE VALOR" in report["formatted_report"]
    assert "CONCLUSAO" in report["formatted_report"]
    assert report["votes"] >= 0
