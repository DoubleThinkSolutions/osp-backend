# osp-backend

## Overview
OSP (Open Source Panopticon) is a **truth verification platform** enabling users to capture and upload **cryptographically verifiable media** (images/videos) with trusted metadata to combat misinformation. The backend provides secure, scalable APIs for media upload with hardware-backed signature verification, geospatial search, trust scoring, and OAuth authentication.

Built with **FastAPI**, this production-ready service features:
- **Hardware attestation verification** using Android Keystore certificates
- **Cryptographic signature validation** (ECDSA with SHA-256)
- **PostGIS geospatial queries** for radius-based search
- **S3-compatible storage** (MinIO for dev, AWS S3 for production)
- **Video processing** with FFmpeg for web compatibility
- **JWT-based authentication** with Apple Sign-In and Google OAuth

---

## Features

### Core Functionality
- ✅ **Cryptographic Media Verification**: ECDSA signature validation with SHA-256/Merkle tree hashing
- ✅ **Hardware Attestation**: Android Keystore certificate chain validation against Google attestation roots
- ✅ **Trust Scoring**: 0–100 score based on capture-to-upload time delta (1 point/minute decay)
- ✅ **Geospatial Search**: PostGIS-powered radius queries with ST_DWithin for efficient spatial indexing
- ✅ **OAuth Authentication**: Apple Sign-In and Google OAuth 2.0 with JWT tokens
- ✅ **Video Processing**: Automatic H.264/AAC re-encoding and rotation-aware thumbnail generation
- ✅ **User Content Management**: Upload, view, comment, and delete media with ownership enforcement
- ✅ **Public Discovery**: Filter content by date/time range and geographic bounds

### Security & Cryptography
- 🔐 **Hardware-Backed Keys**: Verifies device private keys generated in Trusted Execution Environment (TEE)
- 🔐 **X.509 Certificate Validation**: Full chain verification with CRL/OCSP checking via certvalidator
- 🔐 **Dynamic Root CA Updates**: Automatic refresh of Google attestation roots every 24 hours
- 🔐 **Merkle Tree Hashing**: Efficient verification for large video files (1MB chunk size)
- 🔐 **Signature Format Validation**: DER-encoded ECDSA signatures with strict ASN.1 parsing
- 🔐 **Metadata Hash Calculation**: Canonical JSON serialization prevents tampering

### Technical Highlights
- 🛡️ **JWT Protection**: 15-minute access tokens + 7-day refresh tokens with RS256/HS256 support
- 🔍 **Input Validation**: Strict type checking with Pydantic models and coordinate bounds validation
- 🗄️ **Production Database**: PostgreSQL 15 + PostGIS extension with SQLAlchemy 2.0 ORM
- 💾 **S3-Compatible Storage**: MinIO (dev) and AWS S3 (prod) with boto3 client
- 🌍 **Geospatial Indexing**: GIST index on geography columns for sub-millisecond radius queries
- 🎥 **FFmpeg Integration**: Video re-encoding, rotation detection, and thumbnail extraction
- 🐳 **Docker Compose**: Orchestrated services with health checks and volume persistence
- 🧪 **Comprehensive Testing**: Unit, integration, and API tests with pytest

---

## Architecture

### Stack
- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.9+) with async/await
- **ASGI Server**: Uvicorn
- **Database**: PostgreSQL 15 + PostGIS 3.x for geospatial queries
- **ORM**: SQLAlchemy 2.0 with GeoAlchemy2 for spatial types
- **Storage**: MinIO (S3-compatible) for dev, AWS S3 for production (boto3)
- **Security**:
  - JWT tokens via python-jose with cryptography backend
  - Apple Sign-In and Google OAuth 2.0
  - ECDSA signature verification (cryptography library)
  - X.509 certificate chain validation (certvalidator)
- **Media Processing**: FFmpeg (ffmpeg-python) and OpenCV (opencv-python-headless)
- **Validation**: Pydantic v2
- **Migrations**: Alembic
- **Dependency Management**: Poetry
- **Containerization**: Docker + Docker Compose

