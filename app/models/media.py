from datetime import datetime
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, Field, validator, model_validator


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


class MediaFilterParams(BaseModel):
    lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Latitude coordinate for geofence center")
    lng: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Longitude coordinate for geofence center")
    radius: Optional[float] = Field(None, gt=0, description="Radius in meters for geofence")
    start_date: Optional[datetime] = Field(None, description="Start date and time in ISO 8601 format")
    end_date: Optional[datetime] = Field(None, description="End date and time in ISO 8601 format")

    @model_validator(mode='before')
    @classmethod
    def validate_location_fields(cls, values):
        lat, lng, radius = values.get("lat"), values.get("lng"), values.get("radius")
        if lat is not None:
            if lng is None:
                raise ValueError("lng must be provided when lat is specified")
            if radius is None:
                raise ValueError("radius must be provided when lat is specified")
        # Validate that lng is not provided without lat
        if lng is not None and lat is None:
            raise ValueError("lat must be provided when lng is specified")
        # Validate that radius is not provided without lat
        if radius is not None and lat is None:
            raise ValueError("lat must be provided when radius is specified")
        return values

class MediaMetadata(BaseModel):
    capture_time: datetime = Field(..., description="When the media was captured (timezone-aware)")
    lat: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    lng: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    orientation: int = Field(0, ge=0, le=359, description="Orientation in degrees (0-359)")

    @validator("capture_time", pre=True)
    def check_timezone_aware(cls, v):
        # Pydantic can automatically parse ISO 8601 strings to datetime objects
        # We just need to ensure it's a valid string. The timezone will be handled.
        if isinstance(v, str):
            # This will raise a ValueError if the format is wrong, which Pydantic handles
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v