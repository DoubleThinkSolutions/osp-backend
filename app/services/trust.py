from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def calculate_trust_score(capture_time: datetime, upload_time: datetime) -> int:
    """
    Calculate the trust score based on the time difference between capture and upload.

    Formula: max(0, 100 - (upload_time - capture_time).total_seconds() / 60)
    The score decreases by 1 point per minute, starting from 100.

    Args:
        capture_time (datetime): When the media was captured.
        upload_time (datetime): When the media was uploaded.

    Returns:
        int: Calculated trust score (0 to 100), or 0 if inputs are invalid.
    """
    # Validate inputs
    if not isinstance(capture_time, datetime) or not isinstance(upload_time, datetime):
        logger.warning("Invalid timestamp type: capture_time=%s (%s), upload_time=%s (%s)",
                      capture_time, type(capture_time).__name__,
                      upload_time, type(upload_time).__name__)
        return 0

    if capture_time is None or upload_time is None:
        logger.warning("Timestamp is None: capture_time=%s, upload_time=%s", capture_time, upload_time)
        return 0

    if capture_time > upload_time:
        logger.warning("Capture time is after upload time: %s > %s", capture_time, upload_time)
        return 0

    try:
        time_diff_seconds = (upload_time - capture_time).total_seconds()
        score = max(0, 100 - time_diff_seconds / 60)
        return int(score)  # Round down
    except Exception as e:
        logger.warning("Error calculating trust score: %s", e)
        return 0
