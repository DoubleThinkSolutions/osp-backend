import pytest
import time
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from jose import jwt as pyjwt
from jose import JWTError
import httpx
from app.main import app
from app.security.jwt import create_access_token, create_refresh_token, SECRET_KEY, ALGORITHM
from app.db.session import get_db
from app.services.user_service import UserService

# Create a test client
client = httpx.AsyncClient(app=app, base_url="http://test")

# Test user data
TEST_USER_ID = "test-user-123"
TEST_PROVIDER = "test"
TEST_ROLES = ["user"]

@pytest.fixture(autouse=True)
def clear_cache():
    """Ensure clean state for each test"""
    yield
    # Close client after all tests
    if hasattr(client, '_transport'):
        client._transport.aclose()

@pytest.fixture
def valid_access_token():
    """Create a valid access token for testing"""
    return create_access_token(
        user_id=TEST_USER_ID,
        provider=TEST_PROVIDER,
        roles=TEST_ROLES,
        expires_in=900  # 15 minutes
    )

@pytest.fixture
def expired_access_token():
    """Create an expired access token"""
    # Create payload with expired time
    expire = datetime.utcnow() - timedelta(minutes=1)
    payload = {
        "userId": TEST_USER_ID,
        "provider": TEST_PROVIDER,
        "roles": TEST_ROLES,
        "exp": expire,
        "iat": datetime.utcnow() - timedelta(hours=1),
        "type": "access"
    }
    return pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

@pytest.fixture
def malformed_token():
    """Create a malformed token"""
    return "this.is.not.a.valid.jwt.token"

@pytest.fixture
def valid_refresh_token():
    """Create a valid refresh token"""
    return create_refresh_token(
        user_id=TEST_USER_ID,
        provider=TEST_PROVIDER,
        roles=TEST_ROLES,
        expires_in=604800  # 7 days
    )

@pytest.fixture
def expired_refresh_token():
    """Create an expired refresh token"""
    # Create payload with expired time
    expire = datetime.utcnow() - timedelta(hours=1)
    payload = {
        "userId": TEST_USER_ID,
        "provider": TEST_PROVIDER,
        "roles": TEST_ROLES,
        "exp": expire,
        "iat": datetime.utcnow() - timedelta(days=8),
        "type": "refresh"
    }
    return pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

