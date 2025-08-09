import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from app.services.trust import calculate_trust_score

# Helper to create timezone-aware datetime
def dt(*args):
    return datetime(*args, tzinfo=timezone.utc)

class TestCalculateTrustScore:
    def test_valid_small_delay(self):
        capture = dt(2023, 1, 1, 12, 0, 0)
        upload = dt(2023, 1, 1, 12, 5, 0)  # 5 minutes later
        score = calculate_trust_score(capture, upload)
        assert score == 95

    def test_large_delay_yields_zero(self):
        capture = dt(2023, 1, 1, 12, 0, 0)
        upload = dt(2023, 1, 1, 15, 20, 0)  # 200 minutes later
        score = calculate_trust_score(capture, upload)
        assert score == 0

    def test_equal_timestamps_yields_max(self):
        capture = dt(2023, 1, 1, 12, 0, 0)
        upload = dt(2023, 1, 1, 12, 0, 0)
        score = calculate_trust_score(capture, upload)
        assert score == 100

    def test_none_timestamps_returns_zero_and_logs_warning(self, caplog):
        with caplog.at_level("WARNING"):
            score = calculate_trust_score(None, dt(2023, 1, 1, 12, 0, 0))
            assert score == 0
            assert "Timestamp is None" in caplog.text

        caplog.clear()

        with caplog.at_level("WARNING"):
            score = calculate_trust_score(dt(2023, 1, 1, 12, 0, 0), None)
            assert score == 0
            assert "Timestamp is None" in caplog.text

    def test_invalid_type_timestamps_returns_zero_and_logs_warning(self, caplog):
        with caplog.at_level("WARNING"):
            score = calculate_trust_score("not-a-datetime", dt(2023, 1, 1, 12, 0, 0))
            assert score == 0
            assert "Invalid timestamp type" in caplog.text

        caplog.clear()

        with caplog.at_level("WARNING"):
            score = calculate_trust_score(dt(2023, 1, 1, 12, 0, 0), 123)
            assert score == 0
            assert "Invalid timestamp type" in caplog.text

    def test_capture_after_upload_returns_zero_and_logs_warning(self, caplog):
        capture = dt(2023, 1, 1, 13, 0, 0)
        upload = dt(2023, 1, 1, 12, 0, 0)  # earlier upload
        with caplog.at_level("WARNING"):
            score = calculate_trust_score(capture, upload)
            assert score == 0
            assert "Capture time is after upload time" in caplog.text

    def test_negative_time_diff_exception_handled_gracefully(self, caplog):
        # This case is already handled by capture > upload, but testing robustness
        capture = dt(2023, 1, 1, 12, 0, 5)
        upload = dt(2023, 1, 1, 12, 0, 0)
        with caplog.at_level("WARNING"):
            score = calculate_trust_score(capture, upload)
            assert score == 0
            assert "Capture time is after upload time" in caplog.text
