from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime


class CommentCreate(BaseModel):
    """
    Pydantic model for creating a new comment.

    This model is used to validate incoming comment creation requests.
    It ensures that the `text` field is a non-empty string.
    """

    text: str = Field(..., min_length=1, description="The content of the comment, must not be empty.")

    class Config:
        schema_extra = {
            "example": {
                "text": "This is a sample comment."
            }
        }


class CommentResponse(BaseModel):
    id: int
    media_id: str
    text: str
    user_id: str
    created_at: datetime

    class Config:
        orm_mode = True