### Project Structure
```
osp-backend/
├── app/
│   ├── api/v1/endpoints/
│   │   ├── auth.py         # OAuth sign-in, token refresh, account deletion
│   │   ├── media.py        # Upload with verification, get, delete
│   │   ├── comments.py     # Comment creation and retrieval
│   │   └── users.py        # User profile management
│   ├── core/
│   │   ├── config.py       # Pydantic settings (env vars)
│   │   └── logging.py      # Structured logging configuration
│   ├── security/
│   │   └── jwt.py          # JWT creation, validation, decoding
│   ├── middleware/
│   │   └── auth.py         # JWT bearer authentication middleware
│   ├── db/
│   │   ├── base.py         # Base ORM class
│   │   ├── models/
│   │   │   ├── user.py     # User model with OAuth providers
│   │   │   ├── media.py    # Media with geospatial + verification fields
│   │   │   ├── comment.py  # Comment model
│   │   │   └── ...         # Claim, Verification, TrustMetric
│   │   └── session.py      # Async session management
│   ├── services/
│   │   ├── verification.py # Crypto verification + attestation
│   │   ├── trust.py        # Trust score calculation
│   │   ├── storage.py      # S3/MinIO abstraction layer
│   │   ├── user_service.py # User CRUD operations
│   │   └── auth/
│   │       ├── apple.py    # Apple Sign-In provider
│   │       └── google.py   # Google OAuth provider
│   └── main.py             # FastAPI app entrypoint
├── alembic/                # Database migrations
│   └── versions/           # Migration scripts
├── tests/
│   ├── unit/
│   ├── integration/
│   └── api/
├── certs/                  # Google attestation root certificates
├── docker-compose.yml      # Multi-service orchestration
├── Dockerfile              # Container build script
├── pyproject.toml          # Poetry dependencies
└── README.md               # This file
```

---

## Trust Score Calculation

The trust score quantifies authenticity based on how quickly media is uploaded after capture.

### Formula
```python
trust_score = max(0, 100 - (upload_time - capture_time).total_seconds() / 60)
```

### Behavior
| Delay | Score |
|------|-------|
| 0 minutes | 100 |
| 30 minutes | 70 |
| 1 hour | 40 |
| >100 minutes | 0 |

---

## API Endpoints (v1)

### Auth
- `POST /api/v1/auth/signin`
  Authenticate via Apple/Google ID token → receive JWT access + refresh tokens
- `POST /api/v1/auth/refresh`
  Renew access token using refresh token
- `DELETE /api/v1/auth/delete-account`
  Soft-delete user account (sets is_active=false)

### Media
- `POST /api/v1/media/upload` (multipart/form-data)
  Upload file with metadata, signature, public key, and optional attestation chain
  - **Parameters**:
    - `file`: Media file (image/video, max 100MB)
    - `capture_time`: ISO 8601 timestamp
    - `latitude`, `longitude`: GPS coordinates
    - `azimuth`, `pitch`, `roll`: Device orientation (degrees)
    - `signature`: Base64-encoded ECDSA signature
    - `public_key`: Base64-encoded public key (DER format)
    - `metadata_hash`: SHA-256 hash of metadata (hex string)
    - `attestation_chain`: Optional JSON array of base64-encoded certificates
  - **Returns**: `media_id`, `trust_score`, `is_verified`, `message`

- `GET /api/v1/media/{media_id}`
  Retrieve media metadata and signed URL (public access)

- `DELETE /api/v1/media/{media_id}`
  Remove media and associated files (owner only)

- `GET /api/v1/media/search`
  **Query Parameters**:
  - `lat`, `lng`, `radius_meters`: Geospatial radius search (PostGIS ST_DWithin)
  - `start_date`, `end_date`: ISO 8601 date range filter
  - `skip`, `limit`: Pagination (default: 0, 100)

### Comments
- `POST /api/v1/comments`
  Create comment on media (authenticated)
