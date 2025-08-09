import pytest
import logging
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.main import app
from app.db.models import Media

client = TestClient(app)

# Test logger setup
@pytest.fixture
def test_logger():
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    return logger

# Mock database session
@pytest.fixture
def mock_db_session():
    with patch("app.api.v1.endpoints.media.SessionLocal") as mock:
        session = MagicMock(spec=Session)
        mock.return_value = session
        yield session

# Mock Media.filter behavior
@pytest.fixture(autouse=True)
def mock_media_filter():
    with patch("app.api.v1.endpoints.media.Media.filter") as mock:
        yield mock

# Auth mock to bypass actual auth
@pytest.fixture(autouse=True)
def override_dependency():
    from app.api.v1.endpoints.media import get_current_user
    from app.models.auth import User
    app.dependency_overrides[get_current_user] = lambda: User(id=1, apple_sub="test_sub", hashed_password="fake_hash")
    yield
    app.dependency_overrides.pop(get_current_user)

def test_get_media_valid_geofence_and_time_range(mock_media_filter, test_logger):
    """
    Test valid geofence and time range: expect 200 OK and non-empty results.
    """
    # Mock current user and logger
    with patch("app.api.v1.endpoints.media.logger", test_logger):
        mock_media_filter.return_value.all.return_value = [
            MagicMock(
                id=1,
                capture_time=datetime.now(timezone.utc),
                lat=37.7749,
                lng=-122.4194,
                orientation=0,
                trust_score=95,
                user_id=1,
                file_path="/test/path/file.jpg"
            )
        ]

        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat()
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat()
        response = client.get(
            "/api/v1/media",
            params={
                "lat": 37.7749,
                "lng": -122.4194,
                "radius": 1000,
                "start_date": start_date,
                "end_date": end_date
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["media"]) == 1
        assert data["media"][0]["id"] == 1
        assert data["media"][0]["trust_score"] == 95

        # Verify logging
        logs = [record for record in test_logger.handlers[0].buffer if "retrieved" in record.msg]
        assert len(logs) == 1
        assert "Successfully retrieved 1 media records" in logs[0].msg

def test_get_media_no_matching_media(mock_media_filter, test_logger):
    """
    Test valid parameters but no matching media: expect 200 OK with empty list.
    """
    with patch("app.api.v1.endpoints.media.logger", test_logger):
        mock_media_filter.return_value.all.return_value = []

        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat()
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat()
        response = client.get(
            "/api/v1/media",
            params={
                "lat": 37.7749,
                "lng": -122.4194,
                "radius": 1000,
                "start_date": start_date,
                "end_date": end_date
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["media"] == []

        # Verify logging
        logs = [record for record in test_logger.handlers[0].buffer if "retrieved" in record.msg]
        assert len(logs) == 1
        assert "Successfully retrieved 0 media records" in logs[0].msg

def test_get_media_missing_lng_when_lat_provided():
    """
    Test missing lng when lat is provided: expect 422 Unprocessable Entity.
    """
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat()
    end_date = datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat()
    response = client.get(
        "/api/v1/media",
        params={
            "lat": 37.7749,
            "radius": 1000,
            "start_date": start_date,
            "end_date": end_date
        }
    )
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("lng must be provided when lat is specified" in err["msg"] for err in errors)

def test_get_media_missing_radius_when_lat_provided():
    """
    Test missing radius when lat is provided: expect 422 Unprocessable Entity.
    """
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat()
    end_date = datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat()
    response = client.get(
        "/api/v1/media",
        params={
            "lat": 37.7749,
            "lng": -122.4194,
            "start_date": start_date,
            "end_date": end_date
        }
    )
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("radius must be provided when lat is specified" in err["msg"] for err in errors)

def test_get_media_invalid_lat():
    """
    Test invalid lat (e.g., 100.0): expect 422.
    """
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat()
    end_date = datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat()
    response = client.get(
        "/api/v1/media",
        params={
            "lat": 100.0,
            "lng": -122.4194,
            "radius": 1000,
            "start_date": start_date,
            "end_date": end_date
        }
    )
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("ensure this value is less than or equal to 90" in err["msg"] for err in errors)

def test_get_media_invalid_iso_datetime_format():
    """
    Test invalid ISO datetime format: expect 422.
    """
    response = client.get(
        "/api/v1/media",
        params={
            "lat": 37.7749,
            "lng": -122.4194,
            "radius": 1000,
            "start_date": "invalid-date",
            "end_date": "2023-12-31T23:59:59Z"
        }
    )
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("Invalid datetime" in err["msg"] for err in errors)

def test_get_media_database_failure(mock_media_filter, test_logger):
    """
    Test simulated database failure: expect 500 Internal Server Error.
    """
    with patch("app.api.v1.endpoints.media.logger", test_logger):
        mock_media_filter.side_effect = Exception("DB connection failed")

        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat()
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat()
        response = client.get(
            "/api/v1/media",
            params={
                "lat": 37.7749,
                "lng": -122.4194,
                "radius": 1000,
                "start_date": start_date,
                "end_date": end_date
            }
        )

        assert response.status_code == 500
        assert "Failed to retrieve media records" in response.json()["detail"]

        # Verify error logging
        logs = [record for record in test_logger.handlers[0].buffer if record.levelname == "ERROR"]
        assert len(logs) >= 1
        assert any("Failed to retrieve media records" in record.msg for record in logs)

def test_get_media_requires_authentication():
    """
    Test that get_media endpoint requires authentication.
    This checks that the get_current_user dependency is enforced.
    """
    # Temporarily remove override to test actual auth requirement
    app.dependency_overrides.clear()

    response = client.get("/api/v1/media")
    assert response.status_code == 401  # Unauthorized

    # Restore overrides
    from app.api.v1.endpoints.media import get_current_user
    from app.models.auth import User
    app.dependency_overrides[get_current_user] = lambda: User(id=1, apple_sub="test_sub", hashed_password="fake_hash")

def test_get_media_logs_info_on_request(test_logger, mock_media_filter):
    """
    Test that info-level logs are written for normal operation.
    """
    with patch("app.api.v1.endpoints.media.logger", test_logger):
        mock_media_filter.return_value.all.return_value = []

        start_date = datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat()
        end_date = datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat()
        client.get(
            "/api/v1/media",
            params={
                "lat": 37.7749,
                "lng": -122.4194,
                "radius": 1000,
                "start_date": start_date,
                "end_date": end_date
            }
        )

        # Check for INFO logs
        info_logs = [record for record in test_logger.handlers[0].buffer if record.levelname == "INFO"]
        assert len(info_logs) >= 2
        assert any("requesting media with filters" in record.msg for record in info_logs)
        assert any("query media records" in record.msg for record in info_logs)
