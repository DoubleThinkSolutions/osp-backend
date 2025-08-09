from typing import Dict, Any
import logging
from fastapi import Request, Depends, HTTPException, status, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security.jwt import decode_token
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

class JWTBearer(HTTPBearer):
    """
    Custom security scheme that validates JWT tokens.
    Used to extract and verify the Authorization header.
    """
    def __init__(self, auto_error: bool = True):
        super().__init__(bearerFormat="JWT", auto_error=auto_error)

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        try:
            credentials = await super().__call__(request)
            if credentials:
                if not credentials.scheme == "Bearer":
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"error": "INVALID_AUTH_SCHEME", "message": "Invalid authentication scheme."}
                    )
                # Validate token content directly
                token = credentials.credentials
                payload = decode_token(token)
                if not isinstance(payload, dict) or not payload.get("success", False):
                    error = payload.get("error", "INVALID_TOKEN") if isinstance(payload, dict) else "INVALID_TOKEN"
                    if error == "TOKEN_EXPIRED":
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail={"error": "TOKEN_EXPIRED", "message": "Token has expired"}
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail={"error": "INVALID_TOKEN", "message": "Invalid token"}
                        )
                return credentials
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": "INVALID_AUTH_HEADER", "message": "Invalid authorization code."}
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_AUTH_HEADER", "message": "Invalid authorization header"}
            )

    


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(JWTBearer())
) -> Dict[str, Any]:
    """
    Dependency that extracts and validates the JWT from the Authorization header,
    verifies it's an access token, checks user existence, and returns user context.

    Raises appropriate HTTP exceptions for various failure cases.
    Returns:
        Dictionary containing userId, provider, and roles
    """
    # Decode and verify the token
    try:
        payload = decode_token(credentials.credentials)
        if isinstance(payload, dict):
            if not payload.get("success"):
                error = payload.get("error")
                if error == "TOKEN_EXPIRED":
                    logger.warning('Token expired during authentication')
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"error": "TOKEN_EXPIRED", "message": "Token has expired"}
                    )
                else:  # INVALID_TOKEN
                    logger.warning('Invalid token during authentication')
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"error": "INVALID_TOKEN", "message": "Invalid authentication token"}
                    )
        else:
            logger.warning('Token decoding failed - invalid token format')
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_TOKEN", "message": "Invalid authentication token"}
            )

        # Check token type
        token_type = payload.get('type')
        if token_type != 'access':
            logger.warn(f'Invalid token type: {token_type}')
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_TOKEN", "message": "Invalid token type"}
            )

        user_id = payload.get('userId')
        if not user_id:
            logger.warn('Token missing userId claim')
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_TOKEN", "message": "Invalid token: missing user ID"}
            )

        # Verify user still exists in database
        with UserService() as user_service:
            try:
                user = user_service.find_user_by_provider_id(
                    provider=payload.get('provider'),
                    provider_id=user_id
                )
                if not user:
                    logger.warn(f'User not found for token userId: {user_id}')
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"error": "INVALID_TOKEN", "message": "User associated with token does not exist"}
                    )

                user_context = {
                    'userId': user_id,
                    'provider': payload.get('provider'),
                    'roles': payload.get('roles', ['user'])
                }
                
                logger.info(f'Successfully authenticated user {user_id}')
                return user_context
                
            except Exception as e:
                logger.error(f'Error verifying user existence: {str(e)}')
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": "INVALID_TOKEN", "message": "Failed to verify user credentials"}
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Unexpected error during token authentication: {str(e)}')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


# Alias for protected routes
login_required = Depends(get_current_user)
