import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.db.models.media import Media

client = TestClient(app)

@pytest.fixture(autouse=True)
def override_dependency():
    from app.api.v1.endpoints.media import get_current_user
    from app.models.auth import User
    app.dependency_overrides[get_current_user] = lambda: User(
        id="user_123", apple_sub="test_sub", hashed_password="fake_hash", is_superuser=False
    )
    yield
    app.dependency_overrides.pop(get_current_user)

def test_get_media_valid_geofence_and_time_range(capture_log_records):
    """
    Test valid geofence and time range returns 200 OK with expected media list.
    """
    # Reset log records
    capture_log_records.clear()

    # Mock Media.filter() and return value
    mock_query = MagicMock()
    mock_query.all.return_value = [
        MagicMock(
            id=1,
            capture_time=datetime.now(timezone.utc),
            lat=37.7749,
            lng=-122.4194,
            orientation=0,
            trust_score=95,
            user_id="user_123",
            file_path="/test/path/file.jpg"
        )
    ]
    with patch("app.api.v1.endpoints.media.Media.filter", return_value=mock_query):
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

    # Assert 200 OK
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert len(data["media"]) == 1
    assert data["media"][0]["id"] == 1
    assert data["media"][0]["trust_score"] == 95

    # Verify correct log messages
    logs = [record.msg for record in capture_log_records]
    assert any("requesting media with filters" in msg for msg in logs)
    assert any("query media records" in msg for msg in logs)
    assert any("Successfully retrieved 1 media records" in msg for msg in logs)

def test_get_media_invalid_lat():
    """
    Test invalid lat (e.g., 100) returns 422.
    """
    response = client.get(
        "/api/v1/media",
        params={
            "lat": 100.0,
            "lng": -122.4194,
            "radius": 1000,
            "start_date": datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat(),
            "end_date": datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat(),
        }
    )
    assert response.status_code == 422
    assert any("Latitude must be between -90 and 90 degrees" in err["msg"] for err in response.json()["detail"])

def test_get_media_invalid_radius():
    """
    Test invalid radius (e.g., -5) returns 422.
    """
    response = client.get(
        "/api/v1/media",
        params={
            "lat": 37.7749,
            "lng": -122.4194,
            "radius": -5,
            "start_date": datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat(),
            "end_date": datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat(),
        }
    )
    assert response.status_code == 422
    assert any("Radius must be greater than 0" in err["msg"] for err in response.json()["detail"])

def test_get_media_start_date_after_end_date():
    """
    Test start_date after end_date returns 422.
    """
    response = client.get(
        "/api/v1/media",
        params={
            "lat": 37.7749,
            "lng": -122.4194,
            "radius": 1000,
            "start_date": datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat(),
            "end_date": datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat(),
        }
    )
    assert response.status_code == 422
    assert any("start_date must be before end_date" in err["msg"] for err in response.json()["detail"])

def test_get_media_missing_optional_parameters(capture_log_records):
    """
    Test that optional parameters (start_date, end_date) can be omitted.
    """
    capture_log_records.clear()
    mock_query = MagicMock()
    mock_query.all.return_value = []
    with patch("app.api.v1.endpoints.media.Media.filter", return_value=mock_query):
        response = client.get(
            "/api/v1/media",
            params={
                "lat": 37.7749,
                "lng": -122.4194,
                "radius": 1000
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert "media" in data
    assert "count" in data
    assert data["count"] == 0

    # Verify logging still works
    logs = [record.msg for record in capture_log_records]
    assert any("requesting media with filters" in msg for msg in logs)

def test_get_media_database_error(capture_log_records):
    """
    Test database error (mock Media.filter() to raise exception) returns 500.
    """
    capture_log_records.clear()
    with patch("app.api.v1.endpoints.media.Media.filter") as mock_filter:
        mock_filter.side_effect = Exception("DB Error")

        response = client.get(
            "/api/v1/media",
            params={
                "lat": 37.7749,
                "lng": -122.4194,
                "radius": 1000,
                "start_date": datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat(),
                "end_date": datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat(),
            }
        )

    assert response.status_code == 500
    assert "Failed to retrieve media records" in response.json()["detail"]

    # Verify error log
    error_logs = [record for record in capture_log_records if record.levelname == "ERROR"]
    assert len(error_logs) >= 1
    assert any("Failed to retrieve media records" in record.msg for record in error_logs)

def test_get_media_authenticated_user_context():
    """
    Ensure that authenticated user context is properly passed and checked.
    This test verifies that the request fails if no authentication is provided.
    """
    # Remove override to test actual behavior
    app.dependency_overrides.clear()

    response = client.get(
        "/api/v1/media",
        params={
            "lat": 37.7749,
            "lng": -122.4194,
            "radius": 1000
        }
    )
    assert response.status_code == 401  # Unauthorized
