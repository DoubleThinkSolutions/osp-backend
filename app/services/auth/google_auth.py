from google.oauth2 import id_token
from google.auth.transport import requests
from typing import Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

class GoogleAuth:
    """Service for verifying Google ID tokens and extracting user information."""
    
    def __init__(self):
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        if not self.client_id:
            raise ValueError("GOOGLE_CLIENT_ID environment variable is required")
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify a Google ID token and return user information.
        
        Args:
            token: The Google ID token to verify
        
        Returns:
            Dictionary containing provider_id and other relevant user info
        
        Raises:
            ValueError: If token verification fails
        """
        try:
            # Verify the token with Google's servers
            id_info = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                self.client_id
            )
            
            # Verify the token was issued by Google
            iss_verifier = id_info['iss']
            if iss_verifier not in ['https://accounts.google.com', 'https://www.accounts.google.com']:
                raise ValueError('Invalid issuer')
                
            # Extract the user's Google ID (provider_id)
            provider_id = id_info['sub']
            
            # Return user information
            return {
                'provider_id': provider_id,
                'email': id_info.get('email'),
                'verified_email': id_info.get('email_verified', False),
                'name': id_info.get('name'),
                'given_name': id_info.get('given_name'),
                'family_name': id_info.get('family_name'),
                'picture': id_info.get('picture')
            }
            
        except ValueError as e:
            logger.warning(f"Google token verification failed: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail="INVALID_TOKEN"
            )
        except Exception as e:
            logger.error(f"Unexpected error during Google token verification: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred during token verification"
            )