- `GET /api/v1/comments/{media_id}`
  List comments for media item

### User
- `GET /api/v1/users/me`
  Get current authenticated user profile

---

## Development Setup

### Prerequisites
- Python 3.9+
- Poetry (package manager): https://python-poetry.org/
- Docker & Docker Compose (recommended for full stack)
- FFmpeg (for video processing): `brew install ffmpeg` (macOS) or `apt-get install ffmpeg` (Linux)

### Quick Start with Docker Compose
```bash
# Clone repo
git clone https://github.com/your-org/osp-backend.git
cd osp-backend

# Create .env file (see Environment Variables section below)
cp .env.example .env

# Start all services (PostgreSQL + PostGIS + MinIO + Backend)
docker-compose up -d

# Check logs
docker-compose logs -f backend

# Run migrations
docker-compose exec backend alembic upgrade head
```

Backend: `http://localhost:8000`
API docs: `http://localhost:8000/docs` (Swagger UI)
MinIO Console: `http://localhost:9001` (admin/password123)

### Local Development (without Docker)
```bash
# Install dependencies
poetry install

# Start PostgreSQL + PostGIS (via Docker)
docker-compose up -d postgres minio

# Apply migrations
poetry run alembic upgrade head

# Start development server
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Security

### Authentication Flow
1. Mobile app signs in with Apple/Google → receives `id_token`
2. Sends `POST /api/v1/auth/signin { provider: "apple" | "google", id_token: "..." }`
3. Backend validates token with Apple/Google public keys → creates/updates user
4. Returns JWT `access_token` (15 min) + `refresh_token` (7 days)
5. All authenticated endpoints require `Authorization: Bearer <access_token>` header
6. Token refresh: `POST /api/v1/auth/refresh { refresh_token: "..." }` → new access token

### Cryptographic Verification Flow
1. **Device-side** (mobile app):
   - Generate hardware-backed key pair (Android Keystore / iOS Secure Enclave)
   - Calculate media hash (SHA-256 for images, Merkle root for videos)
   - Calculate metadata hash (canonical JSON → SHA-256)
   - Sign `media_hash || metadata_hash` with private key (ECDSA)
   - Export public key and optional attestation certificate chain

2. **Server-side** (backend):
   - Recalculate media hash from uploaded file
   - Recalculate metadata hash from request parameters
   - Verify ECDSA signature using provided public key
   - If attestation chain provided:
     - Validate X.509 certificate chain against Google root CAs
     - Check certificate validity (not expired, not revoked via CRL/OCSP)
     - Verify TEE enforcement (keys generated in hardware)
     - Extract public key from leaf certificate and compare with signature public key
   - Store verification results in database

### Security Features
- ✅ **Hardware Attestation**: Android Keystore certificate chain validation
- ✅ **Cryptographic Signatures**: ECDSA with SHA-256 hashing
- ✅ **Merkle Trees**: Efficient verification for large video files (1MB chunks)
- ✅ **X.509 Chain Validation**: Full CRL/OCSP checking via certvalidator
- ✅ **Dynamic Root Updates**: Google attestation roots refreshed every 24 hours
- ✅ **JWT Protection**: RS256/HS256 with secure key storage
- ✅ **OAuth Validation**: Apple/Google ID tokens verified with provider public keys
- ✅ **Input Sanitization**: Pydantic models with strict type checking
- ✅ **Coordinate Bounds**: -90 ≤ lat ≤ 90, -180 ≤ lng ≤ 180
- ✅ **File Validation**: Type, size (max 100MB), and MIME checking
- ✅ **UUID v4 Filenames**: Prevents path traversal attacks
- ✅ **RBAC**: Ownership enforcement for edit/delete operations
- ✅ **Provider ID Refresh**: Handles device reset scenarios gracefully

---

## Media Storage & Processing

### Storage Architecture
- **Development**: MinIO (S3-compatible) running in Docker container
- **Production**: AWS S3 with pre-signed URL support for secure downloads
- **Abstraction Layer**: `StorageService` in [app/services/storage.py](app/services/storage.py)
- **File Naming**: UUID v4 filenames prevent collisions and path traversal
- **Buckets**: `osp-media` (main storage), `osp-thumbnails` (video previews)

### Video Processing Pipeline
1. **Upload**: Receive video file (MP4, MOV, etc.)
2. **Verification**: Calculate Merkle tree hash (1MB chunks) and verify signature
3. **Storage**: Save original to S3/MinIO
4. **Re-encoding** (async):
   - FFmpeg re-encodes to H.264/AAC for universal web playback
   - Preserves rotation metadata
   - Saves processed version to S3
5. **Thumbnail Generation**:
   - Extracts first frame using FFmpeg
   - Applies rotation correction via OpenCV
   - Resizes to 320px width while preserving aspect ratio
   - Saves thumbnail to S3

### S3 Configuration
```python
# Environment variables
S3_ENDPOINT_URL=http://minio:9000  # MinIO for dev
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=osp-media
S3_REGION=us-east-1
```

---

## Testing

Run all tests:
```bash
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html

