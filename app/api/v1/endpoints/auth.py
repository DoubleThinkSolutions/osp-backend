from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated
import logging
from app.services.auth.apple_auth import verify_apple_id_token
from app.services.auth.google_auth import GoogleAuth
from app.models.auth import SignInRequest, SignInResponse
from app.services.user_service import UserService
from app.security.jwt import create_access_token, create_refresh_token, decode_token, verify_refresh_token
from app.db.session import get_db
from sqlalchemy.orm import Session
import json
from fastapi import Depends, HTTPException, Response, status, APIRouter
from app.db.models import User
from app.db.session import get_db
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Dict

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/refresh-token", response_model=Dict[str, str])
async def refresh_token(
    refresh_token_body: Dict[str, str],
    db: Session = Depends(get_db)
):
    """
    Refresh an access token using a valid refresh token.

    Args:
        refresh_token_body: Dictionary containing the refresh token
        db: Database session

    Returns:
        Dictionary containing the new access token

    Raises:
        HTTPException: 403 for invalid or expired refresh tokens
    """
    refresh_token_str = refresh_token_body.get("refreshToken")
    if not refresh_token_str:
        logger.warning("Refresh token missing from request body")
        raise HTTPException(
            status_code=403,
            detail={"error": "REFRESH_TOKEN_INVALID"}
        )

    # Verify the refresh token
    try:
        token_payload = verify_refresh_token(refresh_token_str)
        if not token_payload:
            logger.warning("Invalid or expired refresh token provided")
            raise HTTPException(
                status_code=403,
                detail={"error": "REFRESH_TOKEN_INVALID"}
            )
        
        user_id = token_payload.get("userId")
        provider = token_payload.get("provider")
        roles = token_payload.get("roles", ["user"])
        
        logger.info(f'Refresh token request received for user: {user_id}')
        
        # Check if user still exists and is active
        user_service = UserService(db)
        user = user_service.find_user_by_provider_id(provider, user_id)
        user_service.close()

        if not user or not user.is_active:
            logger.warning(f"User not found or account inactive for refresh token request: {user_id}")
            raise HTTPException(
                status_code=403,
                detail={"error": "REFRESH_TOKEN_INVALID"}
            )
        
        # Generate new access token
        new_access_token = create_access_token(
            user_id=user_id,
            provider=provider,
            roles=roles,
            expires_in=900  # 15 minutes
        )
        
        logger.info(f"Access token refreshed for user: {user_id}")
        
        return {"accessToken": new_access_token}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during token refresh"
        )

@router.post("/signin", response_model=SignInResponse)
async def signin(
    request: SignInRequest,
    db: Session = Depends(get_db)
):
    """
    Unified authentication endpoint for Apple and Google sign-in.

    Args:
        request: SignInRequest containing provider and token
        db: Database session

    Returns:
        SignInResponse containing JWT token

    Raises:
        HTTPException: 401 for invalid tokens
        HTTPException: 403 for account conflicts (ACCOUNT_EXISTS, DELETION_IN_PROGRESS)
        HTTPException: 500 for unexpected server errors
    """
    try:
        if request.provider == "apple":
            # Extract ID token for Apple verification
            id_token = request.token
            
            # Verify Apple ID token - this will raise HTTPException if invalid
            client_id = "com.osp.mobile"  # This should match your app's bundle ID
            claims = await verify_apple_id_token(id_token, client_id)
                
            # Extract user information from claims
            user_info = {
                'provider_id': claims['sub'],
                'email': claims.get('email'),
                'name': claims.get('name', '')
            }
        elif request.provider == "google":
            google_auth = GoogleAuth()
            user_info = google_auth.verify_token(request.token)
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid provider"
            )
        
        # Use UserService to find or create user
        user_service = UserService(db)
        
        # First, try to find existing user by provider_id
        user = user_service.find_user_by_provider_id(request.provider, user_info['provider_id'])
        
        # If user exists, check if account is in deletion state
        if user and not user.is_active:
            logger.warning(f"Account inactive for user {user.id} attempting sign-in")
            raise HTTPException(
                status_code=403,
                detail="DELETION_IN_PROGRESS"
            )
        else:
            # User doesn't exist, check if email is already associated with another account
            if user_info.get('email'):
                existing_user = user_service.find_user_by_email(user_info['email'])
                if existing_user:
                    # Check if this existing user is already being deleted
                    if not existing_user.is_active:
                        logger.warning(f"Account inactive for user {existing_user.id} with email {user_info['email']} during sign-in")
                        raise HTTPException(
                            status_code=403,
                            detail="DELETION_IN_PROGRESS"
                        )
                    # Otherwise, the email is already associated with another account
                    logger.warning(f"Sign-in attempt with existing email {user_info['email']} but different provider ID")
                    raise HTTPException(
                        status_code=403,
                        detail="ACCOUNT_EXISTS"
                    )
            
            # Create new user since no conflicts found
            # Generate username from email if available
            username = None
            if user_info.get('email'):
                username = user_info['email'].split('@')[0]
                
            user_data = {
                'provider': request.provider,
                'provider_id': user_info['provider_id'],
                'email': user_info.get('email'),
                'username': username,
                'full_name': user_info.get('name') or None
            }
            user = user_service.create_user(user_data)
        
        # Close the UserService session
        user_service.close()

        # Create JWT token using provider_id (external ID) instead of internal DB ID
        access_token = create_access_token(
            user_id=user_info['provider_id'],
            provider=request.provider,
            roles=["user"],
            expires_in=900  # 15 minutes in seconds
        )
        refresh_token = create_refresh_token(
            user_id=user_info['provider_id'],
            provider=request.provider,
            roles=["user"],
            expires_in=604800  # 7 days in seconds
        )
        
        logger.info(f"Successful {request.provider} sign-in for user {user.id}")
        return SignInResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    except HTTPException:
        # Re-raise HTTPExceptions that are already properly formed
        raise
    except Exception as e:
        logger.error(f"Unexpected error during sign-in: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during sign-in"
        )
