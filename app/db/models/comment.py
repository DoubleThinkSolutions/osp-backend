from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base

class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True)
    media_id = Column(String, index=True)
    text = Column(Text)
    user_id = Column(String)
    created_at = Column(DateTime, default=func.now())

    @classmethod
    def create(cls, session, **kwargs):
        """
        Create and save a new Comment instance.

        Parameters:
        - session: SQLAlchemy session object
        - kwargs: keyword arguments for Comment fields

        Returns:
        - Saved Comment instance
        """
        comment = cls(**kwargs)
        session.add(comment)
        session.commit()
        session.refresh(comment)
        return comment

    @classmethod
    def filter(cls, session, **kwargs):
        """
        Filter Comment instances based on provided parameters.

        Parameters:
        - session: SQLAlchemy session object
        - kwargs: filter criteria

        Returns:
        - List of Comment instances matching the criteria
        """
        query = session.query(cls)
        for key, value in kwargs.items():
            if hasattr(cls, key):
                query = query.filter(getattr(cls, key) == value)
        return query.all()
