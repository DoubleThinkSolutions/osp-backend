from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.db.models import User
from app.db.base import SessionLocal
import logging

logger = logging.getLogger(__name__)

class UserService:
    """Service for handling user-related operations in the database."""

    def __init__(self, db: Optional[Session] = None):
        """Initialize the UserService with an optional database session.

        Args:
            db: Optional SQLAlchemy database session. If not provided, a new session will be created.
        """
        self.db = db or SessionLocal()

    def find_user_by_provider_id(self, provider: str, provider_id: str) -> Optional[User]:
        """Find a user by their provider and provider ID.

        Args:
            provider: The authentication provider (e.g., 'google', 'apple').
            provider_id: The unique ID from the authentication provider.

        Returns:
            The User object if found, None otherwise.
        """
        try:
            user = self.db.query(User).filter(
                User.provider == provider,
                User.provider_id == provider_id
            ).first()
            return user
        except Exception as e:
            logger.error(f"Error finding user by provider ID: {e}")
            raise

    def create_user(self, user_data: Dict[str, Any]) -> User:
        """Create a new user in the database.

        Args:
            user_data: Dictionary containing user data including:
                - provider: The authentication provider
                - provider_id: The unique ID from the authentication provider
                - email: User's email address
                - username: User's username (optional)
                - full_name: User's full name (optional)

        Returns:
            The newly created User object.
        """
        try:
            # Ensure required fields are present
            required_fields = ['provider', 'provider_id', 'email']
            for field in required_fields:
                if field not in user_data:
                    raise ValueError(f"Missing required field: {field}")

            # Create the user
            db_user = User(
                provider=user_data['provider'],
                provider_id=user_data['provider_id'],
                email=user_data['email'],
                username=user_data.get('username'),
                full_name=user_data.get('full_name'),
                is_verified=True if user_data['provider'] in ['google', 'apple'] else False,
                is_active=True
            )

            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)

            logger.info(f"Created new user with provider ID: {user_data['provider_id']}")
            return db_user

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating user: {e}")
            raise

    def delete_user(self, user_id: int) -> User:
        """Soft delete a user by deactivating their account.
        
        Args:
            user_id: The unique ID of the user to delete.
            
        Returns:
            The updated User object with is_active=False
        
        Raises:
            ValueError: If user with the given ID is not found
            Exception: For database errors during operation
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User with id {user_id} not found")
            user.is_active = False
            self.db.commit()
            self.db.refresh(user)
            logger.info(f"User account deleted (deactivated): {user_id}")
            return user
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting user account {user_id}: {str(e)}")
            raise
    
    def close(self):
        """Close the database session if it was created internally."""
        if self.db and not hasattr(self.db, 'external'):
            self.db.close()

    def __enter__(self):
        """Support for context manager protocol."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure the session is closed when exiting the context."""
        self.close()
