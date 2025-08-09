from datetime import datetime
from typing import Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DataError, SQLAlchemyError

from app.db.session import SessionLocal
from app.models.media import Media
from app.services.trust import calculate_trust_score

logger = logging.getLogger(__name__)

# Service-level exception for trust score update failures
class TrustScoreUpdateError(Exception):
    """Raised when trust score update fails due to business logic or data issues."""
    pass


def update_media_trust_score(db: Session, media_id: int, capture_time: datetime, upload_time: datetime) -> bool:
    """
    Update the trust score for a media record in the database.
    
    Args:
        db (Session): Database session
        media_id (int): ID of the media record
        capture_time (datetime): When the media was captured
        upload_time (datetime): When the media was uploaded
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Query the Media table to retrieve the media record
        media = db.query(Media).filter(Media.id == media_id).first()
        
        # If record does not exist, log error and exit gracefully
        if not media:
            logger.error(f"Media record not found for id: {media_id}")
            return False
            
        # Validate that capture_time and upload_time are not None
        if capture_time is None or upload_time is None:
            logger.warning(
                f"Missing timestamp(s) for media {media_id}: "
                f"capture_time={capture_time}, upload_time={upload_time}. Setting trust score to 0."
            )
            media.trust_score = 0
            db.commit()
            db.refresh(media)
            return True

        # Use the calculate_trust_score function to compute the score
        trust_score = calculate_trust_score(capture_time, upload_time)
        
        # Update the trust_score field
        media.trust_score = trust_score
        
        # Commit the transaction
        db.commit()
        db.refresh(media)
        
        logger.info(f"Successfully updated trust score for media {media_id}: {trust_score}")
        return True
        
    except IntegrityError as e:
        logger.error(f"IntegrityError when updating trust score for media {media_id}: {str(e)}", exc_info=True)
        db.rollback()
        return False
        
    except DataError as e:
        logger.error(f"DataError when updating trust score for media {media_id}: {str(e)}", exc_info=True)
        db.rollback()
        return False
        
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemyError when updating trust score for media {media_id}: {str(e)}", exc_info=True)
        db.rollback()
        return False
        
    except Exception as e:
        logger.critical(f"Unexpected error when updating trust score for media {media_id}: {str(e)}", exc_info=True)
        db.rollback()
        return False
