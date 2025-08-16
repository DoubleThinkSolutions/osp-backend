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

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials:
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
    """
    try:
        decoded_data = decode_token(credentials.credentials)
        
        if not decoded_data.get("success"):
            error = decoded_data.get("error")
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

        payload = decoded_data.get("payload")
        if not payload:
             logger.warning('Token decoding succeeded but payload is missing')
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_TOKEN", "message": "Invalid token payload"}
            )

        token_type = payload.get('type')
        if token_type != 'access':
            logger.warning(f'Invalid token type provided: {token_type}') # Improved logging
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_TOKEN", "message": "Invalid token type, expected 'access'"}
            )

        user_id = payload.get('userId')
        if not user_id:
            logger.warning('Token missing userId claim')
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_TOKEN", "message": "Invalid token: missing user ID"}
            )

        # Verify user still exists in database
        with UserService() as user_service:
            user = user_service.find_user_by_provider_id(
                provider=payload.get('provider'),
                provider_id=user_id
            )
            if not user or not user.is_active:
                logger.warning(f'User not found or inactive for token userId: {user_id}')
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": "INVALID_TOKEN", "message": "User associated with token does not exist or is inactive"}
                )

            user_context = {
                'userId': user_id,
                'provider': payload.get('provider'),
                'roles': payload.get('roles', ['user'])
            }
            
            logger.info(f'Successfully authenticated user {user_id} for {credentials.scheme} request')
            return user_context

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Unexpected error during token authentication: {str(e)}')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed due to an unexpected error"
        )


# Alias for protected routes
login_required = Depends(get_current_user)
