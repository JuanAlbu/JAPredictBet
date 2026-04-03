# src/japredictbet/betting/engine.py

import logging
import math
from typing import Dict, Iterable, Optional, Sequence

import numpy as np
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
# LAMBDA VALIDATION
# =========================

def _validate_lambda(lambda_: float, context: str = "") -> None:
    """Validate that lambda is a valid Poisson parameter.
    
    Poisson distribution requires lambda >= 0 and finite.
    Raises ValueError with context if validation fails. Logs warning if lambda is 0.
    
    Args:
        lambda_: Predicted lambda value
        context: Context string for error messages (e.g., 'Model 5')
    
    Raises:
        ValueError: If lambda is NaN, infinite, or negative
    """
    if not np.isfinite(lambda_):
        msg = f"Lambda is not finite: {lambda_}"
        if context:
            msg = f"[{context}] {msg}"
        logger.error(msg)
        raise ValueError(msg)
    
    if lambda_ < 0:
        msg = f"Lambda must be non-negative, got {lambda_}"
        if context:
            msg = f"[{context}] {msg}"
        logger.error(msg)
        raise ValueError(msg)
    
    if lambda_ == 0:
        msg = f"Lambda is 0 (no corners expected)"
        if context:
            msg = f"[{context}] {msg}"
        logger.warning(msg)


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
# CLV (P1.D2)
# =========================


def closing_line_value(entry_odds: float, closing_odds: float) -> float:
    """Compute Closing Line Value.

    CLV = implied_prob(closing) - implied_prob(entry).
    Positive CLV means the bettor captured better odds than the closing line.

    Args:
        entry_odds: Decimal odds at the time of bet placement.
        closing_odds: Decimal odds at market close.

    Returns:
        CLV as a probability difference (positive = beat the close).
    """
    return implied_probability(closing_odds) - implied_probability(entry_odds)


def clv_hit_rate(clv_values: Sequence[float]) -> float:
    """Compute the fraction of bets that beat the closing line (CLV >= 0).

    Args:
        clv_values: Sequence of CLV values from placed bets.

    Returns:
        Hit rate in [0, 1]. Returns 0.0 for empty input.
    """
    if not clv_values:
        return 0.0
    positives = sum(1 for v in clv_values if v >= 0)
    return positives / len(clv_values)


def clv_summary(clv_values: Sequence[float]) -> Dict:
    """Compute CLV audit summary statistics.

    Args:
        clv_values: Sequence of CLV values from placed bets.

    Returns:
        Dict with mean_clv, median_clv, hit_rate, n_bets.
    """
    if not clv_values:
        return {
            "mean_clv": 0.0,
            "median_clv": 0.0,
            "hit_rate": 0.0,
            "n_bets": 0,
        }
    arr = np.array(clv_values, dtype=float)
    return {
        "mean_clv": float(arr.mean()),
        "median_clv": float(np.median(arr)),
        "hit_rate": clv_hit_rate(clv_values),
        "n_bets": len(clv_values),
    }


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


