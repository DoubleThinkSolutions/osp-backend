from datetime import datetime
from pydantic import BaseModel, validator

class MediaFilterParams(BaseModel):
    lat: float
    lng: float
    radius: float
    start_date: datetime = None
    end_date: datetime = None

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
