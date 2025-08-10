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
    def filter(cls, session, **kwargs):
        """
        Filter Media instances based on provided parameters.
    
        Parameters:
        - session: SQLAlchemy session object
        - kwargs: filter criteria
    
        Returns:
        - List of Media instances matching the criteria
        """
        query = session.query(cls)
        for key, value in kwargs.items():
            if hasattr(cls, key):
                query = query.filter(getattr(cls, key) == value)
        return query.all()
    
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
