# app/services/storage.py
import os
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger("app.storage")

# Get config from environment variables
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL") # This is None in production

# --- Conditionally configure the S3 client ---
s3_client_config = {
    'region_name': AWS_REGION
}
# If an endpoint_url is provided (i.e., for MinIO in dev), add it to the config
if S3_ENDPOINT_URL:
    s3_client_config['endpoint_url'] = S3_ENDPOINT_URL

# Initialize the S3 client with our flexible configuration
s3_client = boto3.client("s3", **s3_client_config)


def save_file(file_data: bytes, filename: str, content_type: str) -> str:
    """
    Save a file to the configured S3-compatible storage (AWS S3 or MinIO).
    
    Returns:
        The public URL of the saved file.
    """
    if not S3_BUCKET_NAME:
        logger.error("S3_BUCKET_NAME environment variable is not set.")
        raise ValueError("Storage service is not configured.")

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=filename,
            Body=file_data,
            ContentType=content_type
        )
        
        # --- Construct the correct URL based on environment ---
        if S3_ENDPOINT_URL:
            # For MinIO, the URL is http://localhost:9000/bucket-name/filename
            # We use localhost here because this URL will be accessed by the user's browser, not the backend container.
            file_url = f"http://localhost:9000/{S3_BUCKET_NAME}/{filename}"
        else:
            # For AWS S3, use the standard AWS URL format
            file_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"
        
        logger.info(f"Successfully saved file to S3-compatible storage: {file_url}")
        return file_url

    except ClientError as e:
        logger.error(f"Failed to upload file: {e}")
        raise Exception("Failed to save file to storage.") from e


def delete_file(filename: str) -> bool:
    """
    Delete a file from the S3-compatible storage.
    """
    if not S3_BUCKET_NAME:
        logger.error("S3_BUCKET_NAME environment variable is not set.")
        return False
        
    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=filename)
        logger.info(f"Successfully deleted file: {filename}")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete file {filename}: {e}")
        return False
