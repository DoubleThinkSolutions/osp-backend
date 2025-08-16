from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Float, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..base import Base

class Verification(Base):
    __tablename__ = 'verifications'

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey('claims.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    verification_text = Column(Text, nullable=False)
    context = Column(Text)
    evidence = Column(Text)
    confidence_score = Column(Float, default=0.0)
    tags = Column(JSON)
    is_verified = Column(Boolean, default=False)
    sources = Column(JSON)
    rating = Column(Integer)  # 1-5 star rating
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    claim = relationship("Claim", back_populates="verifications")
    user = relationship("User", back_populates="verifications")
