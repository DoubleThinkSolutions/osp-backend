from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
import logging

from app.models.comment import CommentCreate, CommentResponse
from app.db.models.comment import Comment
from app.middleware.auth import get_current_user
from app.db.session import get_db
from sqlalchemy.orm import Session

router = APIRouter()

# Use the standard logger
logger = logging.getLogger(__name__)

@router.get("/comments/{media_id}", response_model=List[CommentResponse])
def get_comments(
    media_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve all comments for a specific media item.
    
    Args:
        media_id: The ID of the media to retrieve comments for
        db: Database session
        current_user: Authenticated user context from JWT
        
    Returns:
        List of comments associated with the media item
        
    Raises:
        HTTPException: 500 if there's a database error
    """
    logger.info(f"User {current_user['userId']} retrieving comments for media {media_id}")
    
    try:
        comments = Comment.filter(db, media_id=media_id)
        logger.info(f"Found {len(comments)} comments for media {media_id}")
        return comments
    except Exception as e:
        logger.error(f"Database error while retrieving comments for media {media_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "COMMENT_RETRIEVAL_FAILED", "message": "Failed to retrieve comments"}
        )


@router.post("/comments/{media_id}", status_code=status.HTTP_201_CREATED)
def create_comment(
    media_id: str,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new comment for a specific media item.
    
    Args:
        media_id: The ID of the media to comment on
        comment_data: The comment content from request body
        db: Database session
        current_user: Authenticated user context from JWT
        
    Returns:
        Dict with comment details and success message
        
    Raises:
        HTTPException: 404 if media_id doesn't exist
                    500 if there's a server error
    """
    logger.info(f"User {current_user['userId']} attempting to comment on media {media_id}")
    
    # For now, validate media_id is not empty
    if not media_id or media_id.strip() == "":
        logger.warning(f"Invalid media_id provided: '{media_id}'")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_MEDIA_ID", "message": "Media ID cannot be empty"}
        )
        
    # Check if media exists in database
    from app.db.models.media import Media
    media = db.query(Media).filter(Media.id == media_id).first()
    if not media:
        logger.warning(f"Media not found for media_id: {media_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "MEDIA_NOT_FOUND", "message": f"Media with id {media_id} not found"}
        )
        
    try:
        # Create the comment in database
        comment = Comment.create(
            session=db,
            media_id=media_id,
            text=comment_data.text,
            user_id=current_user['userId']
        )
        
        logger.info(f"Successfully created comment {comment.id} for media {media_id} by user {current_user['userId']}")
        
        return {
            "id": comment.id,
            "media_id": comment.media_id,
            "text": comment.text,
            "user_id": comment.user_id,
            "created_at": comment.created_at
        }
        
    except Exception as e:
        logger.error(f"Failed to create comment for media {media_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "COMMENT_CREATION_FAILED", "message": "Failed to create comment"}
        )
