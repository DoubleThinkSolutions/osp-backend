# app/services/verification.py

import hashlib
import os
from fastapi import UploadFile
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.exceptions import InvalidSignature
from typing import NamedTuple

from app.core.logging import logger

# --- Merkle Tree Implementation (must match the client's) ---
CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MB

def hash_chunk(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def hash_pair(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(left + right).digest()

async def calculate_merkle_root(file: UploadFile) -> bytes:
    """Calculates the Merkle root hash of an UploadFile."""
    await file.seek(0)
    leaf_hashes = []
    while True:
        chunk = await file.read(CHUNK_SIZE_BYTES)
        if not chunk:
            break
        leaf_hashes.append(hash_chunk(chunk))
    
    await file.seek(0) # Reset file pointer for subsequent use (e.g., S3 upload)

    if not leaf_hashes:
        return hashlib.sha256().digest()
    if len(leaf_hashes) == 1:
        return leaf_hashes[0]

    current_level = leaf_hashes
    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if (i + 1) < len(current_level) else left
            next_level.append(hash_pair(left, right))
        current_level = next_level
    
    return current_level[0]

# --- Verification Logic ---

class VerificationResult(NamedTuple):
    is_valid: bool
    status_message: str

async def verify_signature(
    file: UploadFile,
    metadata_str: str,
    client_media_hash_hex: str,
    client_metadata_hash_hex: str,
    signature_bytes: bytes,
    public_key_bytes: bytes
) -> VerificationResult:
    """
    Performs a full cryptographic verification of the uploaded media and metadata.
    """
    try:
        # 1. Re-calculate server-side hashes
        # Determine hashing strategy based on content type
        if file.content_type == "video/mp4":
            server_media_hash = await calculate_merkle_root(file)
        else: # Default to simple hash for images
            server_media_hash = hashlib.sha256(await file.read()).digest()
            await file.seek(0) # IMPORTANT: Reset file pointer after reading

        server_metadata_hash = hashlib.sha256(metadata_str.encode('utf-8')).digest()

        # 2. Compare server-calculated hashes with client-provided hashes
        client_media_hash = bytes.fromhex(client_media_hash_hex)
        if server_media_hash != client_media_hash:
            logger.warning(f"Media hash mismatch. Client: {client_media_hash_hex}, Server: {server_media_hash.hex()}")
            return VerificationResult(False, "MEDIA_HASH_MISMATCH")

        client_metadata_hash = bytes.fromhex(client_metadata_hash_hex)
        if server_metadata_hash != client_metadata_hash:
            logger.warning(f"Metadata hash mismatch. Client: {client_metadata_hash_hex}, Server: {server_metadata_hash.hex()}")
            return VerificationResult(False, "METADATA_HASH_MISMATCH")

        # 3. Verify the cryptographic signature
        # The data that was signed is the concatenation of the *client-provided* hashes
        data_to_verify = client_media_hash + client_metadata_hash

        public_key = load_der_public_key(public_key_bytes)
        
        # This will raise InvalidSignature on failure
        public_key.verify(
            signature_bytes,
            data_to_verify,
            ec.ECDSA(hashes.SHA256())
        )

        logger.info("Signature verification successful.")
        return VerificationResult(True, "VERIFIED_OK")

    except InvalidSignature:
        logger.warning("Cryptographic signature is invalid.")
        return VerificationResult(False, "SIGNATURE_INVALID")
    except Exception as e:
        logger.error(f"An unexpected error occurred during verification: {e}")
        return VerificationResult(False, "VERIFICATION_ERROR")
