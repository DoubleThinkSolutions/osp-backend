from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Float, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base
import enum

class MediaType(enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
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

class Media(Base):
    __tablename__ = 'media'

    id = Column(Integer, primary_key=True, index=True)
    capture_time = Column(DateTime(timezone=True), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    orientation = Column(Float, nullable=False)
    trust_score = Column(Float, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_media_location', 'lat', 'lng', postgresql_using='gin'),
        Index('idx_media_capture_time', 'capture_time', postgresql_using='btree'),
    )

    # Relationships
    user = relationship("User")

class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    claim_id = Column(Integer, ForeignKey('claims.id'))
    verification_id = Column(Integer, ForeignKey('verifications.id'))
    media_id = Column(Integer, ForeignKey('media.id'))
    parent_id = Column(Integer, ForeignKey('comments.id'))  # For nested/reply comments
    is_edited = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")
    claim = relationship("Claim")
    verification = relationship("Verification")
    replies = relationship("Comment", backref="parent", cascade="all, delete-orphan", remote_side=[id])
