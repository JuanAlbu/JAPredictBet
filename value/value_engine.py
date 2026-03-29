# src/japredictbet/value/value_engine.py

import math
from typing import Dict, Optional

from scipy.stats import poisson


# =========================
# PROBABILITY FUNCTIONS
# =========================

def poisson_over_prob(lambda_: float, line: float) -> float:
    """
    Calcula P(X > line) usando distribuição de Poisson.
    Ex: line = 5.5 → P(X >= 6)
    """
    k = math.floor(line)
    return 1 - poisson.cdf(k, lambda_)


def poisson_under_prob(lambda_: float, line: float) -> float:
    """
    Calcula P(X < line) usando Poisson.
    Ex: line = 5.5 → P(X <= 5)
    """
    k = math.floor(line)
    return poisson.cdf(k, lambda_)


# =========================
# ODDS UTILITIES
# =========================

def implied_probability(odds: float) -> float:
    """
    Converte odds em probabilidade implícita.
    """
    return 1.0 / odds


def remove_overround(prob_over: float, prob_under: float):
    """
    Remove margem do bookmaker.
    """
    total = prob_over + prob_under
    return prob_over / total, prob_under / total


# =========================
# EDGE & EV
# =========================

def calculate_edge(p_model: float, odds: float) -> float:
    """
    Edge = prob_model - prob_odds
    """
    p_odds = implied_probability(odds)
    return p_model - p_odds


def expected_value(p_model: float, odds: float) -> float:
    """
    EV esperado da aposta
    """
    return (p_model * (odds - 1)) - (1 - p_model)


# =========================
# DECISION
# =========================

def should_bet(edge: float, threshold: float = 0.05) -> bool:
    """
    Decide se aposta baseado no edge mínimo
    """
    return edge > threshold


# =========================
# CORE ENGINE
# =========================

def evaluate_bet(
    lambda_: float,
    line: float,
    odds: float,
    bet_type: str = "over",
    edge_threshold: float = 0.05
) -> Dict:

    if bet_type == "over":
        p_model = poisson_over_prob(lambda_, line)
    else:
        p_model = poisson_under_prob(lambda_, line)

    p_odds = implied_probability(odds)
    edge = p_model - p_odds
    ev = expected_value(p_model, odds)

    return {
        "lambda": lambda_,
        "line": line,
        "odds": odds,
        "bet_type": bet_type,
        "p_model": p_model,
        "p_odds": p_odds,
        "edge": edge,
        "ev": ev,
        "bet": should_bet(edge, edge_threshold)
    }


# =========================
# MULTI-MARKET
# =========================

def evaluate_match(
    lambda_home: float,
    lambda_away: float,
    odds_data: Dict,
    edge_threshold: float = 0.05
):

    results = []

    # HOME
    if "home" in odds_data:
        odds = odds_data["home"]
        results.append(
            evaluate_bet(
                lambda_=lambda_home,
                line=odds["line"],
                odds=odds["odds"],
                bet_type=odds.get("type", "over"),
                edge_threshold=edge_threshold
            )
        )

    # AWAY
    if "away" in odds_data:
        odds = odds_data["away"]
        results.append(
            evaluate_bet(
                lambda_=lambda_away,
                line=odds["line"],
                odds=odds["odds"],
                bet_type=odds.get("type", "over"),
                edge_threshold=edge_threshold
            )
        )

    # TOTAL
    if "total" in odds_data:
        odds = odds_data["total"]
        lambda_total = lambda_home + lambda_away

        results.append(
            evaluate_bet(
                lambda_=lambda_total,
                line=odds["line"],
                odds=odds["odds"],
                bet_type=odds.get("type", "over"),
                edge_threshold=edge_threshold
            )
        )

    return results


# =========================
# BACKTEST HELPERS
# =========================

def evaluate_result(
    real_value: int,
    line: float,
    bet_type: str
) -> Optional[bool]:

    if bet_type == "over":
        if real_value > line:
            return True
        elif real_value == line:
            return None
        else:
            return False
    else:
        if real_value < line:
            return True
        elif real_value == line:
            return None
        else:
            return False


def compute_profit(
    result: Optional[bool],
    odds: float,
    stake: float = 1.0
) -> float:

    if result is None:
        return 0.0

    if result:
        return stake * (odds - 1)

    return -stake


# =========================
# EXAMPLE
# =========================

if __name__ == "__main__":
    odds_data = {
        "home": {"line": 5.5, "odds": 1.95},
        "away": {"line": 4.5, "odds": 1.90},
        "total": {"line": 10.5, "odds": 1.92}
    }

    result = evaluate_match(
        lambda_home=6.2,
        lambda_away=5.1,
        odds_data=odds_data
    )

    for r in result:
        print(r)