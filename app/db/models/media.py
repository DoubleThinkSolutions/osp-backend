from sqlalchemy import Column, Integer, String, Float, DateTime, func, and_, text
from datetime import datetime, timezone
from geoalchemy2 import Geography
import uuid
from ..base import Base
from app.core.logging import logger

class Media(Base):
    __tablename__ = 'media'

    id = Column(String, primary_key=True)
    title = Column(String)
    description = Column(String)
    user_id = Column(String)
    created_at = Column(DateTime(timezone=True), default=func.now())
    location = Column(Geography(geometry_type='POINT', srid=4326))
    orientation = Column(Float)
    trust_score = Column(Float)
    file_path = Column(String)
    capture_time = Column(DateTime(timezone=True))

    @classmethod
    def create(cls, db, capture_time, lat, lng, orientation, trust_score, user_id, file_path):
        """
        Create a new Media record in the database.
        
        Parameters:
        - db: SQLAlchemy session object
        - capture_time: DateTime when the media was captured
        - lat: Latitude coordinate
        - lng: Longitude coordinate
        - orientation: Media orientation
        - trust_score: Calculated trust score
        - user_id: ID of the user uploading the media
        - file_path: Path where the file is stored
        
        Returns:
        - Media: The created Media instance
        
        Raises:
        - Exception: If creation fails
        """
        # Generate UUID for the media ID
        media_id = str(uuid.uuid4())

        # PostGIS point in WKT format: longitude first, then latitude
        location_point = f'SRID=4326;POINT({lng} {lat})'
        
        # Create new Media instance
        media = cls(
            id=media_id,
            capture_time=capture_time,
            location=location_point,
            orientation=orientation,
            trust_score=trust_score,
            user_id=user_id,
            file_path=file_path
        )
        
        # Add to session and commit
        try:
            db.add(media)
            db.commit()
            db.refresh(media)  # Refresh to get any database-generated values
            return media
        except Exception as e:
            db.rollback()
            raise e

    @classmethod
    def filter(cls, session, lat=None, lng=None, radius=None, start_date=None, end_date=None):
        """
        Filter Media instances based on geolocation (with radius in meters) and optional time range.
        """
        logger.info(
            f"Filtering with: lat={lat}, lng={lng}, radius={radius}, "
            f"start_date={start_date}, end_date={end_date}"
        )

        query = session.query(cls)
    
        # Apply geofence filtering if all location parameters are provided
        if lat is not None and lng is not None and radius is not None:
            # Create a point from the input lat/lng
            point = f'POINT({lng} {lat})' 
            # Use the efficient ST_DWithin function which uses the index
            query = query.filter(func.ST_DWithin(cls.location, point, radius))
    
        # Apply time range filtering
        # Your model has `capture_time`, not `created_at` for this field. Use the correct one.
        # If the column is actually `created_at`, change `cls.capture_time` to `cls.created_at`.
        if start_date is not None:
            query = query.filter(cls.capture_time >= start_date)
        if end_date is not None:
            query = query.filter(cls.capture_time <= end_date)
    
        return query
    

    @classmethod
    def delete(cls, session, media_id: str) -> bool:
        """
        Delete a media record and its associated file.
        
        Parameters:
        - session: SQLAlchemy session object
        - media_id: ID of the media to delete
        
        Returns:
        - True if deletion was successful
        
        Raises:
        - ValueError if media not found or storage deletion fails
        """
        from app.services.storage import delete_file

        media = session.query(cls).filter(cls.id == media_id).first()
        if not media:
            raise ValueError("Media not found")

        file_path = media.file_path
        if file_path:
            # Assuming file_path is a full URL like https://.../filename.jpg
            filename = file_path.split('/')[-1]
            if not delete_file(filename):
                raise ValueError("Failed to delete file from storage")

        try:
            session.delete(media)
            if file_path and not delete_file(file_path):
                raise ValueError("Failed to delete file from storage")
            session.commit()
        except Exception as e:
            session.rollback()
            raise ValueError(f"Failed to delete media: {str(e)}")

        return True
