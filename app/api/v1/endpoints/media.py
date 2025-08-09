from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from typing import Optional
import logging
import os

from app.core.dependencies import get_current_user
from app.core.logging import logger
from app.models.media import MediaCreateRequest
from app.services.storage import save_file

router = APIRouter()

@router.post("/api/v1/media")
async def create_media(
    file: UploadFile = File(...),
    capture_time: datetime = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    orientation: int = Form(0),
    current_user = Depends(get_current_user)
):
    """
    Upload a new media file with metadata.
    """
    # Extract user_id from current_user
    user_id = current_user.id
    
    # Log the upload attempt
    logger.info(f"User {user_id} attempting media upload")
    
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
        capture_time=capture_time,
        lat=lat,
        lng=lng,
        orientation=orientation
    )
    
    # Set upload time to current UTC time
    upload_time = datetime.now(timezone.utc)
    
    # Calculate time difference in seconds
    time_difference = (upload_time - capture_time).total_seconds()
    
    # Calculate trust score using the formula: max(0, 100 - (difference_in_seconds / 60))
    trust_score = max(0, 100 - (time_difference / 60))
    
    # Ensure trust score is an integer between 0 and 100
    trust_score = int(trust_score)
    trust_score = max(0, min(100, trust_score))
    
    # Log the calculated trust score
    logger.info(f"Trust score calculated: {trust_score} for capture time {capture_time}")
    
    # Save file using storage service
    try:
        from app.services.storage import save_file
        
        # Read file data
        file.file.seek(0)
        file_data = await file.read()
        file.file.seek(0)  # Reset pointer after reading
    
        # Generate UUID v4 filename with original extension
        import uuid
        file_uuid = str(uuid.uuid4())
        _, file_extension = os.path.splitext(file.filename)
        if not file_extension:
            # Fallback to content type mapping if no extension
            content_type_extensions = {
                "image/jpeg": ".jpg",
                "video/mp4": ".mp4"
            }
            file_extension = content_type_extensions.get(file.content_type, "")
        uuid_filename = f"{file_uuid}{file_extension}"
    
        # Save the file
        saved_path = save_file(file_data, file.content_type, len(file_data))
        
        # Log success
        logger.info(f"File saved at {saved_path}")
        
    except Exception as e:
        logger.error(f"Failed to save file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file"
        )
    
    # Import Media model
    from app.db.models import Media
    from app.db.session import SessionLocal
    
    # Create database session
    db = SessionLocal()
    try:
        # Create media record in database
        media = Media.create(
            db=db,
            capture_time=capture_time,
            lat=lat,
            lng=lng,
            orientation=orientation,
            trust_score=trust_score,
            user_id=user_id,
            file_path=saved_path
        )
        # Log successful creation
        logger.info(f"Media record created with ID {media.id}")
        
        # Construct response data
        response_data = {
            "id": media.id,
            "capture_time": media.capture_time.isoformat(),
            "lat": media.lat,
            "lng": media.lng,
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
