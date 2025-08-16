from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Float, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..base import Base

class Claim(Base):
    __tablename__ = 'claims'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String(50))  # news, social_media, video, etc.
    claim_source = Column(String(255))  # URL or source reference
    claim_date = Column(DateTime(timezone=True))
    verified_status = Column(String(20), default='pending')  # pending, verified, debunked
    confidence_score = Column(Float, default=0.0)
    summary = Column(Text)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="claims")
    verifications = relationship("Verification", back_populates="claim", cascade="all, delete-orphan")
