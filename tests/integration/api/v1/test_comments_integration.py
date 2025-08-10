"""
Integration tests for comment endpoints verifying actual database persistence.
These tests use a real database connection and transaction rollback to validate
that comments are correctly stored and retrieved from the database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.models import Media, Comment

client = TestClient(app)

@pytest.mark.integration
def test_comment_persistence(db: Session, test_user):
    """
    Verifies comment creation results in actual database persistence and proper retrieval.
    
    Steps:
    1. Creates a valid media record directly in the database
    2. Creates a comment via API endpoint
    3. Validates database contains the comment with expected attributes
    4. Confirms GET endpoint returns the created comment
    """
    # Setup - create valid media in database
    media = Media(
        id="test_media_integration_001",
        title="Integration Test Media",
        user_id=test_user.id,
        media_type="video",
        status="processing"
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    # Create comment via API
    comment_payload = {"text": "Integration test comment"}
    response = client.post(
        f"/api/v1/comments/{media.id}",
        json=comment_payload,
        headers={"Authorization": f"Bearer {test_user.token}"}
    )
    
    # Validate API response
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["text"] == comment_payload["text"]
    assert response_data["media_id"] == media.id
    assert response_data["user_id"] == test_user.id

    # DIRECT DATABASE VERIFICATION (key requirement)
    comment = db.query(Comment).filter(Comment.id == response_data["id"]).first()
    assert comment is not None, "Comment not found in database"
    assert comment.text == comment_payload["text"]
    assert comment.media_id == media.id
    assert comment.user_id == test_user.id
    assert comment.created_at is not None

    # Validate GET endpoint returns the comment
    get_response = client.get(
        f"/api/v1/comments/{media.id}",
        headers={"Authorization": f"Bearer {test_user.token}"}
    )
    assert get_response.status_code == 200
    comments = get_response.json()
    assert len(comments) == 1
    assert comments[0]["id"] == response_data["id"]
    assert comments[0]["text"] == comment_payload["text"]
