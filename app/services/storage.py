import os
import uuid
from typing import Union
import logging

# Create logger instance
logger = logging.getLogger("app.storage")

# Constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "video/mp4": ".mp4"
}
STORAGE_DIR = "storage"

def delete_file(filename: str) -> bool:
    """
    Delete a file from the storage directory.
    
    Args:
        filename: The name of the file to delete
        
    Returns:
        True if file was successfully deleted or didn't exist, False if deletion failed
    """
    try:
        # Construct full file path
        file_path = os.path.join(STORAGE_DIR, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.warning(f"Attempted to delete non-existent file: {filename}")
            return True  # Idempotent behavior - return True if file doesn't exist
            
        # Attempt to delete the file
        os.remove(file_path)
        logger.info(f"Successfully deleted file: {filename}")
        return True
        
    except OSError as e:
        logger.error(f"Failed to delete file {filename}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while deleting file {filename}: {str(e)}")
        return False

def save_file(file_data: bytes, content_type: str, file_size: int) -> str:
    """
    Save a file to the storage directory with a UUID v4 filename.
    
    Args:
        file_data: The raw bytes of the file to save
        content_type: The MIME type of the file (e.g., "image/jpeg", "video/mp4")
        file_size: The size of the file in bytes
        
    Returns:
        The generated filename (including extension)
        
    Raises:
        ValueError: If the content type is not allowed or file size exceeds limit
        OSError: If there's an error writing the file to disk
        Exception: For any other unexpected errors
    """
    # Validate content type
    if content_type not in ALLOWED_CONTENT_TYPES:
        error_msg = f"Unsupported content type: {content_type}. Allowed types: {list(ALLOWED_CONTENT_TYPES.keys())}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate file size
    if file_size > MAX_FILE_SIZE:
        error_msg = f"File size {file_size} bytes exceeds maximum limit of {MAX_FILE_SIZE} bytes"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        # Generate UUID v4 filename
        file_uuid = str(uuid.uuid4())
        file_extension = ALLOWED_CONTENT_TYPES[content_type]
        filename = f"{file_uuid}{file_extension}"
        
        # Ensure storage directory exists
        os.makedirs(STORAGE_DIR, exist_ok=True)
        
        # Construct file path
        file_path = os.path.join(STORAGE_DIR, filename)
        
        # Write file data to disk
        with open(file_path, "wb") as f:
            f.write(file_data)
        
        # Log successful save
        logger.info(f"Successfully saved file: {filename} ({file_size} bytes, type: {content_type})")
        
        return filename
        
    except OSError as e:
        error_msg = f"Failed to write file to disk: {str(e)}"
        logger.error(error_msg)
        raise OSError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error while saving file: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg) from e
