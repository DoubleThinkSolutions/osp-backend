import cv2
import numpy as np
import tempfile

from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse, Response
from datetime import datetime, timezone
from typing import Optional
import logging
import os

from pydantic import ValidationError
import ffmpeg
from geoalchemy2.shape import to_shape
import uuid

from app.middleware.auth import get_current_user
from app.core.logging import logger
from app.models.media import MediaMetadata
from app.services.storage import save_file, delete_file
from app.db.models.media import Media
from app.schemas.media import MediaFilterParams, MediaListResponse, Media as MediaSchema
from app.db.session import SessionLocal, get_db, Session
from app.services.trust import calculate_trust_score
from app.core.config import settings
from app.services.verification import verify_signature

router = APIRouter()

def reencode_video_for_web_compatibility(video_data: bytes) -> bytes:
    """
    Re-encodes a video to a web-compatible MP4 format (H.264 video, AAC audio).

    This function takes raw video data, writes it to a temporary file,
    and then uses FFmpeg to process it. It corrects potential issues like
    unsupported audio codecs (e.g., AMR) and non-standard video settings.

    Args:
        video_data: The raw byte content of the video file.

    Returns:
        The raw byte content of the re-encoded video file.

    Raises:
        ffmpeg.Error: If the FFmpeg process fails.
        Exception: For other file I/O errors.
    """
    input_temp_file = None
    output_temp_file = None
    try:
        # Create a temporary file for the input video data
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_in:
            temp_in.write(video_data)
            input_temp_file = temp_in.name

        # Create a temporary file path for the output
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_out:
            output_temp_file = temp_out.name

        logger.info(f"Starting re-encoding from {input_temp_file} to {output_temp_file}")

        # Build and run the FFmpeg command
        (
            ffmpeg
            .input(input_temp_file)
            .output(
                output_temp_file,
                **{
                    'c:v': 'libx264',        # Video codec: H.264 (highly compatible)
                    'profile:v': 'main',     # H.264 profile for broad compatibility
                    'pix_fmt': 'yuv420p',    # Standard pixel format for web video
                    'c:a': 'aac',            # Audio codec: AAC (the web standard)
                    'movflags': '+faststart' # Optimize for web streaming
                }
            )
            .run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
        )
        
        logger.info("FFmpeg re-encoding successful.")

        # Read the re-encoded data from the output file
        with open(output_temp_file, 'rb') as f:
            reencoded_data = f.read()
        
        return reencoded_data

    except ffmpeg.Error as e:
        logger.error("FFmpeg re-encoding failed.")
        # The stderr from FFmpeg is very useful for debugging
        logger.error(f"FFmpeg stdout: {e.stdout.decode('utf8')}")
        logger.error(f"FFmpeg stderr: {e.stderr.decode('utf8')}")
        raise  # Re-raise the exception to be handled by the endpoint
    finally:
        # --- Crucial Cleanup Step ---
        # Ensure temporary files are deleted regardless of success or failure
        if input_temp_file and os.path.exists(input_temp_file):
            os.unlink(input_temp_file)
            logger.debug(f"Cleaned up temp input file: {input_temp_file}")
        if output_temp_file and os.path.exists(output_temp_file):
            os.unlink(output_temp_file)
            logger.debug(f"Cleaned up temp output file: {output_temp_file}")

def generate_video_thumbnail(video_data: bytes, max_width: int = 640) -> Optional[bytes]:
    """
    Generates a JPEG thumbnail from the first frame of a video, preserving its
    correct orientation and aspect ratio.

    This function is rotation-aware, using ffprobe to detect rotation metadata
    from mobile devices. It then rotates the frame and resizes it proportionally
    without cropping, ensuring the thumbnail matches the video's intended view.
    """
    temp_video_path = None
    cap = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video_file:
            temp_video_file.write(video_data)
            temp_video_path = temp_video_file.name

        rotation = 0
        try:
            probe = ffmpeg.probe(temp_video_path)
            video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            
            if video_stream and 'side_data_list' in video_stream:
                for side_data in video_stream['side_data_list']:
                    if side_data.get('side_data_type') == 'Display Matrix':
                        if 'rotation' in side_data:
                            rotation = int(side_data['rotation'])
                            logger.info(f"Found rotation '{rotation}' in Display Matrix.")
                            break
            
            if rotation == 0 and video_stream and 'tags' in video_stream:
                if 'rotate' in video_stream['tags']:
                    rotation = int(video_stream['tags']['rotate'])
                    logger.info(f"Found rotation '{rotation}' in stream tags (fallback).")
        except Exception as e:
            logger.warning(f"Could not determine video rotation. Error: {e}")

        cap = cv2.VideoCapture(temp_video_path)
        if not cap.isOpened():
            logger.error("Could not open video file for thumbnail generation.")
            return None

        success, frame = cap.read()
        if not success:
            logger.error("Could not read frame from video for thumbnail generation.")
            return None

        # --- Apply detected rotation ---
        if rotation == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif rotation == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif rotation == 270 or rotation == -90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

        h, w, _ = frame.shape
        aspect_ratio = h / w
        new_height = int(max_width * aspect_ratio)

        resized_frame = cv2.resize(frame, (max_width, new_height), interpolation=cv2.INTER_AREA)

        success, buffer = cv2.imencode('.jpg', resized_frame)
        if not success:
            logger.error("Failed to encode frame to JPEG for thumbnail.")
            return None
            
        return buffer.tobytes()

    except Exception as e:
        logger.error(f"Error during thumbnail generation: {e}", exc_info=True)
        return None
    finally:
        if cap is not None:
            cap.release()
        if temp_video_path and os.path.exists(temp_video_path):
            os.unlink(temp_video_path)

