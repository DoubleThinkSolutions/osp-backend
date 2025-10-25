# app/services/verification.py

import hashlib
import os
import asyncio
import json
from typing import NamedTuple, Optional, List
from fastapi import UploadFile

# --- Cryptography & Validation Imports ---
import httpx
from cryptography import x509
from cryptography.x509.oid import ObjectIdentifier
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_der_public_key, PublicFormat, Encoding
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from certvalidator import CertificateValidator, errors as certval_errors

from app.core.logging import logger

# --- Constants and Dynamic Root Management ---
ATTESTATION_EXTENSION_OID = ObjectIdentifier("1.3.6.1.4.1.11129.2.1.17")
ROOTS_URL = "https://android.googleapis.com/attestation/root"
ROOTS_CACHE_PATH = "certs/attestation_roots.json"

# In-memory store for the trusted root certificates. This will be managed dynamically.
TRUSTED_ATTESTATION_ROOTS: List[x509.Certificate] = []

async def update_attestation_roots():
    """
    Fetches the latest attestation roots from Google, updates the in-memory
    list, and caches them to disk.
    """
    global TRUSTED_ATTESTATION_ROOTS
    logger.info("Attempting to refresh attestation root CAs...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(ROOTS_URL, timeout=15.0)
            response.raise_for_status()
        
        # Load existing roots from cache to compare
        current_roots_pem = set()
        if os.path.exists(ROOTS_CACHE_PATH):
            with open(ROOTS_CACHE_PATH, "r") as f:
                current_roots_pem.update(json.load(f))

        new_roots_data = response.json()
        new_roots_pem = set(new_roots_data)
        
        # If there's a change, update the file and the in-memory store
        if new_roots_pem != current_roots_pem:
            logger.info(f"Found new attestation root CAs. Updating cache. New count: {len(new_roots_pem)}")
            os.makedirs(os.path.dirname(ROOTS_CACHE_PATH), exist_ok=True)
            with open(ROOTS_CACHE_PATH, "w") as f:
                json.dump(new_roots_data, f)
            
            TRUSTED_ATTESTATION_ROOTS = [
                x509.load_pem_x509_certificate(pem.encode('utf-8'), default_backend()) 
                for pem in new_roots_data
            ]
        else:
            logger.info("Attestation root CAs are already up-to-date.")

    except httpx.RequestError as e:
        logger.error(f"Failed to fetch attestation roots: {e}")
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to parse attestation roots JSON: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during root CA update: {e}", exc_info=True)

def load_roots_from_cache():
    """Loads the root certificates from the local cache file on startup."""
    global TRUSTED_ATTESTATION_ROOTS
    if os.path.exists(ROOTS_CACHE_PATH):
        logger.info(f"Loading attestation roots from cache: {ROOTS_CACHE_PATH}")
        with open(ROOTS_CACHE_PATH, "r") as f:
            roots_pem_list = json.load(f)
            TRUSTED_ATTESTATION_ROOTS = [
                x509.load_pem_x509_certificate(pem.encode('utf-8'), default_backend()) 
                for pem in roots_pem_list
            ]
        logger.info(f"Successfully loaded {len(TRUSTED_ATTESTATION_ROOTS)} attestation roots from cache.")
    else:
        logger.warning("Attestation root CA cache not found. Attestation will fail until roots are fetched successfully.")

async def periodic_root_update_task():
    """A background task that runs forever, updating roots periodically."""
    while True:
        await update_attestation_roots()
        await asyncio.sleep(60 * 60 * 24) # Sleep for 24 hours


# --- Merkle Tree Implementation
CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MB

def hash_chunk(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def hash_pair(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(left + right).digest()

async def calculate_merkle_root(file: UploadFile) -> bytes:
    await file.seek(0)
    leaf_hashes = []
    while True:
        chunk = await file.read(CHUNK_SIZE_BYTES)
        if not chunk:
            break
        leaf_hashes.append(hash_chunk(chunk))
    await file.seek(0)
    if not leaf_hashes: return hashlib.sha256().digest()
    if len(leaf_hashes) == 1: return leaf_hashes[0]
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

async def _verify_attestation(cert_chain_der: List[bytes], expected_challenge: bytes, public_key_bytes: bytes) -> VerificationResult:
    """
    Verifies the Android Keystore attestation chain using a robust path validator.
    This is now an async function to handle non-blocking I/O for revocation checks.
    """
    if not TRUSTED_ATTESTATION_ROOTS:
        logger.warning("Attestation verification skipped: No trusted root CAs are loaded.")
        return VerificationResult(False, "ATTESTATION_FAILED_NO_ROOTS_LOADED")

    try:
        # 1. Parse certificates from DER format
        leaf_cert = x509.load_der_x509_certificate(cert_chain_der[0], default_backend())
        intermediate_certs = [x509.load_der_x509_certificate(c, default_backend()) for c in cert_chain_der[1:]]

        # 2. Sanity check: Public key from the leaf certificate must match the standalone public key
        leaf_public_key_bytes = leaf_cert.public_key().public_bytes(
            encoding=Encoding.DER,
            format=PublicFormat.SubjectPublicKeyInfo
        )
        if leaf_public_key_bytes != public_key_bytes:
            logger.warning("Public key in leaf certificate does not match the provided public key.")
            return VerificationResult(False, "ATTESTATION_PUBLIC_KEY_MISMATCH")

        # --- Production-grade Certvalidator Path Validation ---
        # 3. Use CertificateValidator for a full X.509 path validation,
        # including CRL and OCSP checks.
        logger.info("Performing robust certificate path validation...")
        validator = CertificateValidator(
            end_entity_cert=leaf_cert,
            intermediate_certs=intermediate_certs,
            trust_roots=TRUSTED_ATTESTATION_ROOTS
        )
        
        try:
            # Run the blocking validation logic in a separate thread
            # to avoid blocking the asyncio event loop.
            await asyncio.to_thread(validator.validate)
            logger.info("Certificate path validation successful.")
        except certval_errors.PathValidationError as e:
            logger.warning(f"Certificate path validation failed: {e}")
            # Check for specific revocation errors
            if isinstance(e, certval_errors.RevokedError):
                return VerificationResult(False, "ATTESTATION_CERT_REVOKED")
            return VerificationResult(False, "ATTESTATION_PATH_INVALID")
        # --- End of Certvalidator Logic ---

        # 4. Extract and parse the attestation extension from the leaf certificate
        attestation_ext = leaf_cert.extensions.get_extension_for_oid(ATTESTATION_EXTENSION_OID)
        attestation_data_str = str(attestation_ext.value)
        
        # 5. Verify the attestation challenge matches the metadata
        challenge_str = f"challenge=b'{expected_challenge.decode('utf-8')}'"
        if challenge_str not in attestation_data_str:
            logger.warning(f"Attestation challenge mismatch. Expected substring '{challenge_str}' not in attestation data.")
            return VerificationResult(False, "ATTESTATION_CHALLENGE_MISMATCH")

        # 6. Check other critical security properties from the TEE-enforced section
        if "tee_enforced" not in attestation_data_str:
             return VerificationResult(False, "ATTESTATION_PROPERTIES_NOT_TEE_ENFORCED")
        if "origin=b'\\x00'" not in attestation_data_str:
            return VerificationResult(False, "ATTESTATION_KEY_NOT_HARDWARE_GENERATED")
        if "purpose=b'\\x02'" not in attestation_data_str:
             return VerificationResult(False, "ATTESTATION_KEY_PURPOSE_INVALID")

    except x509.ExtensionNotFound:
        return VerificationResult(False, "ATTESTATION_EXTENSION_NOT_FOUND")
    except Exception as e:
        logger.error(f"An unexpected error occurred during attestation: {e}", exc_info=True)
        return VerificationResult(False, f"ATTESTATION_VERIFICATION_ERROR")

    return VerificationResult(True, "VERIFIED_WITH_HARDWARE_ATTESTATION")


async def verify_signature(
    file: UploadFile,
    metadata_str: str,
    client_media_hash_hex: str,
    client_metadata_hash_hex: str,
    signature_bytes: bytes,
    public_key_bytes: bytes,
    attestation_chain_str: Optional[str] = None
) -> VerificationResult:
    """
    Performs a full cryptographic verification of the uploaded media, metadata,
    and optionally the hardware attestation chain.
    """
    try:
        # Steps 1 & 2 (Hash calculation and comparison) remain the same
        if file.content_type == "video/mp4":
            server_media_hash = await calculate_merkle_root(file)
        else:
            server_media_hash = hashlib.sha256(await file.read()).digest()
            await file.seek(0)

        server_metadata_hash = hashlib.sha256(metadata_str.encode('utf-8')).digest()

        if server_media_hash != bytes.fromhex(client_media_hash_hex):
            logger.warning(f"Media hash mismatch. Client: {client_media_hash_hex}, Server: {server_media_hash.hex()}")
            return VerificationResult(False, "MEDIA_HASH_MISMATCH")
        if server_metadata_hash != bytes.fromhex(client_metadata_hash_hex):
            logger.warning(f"Metadata hash mismatch. Client: {client_metadata_hash_hex}, Server: {server_metadata_hash.hex()}")
            return VerificationResult(False, "METADATA_HASH_MISMATCH")

        # Step 3 (Signature verification)
        data_to_verify = bytes.fromhex(client_media_hash_hex) + bytes.fromhex(client_metadata_hash_hex)
        public_key = load_der_public_key(public_key_bytes)
        public_key.verify(
            signature_bytes,
            data_to_verify,
            ec.ECDSA(hashes.SHA256())
        )
        logger.info("Base signature verification successful.")

        # Step 4: Verify Attestation Chain if provided
        if attestation_chain_str:
            logger.info("Attestation chain provided, attempting robust verification...")
            try:
                cert_chain_hex = attestation_chain_str.split(',')
                cert_chain_der = [bytes.fromhex(c) for c in cert_chain_hex]
                expected_challenge = metadata_str.encode('utf-8')
                
                # Await the async attestation verification function
                attestation_result = await _verify_attestation(
                    cert_chain_der=cert_chain_der,
                    expected_challenge=expected_challenge,
                    public_key_bytes=public_key_bytes
                )
                
                return attestation_result
            
            except Exception as e:
                logger.error(f"Failed to process attestation chain: {e}", exc_info=True)
                return VerificationResult(False, "ATTESTATION_CHAIN_INVALID_FORMAT")
        
        # If no attestation was provided, return success based on signature only
        return VerificationResult(True, "VERIFIED_SIGNATURE_ONLY")

    except InvalidSignature:
        logger.warning("Cryptographic signature is invalid.")
        return VerificationResult(False, "SIGNATURE_INVALID")
    except Exception as e:
        logger.error(f"An unexpected error occurred during verification: {e}", exc_info=True)
        return VerificationResult(False, "VERIFICATION_ERROR")