# Run specific test file
poetry run pytest tests/unit/test_verification.py

# Run tests with logging output
poetry run pytest -v -s
```

### Test Structure
- **Unit Tests** (`tests/unit/`)
  - `test_verification.py` – Cryptographic verification, Merkle trees, attestation
  - `test_trust.py` – Trust score calculation
  - `test_storage.py` – S3/MinIO operations
  - `test_models.py` – Database model validation

- **Integration Tests** (`tests/integration/`)
  - `test_auth.py` – OAuth flow, JWT lifecycle
  - `test_media.py` – Full upload/download cycle with verification

- **API Tests** (`tests/api/`)
  - End-to-end API endpoint testing with TestClient

---

## Environment Variables

Create `.env` in project root:
```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/osp

# JWT Configuration
SECRET_KEY=your_secret_key_here_change_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# OAuth Providers
APPLE_CLIENT_ID=your.app.bundle.id
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

# S3/MinIO Storage
S3_ENDPOINT_URL=http://localhost:9000  # MinIO dev, omit for AWS S3
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=osp-media
S3_REGION=us-east-1

# Application
MAX_FILE_SIZE_MB=100
LOG_LEVEL=INFO
ENVIRONMENT=development  # development | production

# Cloudflare Tunnel (optional, for external access)
TUNNEL_TOKEN=your_cloudflare_tunnel_token
```

> ⚠️ Never commit `.env` to version control. Use `.env.example` for templates.

---

## Building & Deployment

### Docker Build
```bash
# Build image
docker build -t osp-backend .

# Run with docker-compose (recommended)
docker-compose up -d

# Or run standalone
docker run -p 8000:8000 --env-file .env osp-backend
```

### Production Deployment Checklist
- ✅ Set `ENVIRONMENT=production` in environment variables
- ✅ Use strong `SECRET_KEY` (generate with `openssl rand -hex 32`)
- ✅ Configure PostgreSQL with PostGIS extension
- ✅ Set up AWS S3 bucket with appropriate CORS and lifecycle policies
- ✅ Configure OAuth client IDs for Apple and Google
- ✅ Enable HTTPS with valid SSL certificates
- ✅ Set up monitoring and logging (CloudWatch, Sentry, etc.)
- ✅ Configure database connection pooling
- ✅ Run migrations: `alembic upgrade head`
- ✅ Set up backup strategy for database and media files

### Production Architecture
```
┌──────────────┐     ┌──────────────┐
│   CloudFront │────▶│   AWS S3     │
│     (CDN)    │     │  (Media)     │
└──────────────┘     └──────────────┘
       │
       │
┌──────▼──────┐     ┌──────────────┐
│   ALB/NLB   │────▶│   RDS        │
│             │     │  PostgreSQL  │
└──────┬──────┘     │  + PostGIS   │
       │            └──────────────┘
       │
