import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import logging

from app.main import app

# Configure logger
logger = logging.getLogger(__name__)

client = TestClient(app)

@pytest.fixture
def mock_db_session():
    with patch("app.api.v1.endpoints.comments.get_db") as mock:
        db_session = MagicMock()
        mock.return_value = db_session
        yield db_session

@pytest.fixture
def mock_get_current_user():
    with patch("app.api.v1.endpoints.comments.get_current_user") as mock:
        mock.return_value = {"userId": "user_123"}
        yield mock

def test_create_comment_success(mock_db_session, mock_get_current_user):
    """
    Test POST with valid media_id, valid text, and authenticated user.
    Expect 201 and response body with correct comment data.
    """
    logger.info("Starting test: test_create_comment_success")
    
    media_id = "valid_media_1"
    comment_text = "This is a valid comment."
    
    # Mock comment creation
    mock_comment = MagicMock()
    mock_comment.id = 1
    mock_comment.media_id = media_id
    mock_comment.text = comment_text
    mock_comment.user_id = "user_123"
    mock_comment.created_at = "2023-01-01T00:00:00"

    mock_db_session.add.return_value = None
    mock_db_session.commit.return_value = None
    mock_db_session.refresh.return_value = None
    with patch("app.db.models.comment.Comment", return_value=mock_comment):
        response = client.post(
            f"/api/v1/comments/{media_id}",
            json={"text": comment_text}
        )
    
    logger.info(f"Response status code: {response.status_code}")
    logger.info(f"Response JSON: {response.json()}")
    
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["id"] == 1
    assert response_data["media_id"] == media_id
    assert response_data["text"] == comment_text
    assert response_data["user_id"] == "user_123"
    assert response_data["success"] is True
    
    logger.info("Completed test: test_create_comment_success")

def test_create_comment_media_not_found():
    """
    Test POST with non-existent media_id: expect 404 Not Found.
    """
    logger.info("Starting test: test_create_comment_media_not_found")
    
    media_id = "not_found"
    comment_text = "This comment should not be created."

    response = client.post(
        f"/api/v1/comments/{media_id}",
        json={"text": comment_text}
    )
    
    logger.info(f"Response status code: {response.status_code}")
    logger.info(f"Response JSON: {response.json()}")
    
    assert response.status_code == 404
    response_data = response.json()
    assert response_data["error"] == "MEDIA_NOT_FOUND"
    
    logger.info("Completed test: test_create_comment_media_not_found")

def test_create_comment_invalid_body():
    """
    Test POST with invalid request body (e.g., empty text): expect 422 Unprocessable Entity.
    """
    logger.info("Starting test: test_create_comment_invalid_body")
    
    media_id = "valid_media_1"

    response = client.post(
        f"/api/v1/comments/{media_id}",
        json={"text": ""}
    )
    
    logger.info(f"Response status code: {response.status_code}")
    
    assert response.status_code == 422
    
    logger.info("Completed test: test_create_comment_invalid_body")

def test_create_comment_unauthenticated():
    """
    Test POST with unauthenticated user: expect 401 Unauthorized.
    """
    logger.info("Starting test: test_create_comment_unauthenticated")
    
    media_id = "valid_media_1"
    comment_text = "This comment should not be created."

    with patch("app.middleware.auth.get_current_user") as mock_auth:
        mock_auth.side_effect = Exception("Invalid token")
        response = client.post(
            f"/api/v1/comments/{media_id}",
            json={"text": comment_text}
        )
    
    logger.info(f"Response status code: {response.status_code}")
    logger.info(f"Response JSON: {response.json()}")
    
    assert response.status_code == 401
    
    logger.info("Completed test: test_create_comment_unauthenticated")

def test_get_comments_success(mock_db_session, mock_get_current_user):
    """
    Test GET with valid media_id: expect 200 and list containing the previously created comment.
    """
    logger.info("Starting test: test_get_comments_success")
    
    media_id = "valid_media_1"
    
    # Mock existing comments
    mock_comment = MagicMock()
    mock_comment.id = 1
    mock_comment.media_id = media_id
    mock_comment.text = "This is a test comment."
    mock_comment.user_id = "user_123"
    mock_comment.created_at = "2023-01-01T00:00:00"
    
    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_comment]
    
    response = client.get(f"/api/v1/comments/{media_id}")
    
    logger.info(f"Response status code: {response.status_code}")
    logger.info(f"Response JSON: {response.json()}")
    
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["id"] == 1
    assert response_data[0]["text"] == "This is a test comment."
    
    logger.info("Completed test: test_get_comments_success")

def test_get_comments_non_existent_media(mock_db_session, mock_get_current_user):
    """
    Test GET with non-existent media_id: expect 200 with empty list.
    """
    logger.info("Starting test: test_get_comments_non_existent_media")
    
    media_id = "invalid"
    
    mock_db_session.query.return_value.filter.return_value.all.return_value = []
    
    response = client.get(f"/api/v1/comments/{media_id}")
    
    logger.info(f"Response status code: {response.status_code}")
    logger.info(f"Response JSON: {response.json()}")
    
    assert response.status_code == 200
    assert response.json() == []
    
    logger.info("Completed test: test_get_comments_non_existent_media")