@pytest.mark.asyncio
async def test_valid_token_is_accepted(valid_access_token, caplog):
    """Test that a valid access token is accepted and grants access to protected routes"""
    
    # Patch UserService.find_user_by_provider_id to return a mock user
    with patch('app.middleware.auth.UserService') as mock_user_service:
        mock_instance = MagicMock()
        mock_instance.find_user_by_provider_id.return_value = MagicMock(
            id=TEST_USER_ID,
            is_deleted=False
        )
        mock_user_service.return_value.__enter__.return_value = mock_instance
        
        # Mock dependency to bypass DB check
        def mock_get_db():
            return MagicMock()
        
        app.dependency_overrides[get_db] = mock_get_db
        
        try:
            with caplog.at_level(logging.INFO):
                headers = {"Authorization": f"Bearer {valid_access_token}"}
                response = await client.get("/api/v1/auth/me", headers=headers)  # Assuming /me is a protected route
                
                # Verify response
                assert response.status_code == 200
                
                # Verify logging
                assert any("Successfully authenticated user" in log for log in caplog.messages)
                
        finally:
            # Clean up dependency overrides
            app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_expired_access_token_is_rejected(expired_access_token, caplog):
    """Test that an expired access token is rejected with TOKEN_EXPIRED error"""
    
    with caplog.at_level(logging.WARN):
        headers = {"Authorization": f"Bearer {expired_access_token}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        # Verify response
        assert response.status_code == 401
        response_data = response.json()
        assert "error" in response_data
        assert response_data["error"] == "INVALID_TOKEN"
        
        # Verify logging
        assert any("Token decoding failed" in log or "expired" in log.lower() for log in caplog.messages)

@pytest.mark.asyncio
async def test_malformed_token_is_rejected(malformed_token, caplog):
    """Test that a malformed JWT token is rejected with INVALID_TOKEN error"""
    
    with caplog.at_level(logging.WARN):
        headers = {"Authorization": f"Bearer {malformed_token}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        # Verify response
        assert response.status_code == 401
        response_data = response.json()
        assert "error" in response_data
        assert response_data["error"] == "INVALID_TOKEN"
        
        # Verify logging
        assert any("Invalid token" in log or "malformed" in log.lower() for log in caplog.messages)

@pytest.mark.asyncio
async def test_valid_refresh_token_returns_new_access_token(valid_refresh_token, caplog):
    """Test that a valid refresh token returns a new access token"""
    
    # Patch the UserService to simulate existing user
    with patch('app.api.v1.endpoints.auth.UserService') as mock_user_service:
        mock_instance = MagicMock()
        mock_instance.find_user_by_provider_id.return_value = MagicMock(
            id=TEST_USER_ID,
            is_deleted=False
        )
        mock_user_service.return_value.__enter__.return_value = mock_instance
        
        try:
            with caplog.at_level(logging.INFO):
                response = await client.post("/api/v1/auth/refresh-token", json={
                    "refreshToken": valid_refresh_token
                })
                
                # Verify response
                assert response.status_code == 200
                response_data = response.json()
                assert "accessToken" in response_data
                assert isinstance(response_data["accessToken"], str)
                assert len(response_data["accessToken"]) > 0
                
                # Verify new token is valid
                # (We won't validate signature here, just check structure)
                parts = response_data["accessToken"].split(".")
                assert len(parts) == 3  # JWT has 3 parts
                
                # Verify logging
                assert any("Access token refreshed" in log for log in caplog.messages)
                
        finally:
            # Ensure mocks are cleaned up
            mock_user_service.reset_mock()

@pytest.mark.asyncio
async def test_invalid_refresh_token_is_rejected(expired_refresh_token, caplog):
    """Test that an invalid (expired) refresh token is rejected with REFRESH_TOKEN_INVALID error"""
    
    with caplog.at_level(logging.WARN):
        response = await client.post("/api/v1/auth/refresh-token", json={
            "refreshToken": expired_refresh_token
        })
        
        # Verify response
        assert response.status_code == 403
        response_data = response.json()
        assert "error" in response_data
        assert response_data["error"] == "REFRESH_TOKEN_INVALID"
        
        # Verify logging
        assert any("Invalid or expired refresh token" in log for log in caplog.messages)

@pytest.mark.asyncio
async def test_user_deletion_invalidates_refresh_token(malformed_token, caplog):
    """Test that a refresh token fails if the user has been deleted"""
    
    # Create a valid refresh token for this test
    valid_token = create_refresh_token(
        user_id=TEST_USER_ID,
        provider=TEST_PROVIDER,
        roles=TEST_ROLES
    )
    
    # Patch UserService to return a deleted user
    with patch('app.api.v1.endpoints.auth.UserService') as mock_user_service:
        mock_instance = MagicMock()
        mock_instance.find_user_by_provider_id.return_value = MagicMock(
            id=TEST_USER_ID,
            is_deleted=True
        )
        mock_user_service.return_value.__enter__.return_value = mock_instance
        
        try:
            with caplog.at_level(logging.WARN):
                response = await client.post("/api/v1/auth/refresh-token", json={
                    "refreshToken": valid_token
                })
                
                # Verify response
                assert response.status_code == 403
                response_data = response.json()
                assert "error" in response_data
                assert response_data["error"] == "REFRESH_TOKEN_INVALID"
                
                # Verify logging
                assert any("User not found or deleted" in log for log in caplog.messages)
                
        finally:
            mock_user_service.reset_mock()
