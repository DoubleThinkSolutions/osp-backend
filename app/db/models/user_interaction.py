from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Float, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..base import Base

class UserInteraction(Base):
    __tablename__ = 'user_interactions'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    target_user_id = Column(Integer, ForeignKey('users.id'))
    claim_id = Column(Integer, ForeignKey('claims.id'))
    verification_id = Column(Integer, ForeignKey('verifications.id'))
    interaction_type = Column(String(50), nullable=False)  # vote, comment, share, follow, etc.
    value = Column(Float)  # +1 for upvote, -1 for downvote, etc.
    content = Column(Text)  # comment text, etc.
    metadata_ = Column("metadata", JSON)  # additional data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
    claim = relationship("Claim")
    verification = relationship("Verification")
