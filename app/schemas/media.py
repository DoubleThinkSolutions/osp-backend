from datetime import datetime
from pydantic import BaseModel, Field, validator, ConfigDict, computed_field
from typing import Optional
from app.core.config import settings

class MediaFilterParams(BaseModel):
    lat: float
    lng: float
    radius: float
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    @validator('lat')
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90 degrees.')
        return v

    @validator('lng')
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180 degrees.')
        return v

    @validator('radius')
    def validate_radius(cls, v):
        if v <= 0:
            raise ValueError('Radius must be greater than 0.')
        return v

    @validator('end_date', always=True)
    def validate_date_range(cls, v, values):
        start_date = values.get('start_date')
        if start_date and v and start_date >= v:
            raise ValueError('start_date must be before end_date.')
        return v

class OrientationVector(BaseModel):
    azimuth: float
    pitch: float
    roll: float

# This schema represents the data coming from the SQLAlchemy model
class Media(BaseModel):
    id: str
    user_id: str
    capture_time: datetime
    file_path: str 
    thumbnail_path: Optional[str] = None
    trust_score: float
    lat: float
    lng: float
    verification_status: str

    orientation_azimuth: float = Field(exclude=True)
    orientation_pitch: float = Field(exclude=True)
    orientation_roll: float = Field(exclude=True)

    @computed_field
    @property
    def orientation(self) -> OrientationVector:
        """
        Dynamically constructs the orientation vector object.
        """
        return OrientationVector(
            azimuth=self.orientation_azimuth,
            pitch=self.orientation_pitch,
            roll=self.orientation_roll
        )

    @computed_field
    @property
    def image_url(self) -> str:
        """
        Dynamically constructs the full public URL for the media file.
        """
        return f"{settings.S3_PUBLIC_BASE_URL}/{self.file_path}"

    @computed_field
    @property
    def thumbnail_url(self) -> Optional[str]:
        """
        Dynamically constructs the full public URL for the thumbnail, if it exists.
        """
        if not self.thumbnail_path:
            return None
        
        return f"{settings.S3_PUBLIC_BASE_URL}/{self.thumbnail_path}"

    # This tells Pydantic to read data from SQLAlchemy model attributes
    model_config = ConfigDict(from_attributes=True)

class MediaListResponse(BaseModel):
    count: int
    media: list[Media]
