"""Probability calibration metrics for model evaluation.

Provides Brier Score and Expected Calibration Error (ECE) to measure
how well predicted probabilities match observed frequencies.

P1.B1 implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalibrationResult:
    """Container for calibration metrics."""

    brier_score: float
    ece: float
    n_samples: int
    bin_edges: tuple[float, ...]
    bin_accuracies: tuple[float, ...]
    bin_confidences: tuple[float, ...]
    bin_counts: tuple[int, ...]


def brier_score(y_true: Sequence[int], y_prob: Sequence[float]) -> float:
    """Compute Brier Score: mean squared error between predicted probs and outcomes.

    Lower is better. Perfect calibration = 0.0, worst = 1.0.

    Args:
        y_true: Binary outcomes (1 = event occurred, 0 = not).
        y_prob: Predicted probabilities for the event.

    Returns:
        Brier Score (float).

    Raises:
        ValueError: If inputs are empty or have mismatched lengths.
    """
    y_true_arr = np.asarray(y_true, dtype=float)
    y_prob_arr = np.asarray(y_prob, dtype=float)

    if len(y_true_arr) == 0:
        raise ValueError("y_true must not be empty.")
    if len(y_true_arr) != len(y_prob_arr):
        raise ValueError(
            f"Length mismatch: y_true={len(y_true_arr)}, y_prob={len(y_prob_arr)}"
        )

    return float(np.mean((y_prob_arr - y_true_arr) ** 2))


def expected_calibration_error(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    n_bins: int = 10,
) -> tuple[float, list[float], list[float], list[float], list[int]]:
    """Compute Expected Calibration Error (ECE).

    Bins predictions by confidence, computes accuracy vs confidence gap per bin,
    then returns weighted average gap.

    Lower is better. 0.0 = perfectly calibrated.

    Args:
        y_true: Binary outcomes (1 = event occurred, 0 = not).
        y_prob: Predicted probabilities for the event.
        n_bins: Number of equal-width bins (default 10).

    Returns:
        Tuple of (ece, bin_edges, bin_accuracies, bin_confidences, bin_counts).

    Raises:
        ValueError: If inputs are empty, mismatched, or n_bins < 1.
    """
    y_true_arr = np.asarray(y_true, dtype=float)
    y_prob_arr = np.asarray(y_prob, dtype=float)

    if len(y_true_arr) == 0:
        raise ValueError("y_true must not be empty.")
    if len(y_true_arr) != len(y_prob_arr):
        raise ValueError(
            f"Length mismatch: y_true={len(y_true_arr)}, y_prob={len(y_prob_arr)}"
        )
    if n_bins < 1:
        raise ValueError(f"n_bins must be >= 1, got {n_bins}")

    bin_edges_arr = np.linspace(0.0, 1.0, n_bins + 1)
    bin_edges = bin_edges_arr.tolist()

    bin_accuracies: list[float] = []
    bin_confidences: list[float] = []
    bin_counts: list[int] = []

    n_total = len(y_true_arr)
    ece = 0.0

    for i in range(n_bins):
        lower = bin_edges_arr[i]
        upper = bin_edges_arr[i + 1]

        if i < n_bins - 1:
            mask = (y_prob_arr >= lower) & (y_prob_arr < upper)
        else:
            # Last bin includes right edge
            mask = (y_prob_arr >= lower) & (y_prob_arr <= upper)

        count = int(mask.sum())
        bin_counts.append(count)

        if count == 0:
            bin_accuracies.append(0.0)
            bin_confidences.append(0.0)
            continue

        acc = float(y_true_arr[mask].mean())
        conf = float(y_prob_arr[mask].mean())

        bin_accuracies.append(acc)
        bin_confidences.append(conf)

        ece += (count / n_total) * abs(acc - conf)

    return ece, bin_edges, bin_accuracies, bin_confidences, bin_counts


def calibration_report(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    n_bins: int = 10,
) -> CalibrationResult:
    """Compute full calibration report with Brier Score and ECE.

    Args:
        y_true: Binary outcomes (1 = event occurred, 0 = not).
        y_prob: Predicted probabilities for the event.
        n_bins: Number of bins for ECE calculation.

    Returns:
        CalibrationResult with all metrics and bin details.
    """
    bs = brier_score(y_true, y_prob)
    ece_val, edges, accuracies, confidences, counts = expected_calibration_error(
        y_true, y_prob, n_bins=n_bins
    )

    result = CalibrationResult(
        brier_score=bs,
        ece=ece_val,
        n_samples=len(y_true),
        bin_edges=tuple(edges),
        bin_accuracies=tuple(accuracies),
        bin_confidences=tuple(confidences),
        bin_counts=tuple(counts),
    )

    logger.info(
        "Calibration: Brier=%.4f ECE=%.4f (n=%d, bins=%d)",
        result.brier_score,
        result.ece,
        result.n_samples,
        n_bins,
    )

    return result


def format_calibration_report(result: CalibrationResult) -> str:
    """Format calibration result as human-readable text.

    Args:
        result: CalibrationResult from calibration_report().

    Returns:
        Formatted multi-line string.
    """
    lines = [
        "=" * 50,
        "CALIBRATION REPORT",
        "=" * 50,
        f"Samples: {result.n_samples}",
        f"Brier Score: {result.brier_score:.4f}  (0=perfect, 1=worst)",
        f"ECE:         {result.ece:.4f}  (0=perfect calibration)",
        "",
        "Bin Details:",
        f"{'Bin':>12} | {'Count':>5} | {'Accuracy':>8} | {'Confidence':>10} | {'Gap':>6}",
        "-" * 55,
    ]

    n_bins = len(result.bin_counts)
    for i in range(n_bins):
        lower = result.bin_edges[i]
        upper = result.bin_edges[i + 1]
        count = result.bin_counts[i]
        acc = result.bin_accuracies[i]
        conf = result.bin_confidences[i]
        gap = abs(acc - conf) if count > 0 else 0.0
        lines.append(
            f"[{lower:.1f}-{upper:.1f}] | {count:>5} | {acc:>8.3f} | {conf:>10.3f} | {gap:>6.3f}"
        )

    lines.extend([
        "-" * 55,
        f"Interpretation:",
        f"  Brier < 0.20 = good    | ECE < 0.05 = well calibrated",
        f"  Brier < 0.25 = fair    | ECE < 0.10 = acceptable",
        "=" * 50,
    ])

    return "\n".join(lines)