def report_consensus(
    lambdas: list[float],
    odds: float,
    line: float,
    threshold_edge: float,
    consensus_threshold: float,
) -> Dict:
    """Gera o output resumido da Analise de Concordancia.
    
    Validates all lambdas before computing statistics.
    
    Args:
        lambdas: List of predicted lambda values from ensemble models
        odds: Betting odds
        line: Betting line
        threshold_edge: Edge threshold for voting
        consensus_threshold: Agreement threshold for decision
    
    Returns:
        Dict with consensus statistics and decision
    
    Raises:
        ValueError: If lambdas list empty, odds invalid, or any lambda invalid
    """

    if not lambdas:
        raise ValueError("lambdas must contain at least one value.")
    if odds <= 0:
        raise ValueError("odds must be positive.")

    # Validate all lambdas before processing
    for i, lambda_ in enumerate(lambdas):
        try:
            _validate_lambda(lambda_, context=f"Model {i+1}/{len(lambdas)}")
        except ValueError as e:
            logger.error(f"Invalid lambda in ensemble: {e}")
            raise

    # 1. Estatisticas Basicas
    mean_lambda = float(np.mean(lambdas))
    std_lambda = float(np.std(lambdas))

    # 2. Votacao de Valor (Poisson + Edge)
    probs = [1 - poisson.cdf(line, lb) for lb in lambdas]
    p_odds = 1 / odds
    votes = int(sum(1 for p in probs if (p - p_odds) >= threshold_edge))
    agreement = votes / len(lambdas)

    # 3. Distribuicao por Ranges (Frequencia)
    ranges = {
        f"< {line}": int(sum(1 for lb in lambdas if lb < line)),
        f"{line} - {line + 1}": int(sum(1 for lb in lambdas if line <= lb < line + 1)),
        f"> {line + 1}": int(sum(1 for lb in lambdas if lb >= line + 1)),
    }

    # 4. Decisao
    status = (
        "VALUE BET CONFIRMADA"
        if agreement >= consensus_threshold
        else "ABSTENCAO (INSEGURA)"
    )

    lines = [
        "-" * 40,
        f"ESTATISTICAS DO ENSEMBLE ({len(lambdas)} MODELOS)",
        f"Media lambda: {mean_lambda:.2f} | Desvio Padrao (sigma): {std_lambda:.2f}",
        "",
        "DISTRIBUICAO POR RANGE (lambda):",
    ]
    for label, count in ranges.items():
        lines.append(f"  {label}: {count} modelos")

    lines.extend(
        [
            "",
            f"VOTACAO DE VALOR (Edge >= {threshold_edge}):",
            f"  Votos: {votes} / {len(lambdas)} ({agreement:.1%})",
            f"  Threshold Requerido: {consensus_threshold:.1%}",
            f"",
            f"CONCLUSAO: {status}",
            "-" * 40,
        ]
    )
    formatted_report = "\n".join(lines)

    return {
        "mean_lambda": mean_lambda,
        "std_lambda": std_lambda,
        "votes": votes,
        "agreement": agreement,
        "ranges": ranges,
        "status": status,
        "formatted_report": formatted_report,
    }


