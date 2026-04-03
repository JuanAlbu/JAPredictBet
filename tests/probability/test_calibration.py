"""Tests for probability calibration metrics (P1.B1)."""

import pytest
import numpy as np

from japredictbet.probability.calibration import (
    brier_score,
    expected_calibration_error,
    calibration_report,
    format_calibration_report,
    CalibrationResult,
)


# =====================
# BRIER SCORE TESTS
# =====================


class TestBrierScore:
    """Tests for brier_score function."""

    def test_perfect_predictions(self):
        """Perfect predictions should give Brier = 0."""
        y_true = [1, 0, 1, 0, 1]
        y_prob = [1.0, 0.0, 1.0, 0.0, 1.0]
        assert brier_score(y_true, y_prob) == pytest.approx(0.0)

    def test_worst_predictions(self):
        """Completely wrong predictions should give Brier = 1."""
        y_true = [1, 0, 1, 0]
        y_prob = [0.0, 1.0, 0.0, 1.0]
        assert brier_score(y_true, y_prob) == pytest.approx(1.0)

    def test_uniform_predictions(self):
        """All 0.5 predictions on balanced outcomes: Brier = 0.25."""
        y_true = [1, 0, 1, 0]
        y_prob = [0.5, 0.5, 0.5, 0.5]
        assert brier_score(y_true, y_prob) == pytest.approx(0.25)

    def test_single_sample(self):
        """Single sample should work."""
        assert brier_score([1], [0.8]) == pytest.approx(0.04)

    def test_realistic_predictions(self):
        """Realistic case: probabilities near correct values."""
        y_true = [1, 1, 0, 0, 1]
        y_prob = [0.9, 0.8, 0.2, 0.1, 0.7]
        expected = np.mean([(0.9-1)**2, (0.8-1)**2, (0.2-0)**2, (0.1-0)**2, (0.7-1)**2])
        assert brier_score(y_true, y_prob) == pytest.approx(expected)

    def test_empty_raises(self):
        """Empty inputs should raise ValueError."""
        with pytest.raises(ValueError, match="not be empty"):
            brier_score([], [])

    def test_length_mismatch_raises(self):
        """Mismatched lengths should raise ValueError."""
        with pytest.raises(ValueError, match="Length mismatch"):
            brier_score([1, 0], [0.5])

    def test_numpy_input(self):
        """Should accept numpy arrays."""
        y_true = np.array([1, 0, 1])
        y_prob = np.array([0.9, 0.1, 0.8])
        result = brier_score(y_true, y_prob)
        assert 0.0 <= result <= 1.0


# =====================
# ECE TESTS
# =====================


class TestExpectedCalibrationError:
    """Tests for expected_calibration_error function."""

    def test_perfectly_calibrated(self):
        """100 samples: 50 with p=0.5 where exactly half are positive => ECE ~0."""
        np.random.seed(42)
        n = 1000
        y_prob = np.full(n, 0.5)
        y_true = np.array([1] * 500 + [0] * 500)
        ece, edges, accs, confs, counts = expected_calibration_error(y_true, y_prob, n_bins=10)
        assert ece < 0.05  # Near perfect calibration

    def test_all_correct_high_confidence(self):
        """All predictions at 0.95, all true => low ECE."""
        y_true = [1] * 100
        y_prob = [0.95] * 100
        ece, _, _, _, _ = expected_calibration_error(y_true, y_prob)
        assert ece < 0.10

    def test_overconfident_model(self):
        """High confidence but 50% accuracy => high ECE."""
        y_true = [1, 0] * 50  # 50% accuracy
        y_prob = [0.95] * 100  # 95% confidence
        ece, _, _, _, _ = expected_calibration_error(y_true, y_prob)
        assert ece > 0.30  # Badly calibrated

    def test_returns_correct_structure(self):
        """Check return value structure."""
        y_true = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        y_prob = [0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.6, 0.4, 0.5, 0.5]
        ece, edges, accs, confs, counts = expected_calibration_error(y_true, y_prob, n_bins=5)

        assert isinstance(ece, float)
        assert len(edges) == 6  # n_bins + 1
        assert len(accs) == 5
        assert len(confs) == 5
        assert len(counts) == 5
        assert sum(counts) == 10

    def test_bin_count(self):
        """Custom n_bins should work."""
        y_true = [1, 0, 1]
        y_prob = [0.9, 0.1, 0.5]
        _, edges, _, _, _ = expected_calibration_error(y_true, y_prob, n_bins=3)
        assert len(edges) == 4

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="not be empty"):
            expected_calibration_error([], [])

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="Length mismatch"):
            expected_calibration_error([1, 0], [0.5])

    def test_invalid_bins_raises(self):
        with pytest.raises(ValueError, match="n_bins"):
            expected_calibration_error([1], [0.5], n_bins=0)

    def test_ece_between_zero_and_one(self):
        """ECE should always be in [0, 1]."""
        np.random.seed(123)
        y_true = np.random.randint(0, 2, 200).tolist()
        y_prob = np.random.uniform(0, 1, 200).tolist()
        ece, _, _, _, _ = expected_calibration_error(y_true, y_prob)
        assert 0.0 <= ece <= 1.0


# =====================
# CALIBRATION REPORT TESTS
# =====================


class TestCalibrationReport:
    """Tests for calibration_report and format_calibration_report."""

    def test_returns_calibration_result(self):
        """Should return CalibrationResult dataclass."""
        y_true = [1, 0, 1, 0, 1]
        y_prob = [0.8, 0.2, 0.9, 0.1, 0.7]
        result = calibration_report(y_true, y_prob)

        assert isinstance(result, CalibrationResult)
        assert result.n_samples == 5
        assert 0.0 <= result.brier_score <= 1.0
        assert 0.0 <= result.ece <= 1.0

    def test_brier_matches_standalone(self):
        """Brier in report should match standalone function."""
        y_true = [1, 0, 1, 1, 0]
        y_prob = [0.7, 0.3, 0.8, 0.6, 0.2]
        result = calibration_report(y_true, y_prob)
        standalone = brier_score(y_true, y_prob)
        assert result.brier_score == pytest.approx(standalone)

    def test_format_report_string(self):
        """format_calibration_report should produce readable string."""
        y_true = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        y_prob = [0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.6, 0.4, 0.55, 0.45]
        result = calibration_report(y_true, y_prob, n_bins=5)
        text = format_calibration_report(result)

        assert "CALIBRATION REPORT" in text
        assert "Brier Score" in text
        assert "ECE" in text
        assert "Bin Details" in text

    def test_custom_bins(self):
        """Should respect n_bins parameter."""
        y_true = [1, 0] * 10
        y_prob = [0.7, 0.3] * 10
        result = calibration_report(y_true, y_prob, n_bins=5)
        assert len(result.bin_counts) == 5

    def test_large_sample_good_model(self):
        """Good model on large sample should have low Brier and ECE."""
        np.random.seed(42)
        n = 500
        # Generate well-calibrated predictions
        y_prob = np.random.uniform(0.1, 0.9, n)
        y_true = (np.random.uniform(0, 1, n) < y_prob).astype(int)

        result = calibration_report(y_true.tolist(), y_prob.tolist())
        assert result.brier_score < 0.30
        assert result.ece < 0.15
