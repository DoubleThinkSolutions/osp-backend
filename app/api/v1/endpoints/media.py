from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse, Response
from datetime import datetime, timezone
from typing import Optional
import logging
import os
from geoalchemy2.shape import to_shape
import uuid

from app.middleware.auth import get_current_user
from app.core.logging import logger
from src.schemas.media import MediaFilterParams
from app.models.media import MediaCreateRequest, MediaMetadata
from app.services.storage import save_file, delete_file
from app.db.models.media import Media
from app.db.session import SessionLocal, get_db, Session

router = APIRouter()

@router.post("/media")
async def create_media(
    file: UploadFile = File(..., description="The media file to upload"),
    metadata_str: str = Form(..., alias="metadata", description="A JSON string of the media metadata"),
    current_user = Depends(get_current_user)
):
    """
    Upload a new media file with metadata.
    """
    # Extract user_id from current_user
    logger.debug(current_user)
    user_id = current_user.get("userId")
    
    # Log the upload attempt
    logger.info(f"User {user_id} attempting media upload")
    try:
        metadata = MediaMetadata.parse_raw(metadata_str)
    except ValidationError as e:
        # If the JSON is malformed or missing fields, raise a 422
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors()
        )
    
    # Validate content type
    if file.content_type not in ["image/jpeg", "video/mp4"]:
        logger.error(f"Invalid file type: {file.content_type}")
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported media type. Only JPEG images and MP4 videos are allowed."
        )
    
    # Validate file size
    try:
        # Move to end of file to get size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        
        # Reset file pointer to beginning
        file.file.seek(0)
    
        max_size = 104_857_600  # 100MB
        if file_size > max_size:
            logger.error(f"File too large: {file_size} bytes")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large: {file_size} bytes. Maximum allowed is {max_size} bytes."
            )
    except Exception as e:
        logger.error(f"Error reading file size: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing file"
        )
    
    # Create request model instance for validation
    request = MediaCreateRequest(
        file=file,
        capture_time=metadata.capture_time,
        lat=metadata.lat,
        lng=metadata.lng,
        orientation=metadata.orientation
    )
    
    # Set upload time to current UTC time
    upload_time = datetime.now(timezone.utc)
    
    # Calculate time difference in seconds
    time_difference = (upload_time - metadata.capture_time).total_seconds()
    
    # Calculate trust score using the formula: max(0, 100 - (difference_in_seconds / 60))
    trust_score = max(0, 100 - (time_difference / 60))
    
    # Ensure trust score is an integer between 0 and 100
    trust_score = int(trust_score)
    trust_score = max(0, min(100, trust_score))
    
    # Log the calculated trust score
    logger.info(f"Trust score calculated: {trust_score} for capture time {metadata.capture_time}")
    
    # Generate a unique filename
    _, file_extension = os.path.splitext(file.filename)
    unique_filename = f"{uuid.uuid4()}{file_extension}"

    try:
        # Read file data
        file_data = await file.read()
    
        # Save the file to S3 and get the URL
        saved_url = save_file(file_data, unique_filename, file.content_type)
        
        logger.info(f"File saved at {saved_url}")
        
    except Exception as e:
        logger.error(f"Failed to save file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file"
        )
    
    # Create database session
    db = SessionLocal()
    try:
        # Create media record in database
        media = Media.create(
            db=db,
            capture_time=metadata.capture_time,
            lat=metadata.lat,
            lng=metadata.lng,
            orientation=metadata.orientation,
            trust_score=trust_score,
            user_id=user_id,
            file_path=saved_url
        )
        # Log successful creation
        logger.info(f"Media record created with ID {media.id}")
        
        location_point = to_shape(media.location)

        # Construct response data
        response_data = {
            "id": media.id,
            "capture_time": media.capture_time.isoformat(),
            "lat": location_point.y,
            "lng": location_point.x,
            "orientation": media.orientation,
            "trust_score": media.trust_score,
            "user_id": media.user_id,
            "file_path": media.file_path
        }
        
        # Log successful upload
        logger.info(f"Media upload succeeded: media_id={media.id}, user_id={user_id}")
        
        # Return 201 Created response
        return JSONResponse(
            content=response_data,
            status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.error(f"Failed to create media record: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save media metadata"
        )
    finally:
        db.close()

@router.get("/media")
async def get_media(
    filters: MediaFilterParams = Depends(), # This uses the Pydantic model
    db: Session = Depends(get_db)
):
    """
    Retrieve media items with filtering by geolocation (required) and optional time range.
    """
    logger.info(
        f"lat={filters.lat}, lng={filters.lng}, radius={filters.radius}, "
        f"start_date={filters.start_date}, end_date={filters.end_date}"
    )

    try:
        media_query = Media.filter(
            session=db,
            lat=filters.lat,
            lng=filters.lng,
            radius=filters.radius,
            start_date=filters.start_date,
            end_date=filters.end_date
        )
        
        media_list = media_query.all()
        logger.info(f"Successfully retrieved {len(media_list)} media records")

        response_media = []
        for media in media_list:
            # Convert the WKBElement from the DB back to a Shapely Point
            location_point = to_shape(media.location)
            response_media.append({
                "id": media.id,
                "capture_time": media.capture_time.isoformat(),
                "lat": location_point.y,
                "lng": location_point.x,
                "orientation": media.orientation,
                "trust_score": media.trust_score,
                "user_id": media.user_id,
                "file_path": media.file_path
            })

        return {
            "count": len(response_media),
            "media": response_media
        }
    except Exception as e:
        logger.error(f"Failed to retrieve media records: {e}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to retrieve media records")


@router.delete("/media/{media_id}")
async def delete_media(
    media_id: str,
    current_user = Depends(get_current_user)
):
    """
    Delete a media item by ID.
    Only the owner of the media item or an admin can delete it.
    """
    # Log the start of the deletion attempt
    logger.info(f"User {current_user.id} attempting to delete media {media_id}")
    
    db = SessionLocal()
    try:
        # Get the media record first to check ownership
        media = db.query(Media).filter(Media.id == media_id).first()
        if not media:
            logger.warning(f"Media {media_id} not found for deletion")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media not found"
            )
        
        # Check if the current user is the owner or an admin
        if media.user_id != current_user.id and not current_user.is_superuser:
            logger.warning(f"User {current_user.id} attempted to delete media {media_id} without permission")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this media"
            )
        
        # Proceed with deletion after permission check (handled at endpoint level)
        Media.delete(session=db, media_id=media_id)
        
        logger.info(f"Successfully deleted media {media_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except Exception as e:
        logger.error(f"Unexpected error while deleting media {media_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete media"
        )
    finally:
        db.close()
