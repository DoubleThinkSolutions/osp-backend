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
