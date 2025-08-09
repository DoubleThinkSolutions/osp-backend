import httpx
import time
import logging
from typing import Dict, Optional, Any
from jose import jwt, jwk
from jose.utils import base64url_decode
from jose.exceptions import JWTError
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)

# Cache for Apple public keys with their expiry
_apple_keys_cache: Optional[Dict] = None
_apple_keys_expiry: int = 0
APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"
ALGORITHM = "RS256"

def _construct_rsa_key(n: str, e: str) -> bytes:
    """
    Construct RSA public key from modulus and exponent (as Base64URL-encoded strings).
    Returns the public key in PEM format.
    """
    try:
        # Decode the Base64URL-encoded modulus and exponent
        n = int.from_bytes(base64url_decode(n.encode()), "big")
        e = int.from_bytes(base64url_decode(e.encode()), "big")
        
        # Construct RSA public numbers and serialize to PEM
        public_numbers = RSAPublicNumbers(e=e, n=n)
        public_key = public_numbers.public_key()
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    except Exception as exc:
        logger.error(f"Failed to construct RSA key: {exc}")
        raise

async def _fetch_apple_public_keys(client: httpx.AsyncClient) -> Dict:
    """
    Fetch Apple's public keys and cache them with a TTL.
    """
    global _apple_keys_cache, _apple_keys_expiry

    current_time = int(time.time())
    if _apple_keys_cache is not None and current_time < _apple_keys_expiry:
        return _apple_keys_cache

    try:
        response = await client.get(APPLE_KEYS_URL)
        response.raise_for_status()
        keys = response.json().get("keys", [])

        # Cache for 24 hours (Apple keys rarely rotate)
        _apple_keys_cache = {key["kid"]: key for key in keys}
        _apple_keys_expiry = current_time + (24 * 3600)

        logger.info("Successfully fetched and cached Apple public keys")
        return _apple_keys_cache
    except Exception as exc:
        logger.error(f"Failed to fetch Apple public keys: {exc}")
        if _apple_keys_cache is not None:
            logger.info("Using expired cached keys as fallback")
            return _apple_keys_cache
        raise

async def verify_apple_id_token(
    id_token: str,
    client_id: str,
    nonce: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Verify an Apple ID token and return the decoded claims.

    Args:
        id_token: The JWT ID token from Apple Sign-In.
        client_id: The expected audience (your service ID).
        nonce: Optional nonce used during authentication.

    Returns:
        Decoded token claims on success.

    Raises:
        HTTPException: With status_code 401 for invalid/missing tokens
        HTTPException: With status_code 500 for unexpected errors
    """
    if not id_token:
        logger.warning("No ID token provided")
        raise HTTPException(
            status_code=401,
            detail="INVALID_TOKEN"
        )

    try:
        # Decode the token header to get the key ID (kid)
        unverified_header = jwt.get_unverified_header(id_token)
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg")

        if not kid:
            logger.warning("No key ID (kid) found in token header")
            raise HTTPException(
                status_code=401,
                detail="INVALID_TOKEN"
            )

        if alg != ALGORITHM:
            logger.warning(f"Invalid algorithm: {alg}, expected {ALGORITHM}")
            raise HTTPException(
                status_code=401,
                detail="INVALID_TOKEN"
            )

        # Get Apple's public keys
        async with httpx.AsyncClient() as client:
            keys = await _fetch_apple_public_keys(client)

        key = keys.get(kid)
        if not key:
            logger.warning(f"Public key not found for kid: {kid}")
            raise HTTPException(
                status_code=401,
                detail="INVALID_TOKEN"
            )

        # Construct RSA public key from n and e
        rsa_key = _construct_rsa_key(key["n"], key["e"])

        # Decode and verify the token
        claims = jwt.decode(
            id_token,
            rsa_key,
            algorithms=[ALGORITHM],
            audience=client_id,
            issuer=APPLE_ISSUER,
            options={
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_nonce": bool(nonce),
            },
            nonce=nonce
        )

        # Ensure essential claims are present
        if "sub" not in claims:
            logger.warning("No subject (sub) claim in token")
            raise HTTPException(
                status_code=401,
                detail="INVALID_TOKEN"
            )

        logger.info(f"Successfully verified Apple ID token for user: {claims['sub']}")
        return claims

    except jwt.ExpiredSignatureError:
        logger.warning("Apple ID token has expired")
        raise HTTPException(
            status_code=401,
            detail="INVALID_TOKEN"
        )
    except jwt.JWTClaimsError as e:
        logger.warning(f"Apple ID token claim validation failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="INVALID_TOKEN"
        )
    except JWTError as e:
        logger.error(f"JWT decode failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="INVALID_TOKEN"
        )
    except Exception as e:
        logger.error(f"Unexpected error during Apple ID token verification: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during token verification"
        )
