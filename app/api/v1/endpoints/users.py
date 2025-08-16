import logging

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.middleware.auth import get_current_user
from app.services.user_service import UserService
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

@router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    # Use the login_required dependency.
    # It will automatically handle token validation and user lookup.
    # If the token is invalid or the user doesn't exist, it will raise a 401 error.
    # If successful, 'current_user' will be a dict like: {'userId': ..., 'provider': ..., 'roles': ...}
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Soft delete the currently authenticated user's account by deactivating it.
    This endpoint is protected and requires a valid JWT.
    """
    try:
        # The user is already authenticated by the 'login_required' dependency.
        # We can safely get the user's details from the 'current_user' dictionary.
        provider_id = current_user.get("userId")
        provider = current_user.get("provider")

        # The dependency already confirmed the user exists, but we fetch the
        # full User model object to perform the deletion.
        user_service = UserService(db)
        user = user_service.find_user_by_provider_id(provider, provider_id)
        
        # This check is good practice, though login_required should prevent this.
        if not user:
            logger.warning(f"User from valid token not found in DB: provider={provider}, id={provider_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found"
            )
        
        # Check if user is already inactive
        if not user.is_active:
            logger.info(f"User account {user.id} is already deactivated.")
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        
        # Attempt to deactivate the account using the internal database ID
        user_service.delete_user(user.id)
        user_service.close()
        
        logger.info(f"Successfully deactivated account: {user.id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logger.exception("Unexpected error during account deletion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your request"
        )