class ConsensusEngine:
    """Consensus-based evaluator for value betting decisions.

    This engine consumes a list of model predictions for the same match and
    market, computes each model edge independently, and then applies a
    configurable agreement threshold to decide whether to bet.
    
    Supports dynamic margin-based threshold adjustment: when the absolute
    difference between mean lambda and betting line is tight (< 0.5),
    consensus threshold increases to 50% for additional safety.
    """

    def __init__(
        self,
        edge_threshold: float = 0.05,
        use_dynamic_margin: bool = True,
        tight_margin_threshold: float = 0.5,
        tight_margin_consensus: float = 0.50,
    ):
        """Initialize consensus engine.
        
        Args:
            edge_threshold: Minimum edge for a model to vote positive
            use_dynamic_margin: Enable dynamic margin-based threshold adjustment
            tight_margin_threshold: Margin threshold to trigger tight mode (corners)
            tight_margin_consensus: Consensus required when margin is tight (0.5 = 50%)
        """
        self.edge_threshold = edge_threshold
        self.use_dynamic_margin = use_dynamic_margin
        self.tight_margin_threshold = tight_margin_threshold
        self.tight_margin_consensus = tight_margin_consensus

    def _compute_dynamic_threshold(
        self,
        mean_lambda: float,
        line: float,
        base_threshold: float = 0.45,
    ) -> float:
        """Compute dynamic consensus threshold based on lambda-line margin.
        
        When predictions are very close to the betting line (within tight_margin_threshold),
        increase consensus requirement to tight_margin_consensus for additional safety.
        
        Args:
            mean_lambda: Mean prediction from ensemble
            line: Betting line
            base_threshold: Default consensus threshold
            
        Returns:
            Adjusted consensus threshold
        """
        margin = abs(mean_lambda - line)
        if margin < self.tight_margin_threshold and self.use_dynamic_margin:
            return self.tight_margin_consensus
        return base_threshold

    def evaluate_with_consensus(
        self,
        predictions_list: Iterable[Dict],
        odds_data: Dict,
        threshold: float = 0.45,
        model_weights: Sequence[float] | None = None,
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
                Base consensus ratio required to confirm the bet (may be adjusted dynamically).
            model_weights:
                Optional per-model weights for weighted voting (P1.C2 SHAP).
                If None, all models vote with equal weight.

        Returns:
            Dict with voting distribution, agreement and final decision.
        """

        model_votes = []
        model_edges = []
        model_probs = []
        lambda_totals = []
        normalized_predictions = list(predictions_list)

        if not normalized_predictions:
            raise ValueError("predictions_list must contain at least one prediction.")

        line = float(odds_data["line"])
        odds = float(odds_data["odds"])
        bet_type = str(odds_data.get("type", "over")).lower()

        for idx, prediction in enumerate(normalized_predictions):
            try:
                lambda_total = _extract_lambda_total(prediction)
            except ValueError as e:
                logger.error(f"Failed to extract lambda from prediction {idx+1}/{len(normalized_predictions)}: {e}")
                raise
            
            if bet_type == "over":
                p_model = poisson_over_prob(lambda_total, line)
            else:
                p_model = poisson_under_prob(lambda_total, line)

            edge = calculate_edge(p_model=p_model, odds=odds)
            vote = 1 if edge >= self.edge_threshold else 0

            model_votes.append(vote)
            model_edges.append(edge)
            model_probs.append(p_model)
            lambda_totals.append(lambda_total)

        # Compute dynamic threshold based on margin if enabled
        mean_lambda = float(sum(lambda_totals) / len(lambda_totals)) if lambda_totals else line
        dynamic_threshold = self._compute_dynamic_threshold(
            mean_lambda=mean_lambda,
            line=line,
            base_threshold=threshold,
        )
        
        # Use dynamic threshold for decision
        threshold_to_use = dynamic_threshold

        total_models = len(model_votes)

        # P1.C2: Weighted voting when model_weights are provided
        if model_weights is not None and len(model_weights) == total_models:
            weighted_positive = sum(
                w * v for w, v in zip(model_weights, model_votes)
            )
            total_weight = sum(model_weights)
            agreement = weighted_positive / total_weight if total_weight > 0 else 0.0
            positive_votes = int(sum(model_votes))  # raw count for reporting
        else:
            positive_votes = int(sum(model_votes))
            agreement = positive_votes / total_models if total_models else 0.0

        should_place_bet = agreement >= threshold_to_use

        status_message = (
            f"Aposta confirmada (Agreement: {agreement:.0%})"
            if should_place_bet
            else f"Aposta descartada por falta de consenso (Agreement: {agreement:.0%})"
        )
        vote_distribution = f"{positive_votes}/{total_models} modelos concordam"
        decision_status = "Value Bet" if should_place_bet else "Insegura"
        consensus_label = (
            f"Consenso: {positive_votes}/{total_models} - {agreement:.0%} | "
            f"Status: {decision_status}"
        )
        audit_report = report_consensus(
            lambdas=lambda_totals,
            odds=odds,
            line=line,
            threshold_edge=self.edge_threshold,
            consensus_threshold=threshold_to_use,
        )

        logger.info(
            "%s | threshold=%.0f%% (base=%.0f%%) | edge_threshold=%.2f | votes=%s",
            consensus_label,
            threshold_to_use * 100,
            threshold * 100,
            self.edge_threshold,
            model_votes,
        )
        logger.info(
            "Ensemble lambda stats | mean=%.3f | std=%.3f | ranges=%s | margin=%.2f",
            audit_report["mean_lambda"],
            audit_report["std_lambda"],
            audit_report["ranges"],
            abs(mean_lambda - line),
        )
        logger.info("Audit report\n%s", audit_report["formatted_report"])

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
            "consensus_label": consensus_label,
            "decision_status": decision_status,
            "model_votes": model_votes,
            "model_edges": model_edges,
            "audit_report": audit_report["formatted_report"],
            "consensus_report": audit_report,
            "lambda_ranges": audit_report["ranges"],
            "ensemble_mean_lambda": audit_report["mean_lambda"],
            "ensemble_std_lambda": audit_report["std_lambda"],
            "status_message": status_message,
            "bet": should_place_bet,
            "is_value": should_place_bet,
        }

    def evaluate_match_with_consensus(
        self,
        predictions_list: Iterable[Dict],
        odds_data: Dict,
        threshold: float = 0.7,
        model_weights: Sequence[float] | None = None,
    ) -> Dict:
        """Alias explicito para integracao com pipeline/backtest."""

        return self.evaluate_with_consensus(
            predictions_list=predictions_list,
            odds_data=odds_data,
            threshold=threshold,
            model_weights=model_weights,
        )


def _extract_lambda_total(prediction: Dict) -> float:
    """Extract total lambda from a prediction payload.
    
    Validates that lambda is finite and non-negative.
    
    Raises:
        ValueError: If required fields missing or lambda is invalid
    """

    if "lambda_total" in prediction:
        lambda_total = float(prediction["lambda_total"])
    elif "lambda_home" in prediction and "lambda_away" in prediction:
        lambda_total = float(prediction["lambda_home"]) + float(prediction["lambda_away"])
    else:
        raise ValueError(
            "Each prediction must contain either 'lambda_total' or "
            "'lambda_home' and 'lambda_away'."
        )
    
    _validate_lambda(lambda_total, context="_extract_lambda_total")
    return lambda_total
