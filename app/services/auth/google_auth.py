from fastapi import HTTPException
from google.oauth2 import id_token
from google.auth.transport import requests
from typing import Dict, Any
import logging
import os

from google_auth_oauthlib.flow import Flow
import json

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
    
    async def exchange_google_code_for_token(self, authorization_code: str) -> Dict[str, Any]:
        """
        Exchange Google authorization code for user information.
        
        Args:
            authorization_code: The authorization code from Google
            
        Returns:
            Dictionary containing user information
            
        Raises:
            HTTPException: If token exchange fails
        """
        try:
            # Configure the OAuth flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8001")]
                    }
                },
                scopes=["openid", "email", "profile"]
            )
            
            # Set the redirect URI (must match what was used in the frontend)
            flow.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8001")
            
            # Exchange the authorization code for tokens
            flow.fetch_token(code=authorization_code)
            
            # Get the ID token and verify it
            id_token_jwt = flow.credentials.id_token
            
            # Verify the ID token
            idinfo = id_token.verify_oauth2_token(
                id_token_jwt, 
                requests.Request(), 
                os.getenv("GOOGLE_CLIENT_ID")
            )
            
            # Extract user information
            return {
                'provider_id': idinfo['sub'],
                'email': idinfo.get('email'),
                'name': idinfo.get('name', ''),
                'verified_email': idinfo.get('email_verified', False)
            }
            
        except Exception as e:
            logger.error(f"Google token exchange failed: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail="Invalid Google authorization code"
            )
