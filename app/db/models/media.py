from sqlalchemy import Column, Integer, String, Float, DateTime, func, LargeBinary
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
    orientation_azimuth = Column(Float)
    orientation_pitch = Column(Float)
    orientation_roll = Column(Float)
    trust_score = Column(Float)
    file_path = Column(String)
    capture_time = Column(DateTime(timezone=True))

    verification_status = Column(String, nullable=False, default="UNVERIFIED")
    signature = Column(LargeBinary, nullable=True)
    public_key = Column(LargeBinary, nullable=True)
    client_media_hash = Column(String, nullable=True)
    client_metadata_hash = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)

    @classmethod
    def create(cls, db, capture_time, lat, lng, orientation_azimuth, orientation_pitch, orientation_roll,
               trust_score, user_id, file_path, verification_status, signature, public_key,
               client_media_hash, client_metadata_hash, thumbnail_path=None):
        media_id = str(uuid.uuid4())
        location_point = f'SRID=4326;POINT({lng} {lat})'
        
        media = cls(
            id=media_id,
            capture_time=capture_time,
            location=location_point,
            orientation_azimuth=orientation_azimuth,
            orientation_pitch=orientation_pitch,
            orientation_roll=orientation_roll,
            trust_score=trust_score,
            user_id=user_id,
            file_path=file_path,
            thumbnail_path=thumbnail_path,
            verification_status=verification_status,
            signature=signature,
            public_key=public_key,
            client_media_hash=client_media_hash,
            client_metadata_hash=client_metadata_hash
        )
        
        try:
            db.add(media)
            db.commit()
            db.refresh(media)
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
        Deletes a media record and its associated file(s) from storage.
        """
        from app.services.storage import delete_file

        media = session.query(cls).filter(cls.id == media_id).first()
        if not media:
            raise ValueError("Media not found")

        # Get paths before deleting the record
        file_path_to_delete = media.file_path
        thumbnail_path_to_delete = media.thumbnail_path
        
        try:
            # Delete from database first within the transaction
            session.delete(media)
            
            # Delete main file from storage
            if file_path_to_delete:
                filename = file_path_to_delete.split('/')[-1]
                if not delete_file(filename):
                    # Raise error to trigger a rollback
                    raise ValueError(f"Failed to delete main file {filename} from storage.")

            # Delete thumbnail from storage if it exists
            if thumbnail_path_to_delete:
                thumb_filename = thumbnail_path_to_delete.split('/')[-1]
                if not delete_file(thumb_filename):
                    # Raise error to trigger a rollback
                    raise ValueError(f"Failed to delete thumbnail {thumb_filename} from storage.")
            
            # If all deletions succeed, commit the transaction
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete media {media_id} due to: {str(e)}")
            raise e # Re-raise the exception to be handled by the endpoint

        return True