┌──────▼──────────────────────┐
│   ECS/EKS Cluster           │
│  ┌─────────────────────┐    │
│  │  FastAPI Containers │    │
│  │  (Auto-scaling)     │    │
│  └─────────────────────┘    │
└─────────────────────────────┘
```

### Recommended Stack
- **Compute**: AWS ECS Fargate or EKS
- **Database**: AWS RDS PostgreSQL 15 with Multi-AZ
- **Storage**: AWS S3 with CloudFront CDN
- **Load Balancer**: Application Load Balancer (ALB)
- **Monitoring**: CloudWatch + Sentry
- **CI/CD**: GitHub Actions + AWS CodeDeploy

---

## Geospatial Features

### PostGIS Integration
The backend leverages PostgreSQL's PostGIS extension for efficient geospatial queries:

```sql
-- Example: Find media within 5km radius of a point
SELECT * FROM media
WHERE ST_DWithin(
  location::geography,
  ST_SetSRID(ST_MakePoint(-122.4194, 37.7749), 4326)::geography,
  5000  -- meters
);
```

### Spatial Index
A GIST index on the `location` column enables sub-millisecond radius queries:
```sql
CREATE INDEX idx_media_location ON media USING GIST(location);
```

### Coordinate System
- **SRID 4326**: WGS 84 (GPS coordinates)
- **Geography Type**: Accurate distance calculations on Earth's surface
- **Validation**: -90 ≤ latitude ≤ 90, -180 ≤ longitude ≤ 180

---

## Cryptographic Details

### Signature Format
- **Algorithm**: ECDSA (Elliptic Curve Digital Signature Algorithm)
- **Curve**: P-256 (secp256r1 / prime256v1)
- **Hash Function**: SHA-256
- **Encoding**: DER (Distinguished Encoding Rules)
- **Message**: `media_hash || metadata_hash` (concatenation of two 32-byte hashes)

### Merkle Tree Construction
For video files, a Merkle tree is constructed to enable efficient verification:

1. **Chunking**: Split file into 1MB chunks
2. **Leaf Hashes**: Calculate SHA-256 for each chunk
3. **Tree Construction**: Recursively hash pairs of nodes
4. **Root Hash**: Final root becomes the `media_hash` used in signature

### Attestation Chain Validation
Android hardware attestation is verified through a full X.509 certificate chain:

```
Google Root CA (stored in certs/)
    ↓
Intermediate CA(s)
    ↓
Attestation Certificate (contains device public key)
```

**Validation Steps**:
1. Parse all certificates in chain
2. Verify signatures from root to leaf
3. Check validity dates and revocation status (CRL/OCSP)
4. Verify attestation extension properties (TEE enforcement, challenge)
5. Extract public key from leaf certificate
6. Compare with public key used for signature verification

---

## Mobile Integration

### iOS (Swift)
```swift
// Generate key pair in Secure Enclave
let tag = "com.osp.signingkey".data(using: .utf8)!
let attributes: [String: Any] = [
    kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
    kSecAttrKeySizeInBits as String: 256,
    kSecAttrTokenID as String: kSecAttrTokenIDSecureEnclave,
    kSecPrivateKeyAttrs as String: [
        kSecAttrIsPermanent as String: true,
        kSecAttrApplicationTag as String: tag
    ]
]

// Sign media + metadata
let signature = SecKeyCreateSignature(privateKey, .ecdsaSignatureMessageX962SHA256,
                                      dataToSign, &error)
```

### Android (Kotlin)
```kotlin
// Generate key with attestation
val keyPairGenerator = KeyPairGenerator.getInstance(
    KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore"
)
val parameterSpec = KeyGenParameterSpec.Builder(
    "osp_signing_key",
    KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
)
    .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
    .setDigests(KeyProperties.DIGEST_SHA256)
    .setAttestationChallenge(challenge.toByteArray())
    .build()

keyPairGenerator.initialize(parameterSpec)
val keyPair = keyPairGenerator.generateKeyPair()

