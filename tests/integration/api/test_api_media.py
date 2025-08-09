import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.db.models import Media
from app.core.logging import logger
import logging

client = TestClient(app)

class TestMediaUpload:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        # Setup: Clear any existing media records
        Media.query.delete()
        yield
        # Teardown: Clean up after each test
        Media.query.delete()

    @pytest.fixture
    def mock_storage_save(self):
        with patch("app.api.v1.endpoints.media.save_file") as mock:
            mock.return_value = "test-uuid.jpg"
            yield mock

    @pytest.fixture
    def mock_media_create(self):
        with patch("app.api.v1.endpoints.media.Media.create") as mock:
            mock.return_value = Media(
                id=1,
                capture_time=datetime.now(timezone.utc),
                lat=40.7128,
                lng=-74.0060,
                orientation=0,
                trust_score=95,
                user_id=1,
                file_path="test-uuid.jpg"
            )
            yield mock

    @pytest.fixture
    def authenticated_client(self):
        # Mock authentication - bypass real auth
        with patch("app.api.v1.endpoints.media.get_current_user") as mock:
            mock.return_value = MagicMock(id=1, username="testuser")
            yield client

    def test_successful_upload(self, authenticated_client, mock_storage_save, mock_media_create, caplog):
        caplog.set_level(logging.INFO)
        
        # Prepare test data
        file_content = b"fake jpeg content"
        files = {"file": ("test.jpg", file_content, "image/jpeg")}
        data = {
            "capture_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "lat": 40.7128,
            "lng": -74.0060,
            "orientation": 90
        }

        # Make request
        response = authenticated_client.post("/api/v1/media", files=files, data=data)

        # Assertions
        assert response.status_code == 201
        assert "id" in response.json()
        assert response.json()["lat"] == 40.7128
        assert response.json()["lng"] == -74.0060
        assert response.json()["orientation"] == 90
        assert 0 <= response.json()["trust_score"] <= 100

        # Verify mocks were called correctly
        mock_storage_save.assert_called_once_with(
            file_content, "image/jpeg", 19  # len(b"fake jpeg content")
        )
        mock_media_create.assert_called_once()

        # Verify logs
        assert any("attempting media upload" in record.message.lower() for record in caplog.records)
        assert any("trust score calculated" in record.message.lower() for record in caplog.records)
        assert any("file saved at" in record.message.lower() for record in caplog.records)
        assert any("media record created" in record.message.lower() for record in caplog.records)

    def test_invalid_file_type(self, authenticated_client):
        # Prepare test data with invalid content type
        files = {"file": ("test.pdf", b"fake pdf", "application/pdf")}
        data = {
            "capture_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "lat": 40.7128,
            "lng": -74.0060
        }

        # Make request
        response = authenticated_client.post("/api/v1/media", files=files, data=data)

        # Assertions
        assert response.status_code == 415
        assert "unsupported media type" in response.json()["detail"].lower()

    def test_file_too_large(self, authenticated_client):
        # Mock storage save to raise size error
        with patch("app.api.v1.endpoints.media.save_file") as mock_save:
            mock_save.side_effect = ValueError("File size exceeds maximum limit")

            # Prepare large file
            files = {"file": ("test.jpg", b"0" * (100 * 1024 * 1024 + 1), "image/jpeg")}
            data = {
                "capture_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                "lat": 40.7128,
                "lng": -74.0060
            }

            # Make request
            response = authenticated_client.post("/api/v1/media", files=files, data=data)

            # Assertions
            assert response.status_code == 413
            assert "file too large" in response.json()["detail"].lower()

    def test_missing_capture_time(self, authenticated_client):
        # Prepare data without capture_time
        file_content = b"fake jpeg content"
        files = {"file": ("test.jpg", file_content, "image/jpeg")}
        data = {
            "lat": 40.7128,
            "lng": -74.0060
        }

        # Make request
        response = authenticated_client.post("/api/v1/media", files=files, data=data)

        # Assertions
        assert response.status_code == 422  # Unprocessable Entity

    def test_invalid_latitude(self, authenticated_client):
        # Prepare data with invalid lat
        file_content = b"fake jpeg content"
        files = {"file": ("test.jpg", file_content, "image/jpeg")}
        data = {
            "capture_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "lat": 100.0,  # Invalid
            "lng": -74.0060
        }

        # Make request
        response = authenticated_client.post("/api/v1/media", files=files, data=data)

        # Assertions
        assert response.status_code == 422

    def test_invalid_longitude(self, authenticated_client):
        # Prepare data with invalid lng
        file_content = b"fake jpeg content"
        files = {"file": ("test.jpg", file_content, "image/jpeg")}
        data = {
            "capture_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "lat": 40.7128,
            "lng": 200.0  # Invalid
        }

        # Make request
        response = authenticated_client.post("/api/v1/media", files=files, data=data)

        # Assertions
        assert response.status_code == 422

    def test_unauthenticated_request(self):
        # Don't use authenticated_client fixture - test without auth
        file_content = b"fake jpeg content"
        files = {"file": ("test.jpg", file_content, "image/jpeg")}
        data = {
            "capture_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "lat": 40.7128,
            "lng": -74.0060
        }

        # Make request without authentication
        response = client.post("/api/v1/media", files=files, data=data)

        # Assertions
        assert response.status_code == 401

    def test_trust_score_calculation(self, authenticated_client, mock_storage_save, mock_media_create):
        # Test with various time differences
        test_cases = [
            (0, 100),      # 0 seconds difference -> 100
            (60, 99),      # 1 minute -> 99
            (300, 95),     # 5 minutes -> 95
            (3600, 40),    # 1 hour -> 40
            (6000, 0),     # 100 minutes -> 0 (min bound)
        ]

        for seconds_diff, expected_score in test_cases:
            with self.subTest(seconds_diff=seconds_diff):
                # Set capture time in the past
                capture_time = datetime.now(timezone.utc) - timedelta(seconds=seconds_diff)
                
                files = {"file": ("test.jpg", b"fake", "image/jpeg")}
                data = {
                    "capture_time": capture_time.isoformat(),
                    "lat": 40.7128,
                    "lng": -74.0060
                }

                response = authenticated_client.post("/api/v1/media", files=files, data=data)

                assert response.status_code == 201
                assert response.json()["trust_score"] == expected_score

    def test_filename_uuid_and_extension(self, authenticated_client, mock_storage_save, mock_media_create, caplog):
        # Make upload request
        files = {"file": ("test_image.jpg", b"fake", "image/jpeg")}
        data = {
            "capture_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "lat": 40.7128,
            "lng": -74.0060
        }

        authenticated_client.post("/api/v1/media", files=files, data=data)

        # Verify save_file was called with correct arguments
        assert mock_storage_save.called
        call_args = mock_storage_save.call_args[0]
        file_data = call_args[0]
        content_type = call_args[1]
        file_size = call_args[2]
        
        assert content_type in ["image/jpeg", "video/mp4"]
        expected_ext = ".jpg" if content_type == "image/jpeg" else ".mp4"
        
        # Extract filename from file_path returned by Media.create
        create_kwargs = mock_media_create.call_args[1]
        saved_filename = create_kwargs['file_path']
        
        # Filename should be UUID v4 + extension
        assert saved_filename.endswith(expected_ext)
        name_part = saved_filename[:-len(expected_ext)]
        try:
            uuid.UUID(name_part, version=4)
        except ValueError:
            pytest.fail(f"Filename {name_part} is not a valid UUID v4")

        # Also verify extension preservation when no extension in original
        files_no_ext = {"file": ("test", b"fake", "image/jpeg")}
        data_no_ext = {
            "capture_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "lat": 40.7128,
            "lng": -74.0060
        }
        authenticated_client.post("/api/v1/media", files=files_no_ext, data=data_no_ext)
        
        # Check that the extension was properly assigned based on content type
        final_call_args = mock_media_create.call_args[1]
        final_filename = final_call_args['file_path']
        assert final_filename.endswith(".jpg")