@router.post("/media")
async def create_media(
    file: UploadFile = File(..., description="The media file to upload"),
    metadata_str: str = Form(..., alias="metadata", description="A JSON string of the media metadata"),
    current_user = Depends(get_current_user),
    signature: bytes = Form(..., description="The DER-encoded ECDSA signature"),
    public_key: bytes = Form(..., description="The DER-encoded SPKI public key"),
    media_hash: str = Form(..., description="The client-calculated hex hash of the media file"),
    metadata_hash: str = Form(..., description="The client-calculated hex hash of the metadata"),
    attestation_chain_str: Optional[str] = Form(None, description="The attestation retrieved from the device"),
    db: Session = Depends(get_db)
):
    """
    Upload a new media file with metadata.
    """
    # Extract user_id from current_user
    logger.debug(current_user)
    user_id = current_user.get("userId")
    
    # Log the upload attempt
    logger.info(f"User {user_id} attempting signed media upload for {file.filename}")
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

    verification_result = await verify_signature(
        file=file,
        metadata_str=metadata_str,
        client_media_hash_hex=media_hash,
        client_metadata_hash_hex=metadata_hash,
        signature_bytes=signature,
        public_key_bytes=public_key,
        attestation_chain_str=attestation_chain_str
    )

    if not verification_result.is_valid:
        logger.warning(f"Verification failed for {file.filename}: {verification_result.status_message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Verification failed: {verification_result.status_message}")

    try:
        metadata = MediaMetadata.parse_raw(metadata_str)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid metadata format.")

    # Set upload time to current UTC time
    upload_time = datetime.now(timezone.utc)
    trust_score = calculate_trust_score(metadata.capture_time, upload_time)
    
    # Generate a unique filename
    base_uuid = uuid.uuid4()
    _, file_extension = os.path.splitext(file.filename)
    unique_filename = f"{base_uuid}{file_extension}"

    thumbnail_key = None

    try:
        # Read file data
        file_data = await file.read()

        if file.content_type == "video/mp4":

            try:
                logger.info(f"Re-encoding video {unique_filename} for web compatibility...")
                reencoded_file_data = reencode_video_for_web_compatibility(file_data)
                
                # If encoding is successful, replace the original file data
                file_data = reencoded_file_data
                logger.info("Video successfully re-encoded. New size: {len(file_data)} bytes.")

            except Exception as e:
                # If encoding fails, we should not proceed with the potentially broken file.
                logger.error(f"Critical error during video re-encoding for {unique_filename}: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                    detail="Failed to process video file. It may be corrupted or in an unsupported format."
                )

            logger.info(f"Generating thumbnail for video {unique_filename}...")
            thumbnail_data = generate_video_thumbnail(file_data)
            if thumbnail_data:
                thumbnail_filename = f"{base_uuid}_thumb.jpg"
                save_file(thumbnail_data, thumbnail_filename, "image/jpeg")
                thumbnail_key = f"{settings.S3_BUCKET_NAME}/{thumbnail_filename}"
                logger.info(f"Thumbnail saved with key: {thumbnail_key}")
            else:
                logger.warning("Failed to generate thumbnail, proceeding without one.")

        # Save the main file to S3
        object_key = f"{settings.S3_BUCKET_NAME}/{unique_filename}"
        save_file(file_data, unique_filename, file.content_type)
        logger.info(f"File saved with key: {object_key}")
        
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
            orientation_azimuth=metadata.orientation.azimuth,
            orientation_pitch=metadata.orientation.pitch,
            orientation_roll=metadata.orientation.roll,
            trust_score=trust_score,
            user_id=user_id,
            file_path=object_key,
            thumbnail_path=thumbnail_key,
            verification_status=verification_result.status_message,
            signature=signature,
            public_key=public_key,
            client_media_hash=media_hash,
            client_metadata_hash=metadata_hash
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
            "orientation": {
                "azimuth": media.orientation_azimuth,
                "pitch": media.orientation_pitch,
                "roll": media.orientation_roll
            },
            "trust_score": media.trust_score,
            "user_id": media.user_id,
            "file_path": media.file_path,
            "verification_status": media.verification_status,
            "thumbnail_path": media.thumbnail_path
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

@router.get("/media", response_model=MediaListResponse)
async def get_media(
    filters: MediaFilterParams = Depends(),
    db: Session = Depends(get_db)
):
    """
    Retrieve media items with filtering by geolocation and optional time range.
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

        serialized_media = []
        for media_item in media_list:
            # Convert the location point to get lat/lng
            location_point = to_shape(media_item.location)
            
            media_data = media_item.__dict__
            
            media_data['lat'] = location_point.y
            media_data['lng'] = location_point.x
            
            media_schema = MediaSchema.model_validate(media_data)
            
            serialized_media.append(media_schema)
        
        return MediaListResponse(
            count=len(serialized_media),
            media=serialized_media
        )
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
    user_id = current_user.get("userId")
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
        if media.user_id != user_id: # and not user_is_admin(): # Add admin check if needed
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        
        # Proceed with deletion after permission check (handled at endpoint level)
        Media.delete(session=db, media_id=media_id)
        
        logger.info(f"Successfully deleted media {media_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except ValueError as e:
        # Catch specific errors from the delete method for better responses
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error while deleting media {media_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete media")
    finally:
        db.close()
