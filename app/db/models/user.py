from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Float, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..base import Base

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(100))
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    profile_image = Column(String(255))
    bio = Column(Text)
    provider = Column(String(50), default='native')
    provider_id = Column(String(255))
    social_links = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    verifications = relationship("Verification", back_populates="user", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="user", cascade="all, delete-orphan")
