from datetime import datetime
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, Field, validator


class MediaCreateRequest(BaseModel):
    file: UploadFile = Field(..., description="The media file to upload")
    capture_time: datetime = Field(..., description="When the media was captured (timezone-aware)")
    lat: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    lng: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    orientation: int = Field(0, ge=0, le=359, description="Orientation in degrees (0-359)")

    @validator("capture_time")
    def check_timezone_aware(cls, v):
        if v and v.tzinfo is None:
            raise ValueError("capture_time must be timezone-aware")
        return v
