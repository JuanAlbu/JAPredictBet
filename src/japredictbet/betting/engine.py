# src/japredictbet/betting/engine.py

import logging
import math
from typing import Dict, Iterable, Optional

from scipy.stats import poisson

logger = logging.getLogger(__name__)


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
    if odds <= 0:
        raise ValueError("Odds must be positive.")
    return 1.0 / odds


def remove_overround(prob_over: float, prob_under: float):
    """
    Remove margem do bookmaker.
    """
    total = prob_over + prob_under
    if total == 0:
        return 0.0, 0.0
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
    return edge >= threshold


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
            return None # Push
        else:
            return False
    else: # under
        if real_value < line:
            return True
        elif real_value == line:
            return None # Push
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


class ConsensusEngine:
    """Consensus-based evaluator for value betting decisions.

    This engine consumes a list of model predictions for the same match and
    market, computes each model edge independently, and then applies a
    configurable agreement threshold to decide whether to bet.
    """

    def __init__(self, edge_threshold: float = 0.05):
        self.edge_threshold = edge_threshold

    def evaluate_with_consensus(
        self,
        predictions_list: Iterable[Dict],
        odds_data: Dict,
        threshold: float = 0.7,
    ) -> Dict:
        """Evaluate whether a bet is safe using model consensus.

        Args:
            predictions_list:
                Iterable where each item must contain either:
                - ``lambda_home`` and ``lambda_away``; or
                - ``lambda_total``.
            odds_data:
                Market payload with ``line``, ``odds`` and optional ``type``.
            threshold:
                Minimum agreement ratio required to confirm the bet.

        Returns:
            Dict with voting distribution, agreement and final decision.
        """

        model_votes = []
        model_edges = []
        model_probs = []
        normalized_predictions = list(predictions_list)

        if not normalized_predictions:
            raise ValueError("predictions_list must contain at least one prediction.")

        line = float(odds_data["line"])
        odds = float(odds_data["odds"])
        bet_type = str(odds_data.get("type", "over")).lower()

        for prediction in normalized_predictions:
            lambda_total = _extract_lambda_total(prediction)
            if bet_type == "over":
                p_model = poisson_over_prob(lambda_total, line)
            else:
                p_model = poisson_under_prob(lambda_total, line)

            edge = calculate_edge(p_model=p_model, odds=odds)
            vote = 1 if edge >= self.edge_threshold else 0

            model_votes.append(vote)
            model_edges.append(edge)
            model_probs.append(p_model)

        total_models = len(model_votes)
        positive_votes = int(sum(model_votes))
        agreement = positive_votes / total_models if total_models else 0.0
        should_place_bet = agreement >= threshold

        status_message = (
            f"Aposta confirmada (Agreement: {agreement:.0%})"
            if should_place_bet
            else f"Aposta descartada por falta de consenso (Agreement: {agreement:.0%})"
        )
        vote_distribution = f"{positive_votes}/{total_models} modelos concordam"

        logger.info(
            "Consensus decision | %s | threshold=%.0f%% | edge_threshold=%.2f",
            vote_distribution,
            threshold * 100,
            self.edge_threshold,
        )

        return {
            "line": line,
            "odds": odds,
            "bet_type": bet_type,
            "p_model_mean": float(sum(model_probs) / total_models),
            "p_odds": implied_probability(odds),
            "edge_mean": float(sum(model_edges) / total_models),
            "edge_min": float(min(model_edges)),
            "edge_max": float(max(model_edges)),
            "votes_positive": positive_votes,
            "total_models": total_models,
            "agreement": agreement,
            "consensus_threshold": threshold,
            "vote_distribution": vote_distribution,
            "status_message": status_message,
            "bet": should_place_bet,
            "is_value": should_place_bet,
        }


def _extract_lambda_total(prediction: Dict) -> float:
    """Extract total lambda from a prediction payload."""

    if "lambda_total" in prediction:
        return float(prediction["lambda_total"])

    if "lambda_home" in prediction and "lambda_away" in prediction:
        return float(prediction["lambda_home"]) + float(prediction["lambda_away"])

    raise ValueError(
        "Each prediction must contain either 'lambda_total' or "
        "'lambda_home' and 'lambda_away'."
    )
