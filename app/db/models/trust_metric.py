from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Float, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..base import Base

class TrustMetric(Base):
    __tablename__ = 'trust_metrics'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    claim_id = Column(Integer, ForeignKey('claims.id'))
    verification_id = Column(Integer, ForeignKey('verifications.id'))
    trust_score = Column(Float, default=0.0)
    metric_type = Column(String(50), nullable=False)  # user_trust, claim_credibility, verification_quality
    context = Column(String(100))  # political_bias, scientific_accuracy, etc.
    weight = Column(Float, default=1.0)
    explanation = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User")
    claim = relationship("Claim")
    verification = relationship("Verification")