// Get attestation chain
val certChain = keyStore.getCertificateChain("osp_signing_key")
```

---

## Database Schema Highlights

### Media Table
```sql
CREATE TABLE media (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    file_path VARCHAR NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    capture_time TIMESTAMP NOT NULL,
    upload_time TIMESTAMP NOT NULL,
    location GEOGRAPHY(POINT, 4326) NOT NULL,
    azimuth DOUBLE PRECISION,
    pitch DOUBLE PRECISION,
    roll DOUBLE PRECISION,
    trust_score INTEGER NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    signature TEXT,
    public_key TEXT,
    media_hash VARCHAR(64),
    metadata_hash VARCHAR(64),
    attestation_chain TEXT,
    thumbnail_path VARCHAR,
    is_public BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_media_location ON media USING GIST(location);
CREATE INDEX idx_media_capture_time ON media(capture_time);
CREATE INDEX idx_media_user_id ON media(user_id);
```

---

## Key Implementation Details

### Background Tasks
- **Attestation Root Updates**: Automatic refresh of Google's attestation root certificates every 24 hours
  - Fetches from `https://www.gstatic.com/android/key_attestation/certs.xml`
  - Parses XML and stores PEM certificates in `certs/` directory
  - Runs as FastAPI background task on startup

### Error Handling
- **Graceful Degradation**: Thumbnail generation failures don't block media upload
- **Transaction Rollback**: Failed storage operations trigger database rollback
- **Detailed Logging**: Structured logging with context for debugging
- **User-Friendly Messages**: Generic error messages to clients, detailed logs server-side

### Performance Optimizations
- **Async/Await**: All I/O operations use async for concurrency
- **Database Connection Pooling**: SQLAlchemy async engine with connection reuse
- **Spatial Indexing**: GIST indexes on geography columns for fast radius queries
- **Streaming Uploads**: Large files handled with streaming to minimize memory usage
- **Pre-signed URLs**: S3 pre-signed URLs for direct client downloads (reduces backend load)

### CORS Configuration
Configured for cross-origin requests from web clients:
```python
origins = [
    "http://localhost:3000",  # React dev server
    "http://localhost:8001",  # Static file server
    "https://osp.example.com"  # Production domain
]
```

---

## Roadmap

### Completed
- ✅ Hardware-backed cryptographic verification
- ✅ Android Keystore attestation validation
- ✅ PostGIS geospatial queries
- ✅ Video processing with FFmpeg
- ✅ S3-compatible storage
- ✅ OAuth authentication (Apple/Google)
- ✅ Docker Compose development environment

### Planned Features
- 🔲 iOS Secure Enclave attestation support
- 🔲 WebAuthn integration for web clients
- 🔲 Real-time notification system (WebSocket)
- 🔲 Content moderation and reporting
- 🔲 Advanced trust metrics (device reputation, user history)
- 🔲 Blockchain anchoring for immutable audit trails
- 🔲 Multi-language support (i18n)
- 🔲 GraphQL API alongside REST

---

## Contributing

We welcome contributions! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with clear commit messages
4. Add tests for new functionality
5. Ensure all tests pass (`poetry run pytest`)
6. Update documentation as needed
7. Submit a pull request

### Code Style
- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Write docstrings for public APIs
- Keep functions focused and modular

---

## License
MIT License - see LICENSE file for details

---

## Contact & Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/your-org/osp-backend/issues)
- **Documentation**: See individual module docstrings and API documentation at `/docs`
- **Security Issues**: Please report security vulnerabilities privately to security@osp.example.com

---

## Acknowledgments

- **FastAPI**: Modern, fast web framework for building APIs
- **PostGIS**: Spatial database extender for PostgreSQL
- **certvalidator**: Python library for X.509 certificate validation
- **FFmpeg**: Multimedia framework for video processing
- **Google**: Android Key Attestation infrastructure

---

**OSP Backend** – Building a foundation for verifiable truth through cryptographic evidence and geospatial verification.
