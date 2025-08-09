import time
import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from jose import jwt
from jose.exceptions import JWTError
import logging

logger = logging.getLogger(__name__)

# Get secret key from environment or generate a default (not for production)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(
    user_id: str,
    provider: str,
    roles: Optional[list] = None,
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60
) -> str:
    """
    Create a signed JWT access token with user information.
    
    Args:
        user_id: The user's unique identifier in the system
        provider: Authentication provider (e.g., 'apple', 'google')
        roles: List of user roles (e.g., ['user'], ['admin', 'user'])
        expires_in: Token expiration duration in seconds (default: 15 minutes)
        
    Returns:
        Encoded JWT token as a string
    """
    if roles is None:
        roles = ["user"]
        
    # Set token expiration (based on expires_in seconds)
    expire = datetime.utcnow() + timedelta(seconds=expires_in)
    
    # Create the token payload with required claims
    to_encode = {
        "userId": user_id,
        "provider": provider,
        "roles": roles,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(f"Successfully created access token for user {user_id}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create access token: {str(e)}")
        raise

def create_refresh_token(
    user_id: str,
    provider: str,
    roles: Optional[list] = None,
    expires_in: int = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
) -> str:
    """
    Create a signed JWT refresh token with user information.
    
    Args:
        user_id: The user's unique identifier in the system
        provider: Authentication provider (e.g., 'apple', 'google')
        roles: List of user roles
        expires_in: Token expiration duration in seconds (default: 7 days)
        
    Returns:
        Encoded JWT token as a string
    """
    if roles is None:
        roles = ["user"]
        
    # Set token expiration (based on expires_in seconds)
    expire = datetime.utcnow() + timedelta(seconds=expires_in)
    
    # Create the token payload with required claims
    to_encode = {
        "userId": user_id,
        "provider": provider,
        "roles": roles,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    
    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.info(f"Successfully created refresh token for user {user_id}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create refresh token: {str(e)}")
        raise

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT token.
    
    Args:
        token: The JWT token to decode
        
    Returns:
        Dictionary with token claims if valid, None if invalid
    """
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"Successfully decoded token for user {decoded_token.get('userId')}")
        return decoded_token
    except JWTError as e:
        logger.warning(f"Token decoding failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during token decoding: {str(e)}")
        return None
