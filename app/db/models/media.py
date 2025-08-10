from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.base import Base

class Media(Base):
    __tablename__ = 'media'

    id = Column(String, primary_key=True)
    title = Column(String)
    description = Column(String)
    user_id = Column(String)
    created_at = Column(DateTime, default=func.now())

    @classmethod
    def filter(cls, session, lat=None, lng=None, radius=None, start_date=None, end_date=None):
        """
        Filter Media instances based on geolocation (with radius in meters) and optional time range.
    
        Parameters:
        - session: SQLAlchemy session object
        - lat (float): Latitude of the center point
        - lng (float): Longitude of the center point
        - radius (float): Radius in meters
        - start_date (datetime): Start of the time range (optional)
        - end_date (datetime): End of the time range (optional)
    
        Returns:
        - SQLAlchemy query object for Media instances matching the criteria
        """
        from sqlalchemy import and_, text, Column
    
        query = session.query(cls)
    
        # Apply geofence filtering if all location parameters are provided
        if lat is not None and lng is not None and radius is not None:
            # Using raw SQL fragment for Haversine distance formula
            # Distance in meters
            haversine_expr = text("""
                6371000 * 2 * asin(sqrt(
                    power(sin(radians(:lat - lat) / 2), 2) +
                    cos(radians(:lat)) * cos(radians(lat)) *
                    power(sin(radians(:lng - lng) / 2), 2)
                ))
            """)
            query = query.filter(haversine_expr < radius).params(lat=lat, lng=lng)
    
        # Apply time range filtering
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

        try:
            session.delete(media)
            if file_path and not delete_file(file_path):
                raise ValueError("Failed to delete file from storage")
            session.commit()
        except Exception as e:
            session.rollback()
            raise ValueError(f"Failed to delete media: {str(e)}")

        return True
