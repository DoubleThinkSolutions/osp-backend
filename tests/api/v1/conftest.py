import logging
from unittest.mock import Mock
from _pytest.logging import LogCaptureHandler
from _pytest.monkeypatch import MonkeyPatch

@pytest.fixture(autouse=True)
def test_logger():
    logger = logging.getLogger("app.core.logging")
    logger.setLevel(logging.DEBUG)
    # Add a handler that captures log records
    handler = LogCaptureHandler([])
    logger.addHandler(handler)
    yield logger
    logger.removeHandler(handler)

@pytest.fixture
def capture_log_records(test_logger):
    # Clear existing records
    test_logger.handlers[0].records.clear()
    return test_logger.handlers[0].records
