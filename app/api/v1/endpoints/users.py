|-2
  from fastapi import APIRouter, Depends, HTTPException, status, Response
  from app.core.security import oauth2_scheme, decode_token
  from app.services.user_service import UserService
  from app.db.session import get_db
  from sqlalchemy.orm import Session
  import logging

  logger = logging.getLogger(__name__)

  router = APIRouter()

  @router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
  async def delete_current_user(
      token: str = Depends(oauth2_scheme),
      db: Session = Depends(get_db)
  ):
      """
      Soft delete the currently authenticated user's account by deactivating it.

      This endpoint processes account deletion requests by:
      1. Validating the user's authentication token
      2. Verifying the user's identity
      3. Deactivating the account (setting is_active=False)

      Args:
          token: Valid access token from Authorization header
          db: Database session dependency

      Returns:
          204 No Content on successful deactivation

      Raises:
          401 Unauthorized: Invalid or missing authentication token
          404 Not Found: User account not found
          400 Bad Request: Validation errors
          500 Internal Server Error: Unexpected server issues
      """
      try:
          # Decode the token to get user information
          payload = decode_token(token)
          if not payload:
              logger.warning("Invalid or expired token during account deletion")
              raise HTTPException(
                  status_code=status.HTTP_401_UNAUTHORIZED,
                  detail="Invalid authentication token"
              )
          
          # Extract user identification from token
          user_id = payload.get("sub")
          provider = payload.get("provider")
          
          if not user_id or not provider:
              logger.error(f"Missing critical token claims: user_id={user_id}, provider={provider}")
              raise HTTPException(
                  status_code=status.HTTP_401_UNAUTHORIZED,
                  detail="Invalid authentication token"
              )
          
          # Find the user in our database
          user_service = UserService(db)
          user = user_service.find_user_by_provider_id(provider, user_id)
          
          if not user:
              logger.warning(f"User not found for deletion: provider={provider}, user_id={user_id}")
              raise HTTPException(
                  status_code=status.HTTP_404_NOT_FOUND,
                  detail="User account not found"
              )
          
          # Check if user is already inactive
          if not user.is_active:
              logger.info(f"User already deactivated: {user.id}")
              return Response(status_code=status.HTTP_204_NO_CONTENT)
          
          # Attempt to deactivate the account
          deleted_user = user_service.delete_user(user.id)
          
          logger.info(f"Successfully deactivated account: {user.id}")
          return Response(status_code=status.HTTP_204_NO_CONTENT)

      except ValueError as ve:
          logger.warning(f"Validation error during account deletion: {str(ve)}")
          raise HTTPException(
              status_code=status.HTTP_400_BAD_REQUEST,
              detail=str(ve)
          )
      except Exception as e:
          logger.exception("Unexpected error during account deletion")
          raise HTTPException(
              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
              detail="An unexpected error occurred while processing your request"
          )
