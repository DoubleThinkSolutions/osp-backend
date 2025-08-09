# osp-backend

## Overview
OSP (Open Source Panopticon) is a truth verification platform enabling users to capture and upload verifiable media (images/videos) with trusted metadata. The backend provides secure, scalable APIs for media upload, trust scoring, user authentication, and content retrieval.

Built with **FastAPI**, this service supports JWT-based authentication, metadata-rich media handling, and dynamic trust scoring based on capture-to-upload latency. Designed for production from day one, it is container-ready and modular for future AWS/S3 integration.

---

## Features

### Core Functionality
- ✅ **Media Upload**: Accept image/video files with metadata (capture time, GPS coordinates, device orientation)
- ✅ **Trust Scoring**: Automatically calculates a 0–100 score based on time delay between capture and upload
- ✅ **Secure Authentication**: Sign-in via Apple (iOS) and Google (Android) using JWT tokens
- ✅ **User Content Management**: Users can view, comment on, or delete their own content
- ✅ **Public Search & Discovery**: Filter content by date/time and geographic region via interactive map
- ✅ **Role-Based Access Control (RBAC)**: Enforces ownership rules for edit/delete actions

### Technical Highlights
- 🛡️ **JWT Protection**: All sensitive endpoints require authentication with 15-minute access tokens + 7-day refresh
- 🔍 **Input Validation**: Strict type and bounds checking using Pydantic models
- 🧱 **Database Ready**: SQLite for development, schema-compatible with PostgreSQL (production target)
- 💾 **Storage Abstraction**: Pluggable storage layer (currently local filesystem → future S3)
- 🌍 **Interactive Map Support**: Designed for integration with Leaflet.js and OpenStreetMap
- 🧪 **Tested & Verified**: Unit and integration tests ensure correctness

---

## Architecture

### Stack
- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10)
- **ASGI Server**: Uvicorn
- **Database**: SQLite (dev), PostgreSQL-compatible schema (production-ready)
- **ORM**: SQLAlchemy
- **Security**: JWT (python-jose), Bcrypt (Passlib)
- **Validation**: Pydantic
- **Migrations**: Alembic

### Project Structure
```
osp-backend/
├── app/
│   ├── api/v1/endpoints/
│   │   ├── auth.py      # OAuth sign-in, token issuance
│   │   ├── media.py     # Upload, get, delete, comment
│   │   └── users.py     # Profile, account deletion
│   ├── core/
│   │   ├── config.py    # Settings, env vars
│   │   ├── security.py  # JWT, hashing, auth middleware
│   │   └── storage.py   # Media file handling (uuid paths, fs)
│   ├── db/
│   │   ├── base.py      # Base ORM model
│   │   ├── models.py    # DB tables: User, Media, Comment
│   │   └── session.py   # DB session management
│   ├── services/
│   │   ├── auth.py      # Token validation, user creation
│   │   ├── media.py     # Business logic for media ops
│   │   └── trust.py     # Trust score calculation
│   └── main.py          # App entrypoint
├── alembic/             # DB migrations
├── tests/
│   ├── unit/
│   └── integration/
├── Dockerfile           # Containerization script
├── pyproject.toml       # Dependency management (Poetry)
└── README.md            # This file
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
  Authenticate via Apple/Google ID token → receive JWT
- `POST /api/v1/auth/refresh`  
  Renew access token using refresh token
- `DELETE /api/v1/auth/delete-account`  
  Delete user account and associated data

### Media
- `POST /api/v1/media/upload`  
  Upload file with metadata → returns `media_id`, `trust_score`
- `GET /api/v1/media/{media_id}`  
  Retrieve media metadata (public)
- `DELETE /api/v1/media/{media_id}`  
  Remove media (user must own it)
- `POST /api/v1/media/{media_id}/comment`  
  Add comment to media
- `GET /api/v1/media/search?lat_min=...&lng_max=...&start_date=...&end_date=...`  
  Search by geolocation and time

### User
- `GET /api/v1/users/me`  
  Get current user info

---

## Development Setup

### Prerequisites
- Python 3.10+
- Poetry (package manager): https://python-poetry.org/
- Optional: Docker (for containerized runs)

### Install & Run
```bash
# Clone repo
git clone https://github.com/your-org/osp-backend.git
cd osp-backend

# Install dependencies
poetry install

# Initialize database & apply migrations
alembic upgrade head

# Start server
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will be available at: `http://localhost:8000`  
API docs: `http://localhost:8000/docs` (Swagger UI)

---

## Security

### Authentication Flow
1. Mobile app signs in with Apple/Google → receives `id_token`
2. Sends `POST /api/v1/auth/signin { provider: "apple", id_token: "..." }`
3. Backend validates token → creates user if new → returns `access_token` and `refresh_token`
4. Web and mobile use `access_token` in `Authorization: Bearer <token>` header

### Protections Implemented
- ✅ JWT validation with RSA signatures (mocked in dev)
- ✅ Secure password hashing (BCrypt)
- ✅ Input sanitization (Pydantic models)
- ✅ Geo-coordinate bounds (-90 <= lat <= 90, -180 <= lng <= 180)
- ✅ File type/size limits (max 100MB, only `.jpg`, `.jpeg`, `.mp4`)
- ✅ UUID v4 media IDs prevent path traversal
- ✅ RBAC: Users only modify/delete their own content

---

## Media Storage

### Current (Development)
- Files stored under `./storage/` using UUID v4 filenames
- Example path: `storage/7a81c9e2-f3b4-4a1d-8f0e-1d2c4f5b6a7c.jpg`

### Future-Proof (Production)
- Interface defined in `app.core.storage.StorageBackend`
- Easy swap to S3 via `S3Storage` implementation (boto3)
- Environment-controlled via config

---

## Testing

Run all tests:
```bash
poetry run pytest
```

Test categories:
- `tests/unit/test_trust.py` – Trust score formula verification
- `tests/unit/test_storage.py` – File save/load correctness
- `tests/unit/test_validation.py` – Bad input rejection (e.g., invalid lat/lng)
- `tests/integration/test_auth.py` – JWT flow and protected routes
- `tests/integration/test_media.py` – Full upload cycle

---

## Environment Variables

Create `.env` in project root:
```env
DATABASE_URL=sqlite+aiosqlite:///./app.db
SECRET_KEY=your_jwt_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
AUTH_PROVIDER=mock  # mock | firebase (production)
STORAGE_PATH=./storage
MAX_FILE_SIZE_MB=100
```

> ⚠️ Never commit `.env` to version control

---

## Building & Deployment

### Docker Build
```bash
docker build -t osp-backend .
docker run -p 8000:8000 --env-file .env osp-backend
```

### Production Readiness
- ✅ OpenAPI/Swagger docs built-in
- ✅ Structured logging ready
- ✅ Async-safe database access
- ✅ Migration-ready (Alembic)
- ✅ Configurable storage backend
- ✅ Auth provider abstraction

Target deployment: AWS EC2/ECS + RDS (PostgreSQL) + S3 (media)

---

## Local Simulation & Stubs

To support development without emulators or external services:

| Component | Stub | Real Replacement |
|--------|------|----------------|
| Apple/Google Login | `MockAuthProvider` accepts "MOCK_TOKEN" | Firebase Auth |
| Map Tiles | Offline OSM tile cache | Tiled OSM/WMTS endpoint |
| Media Storage | Local filesystem | AWS S3 |

Set `AUTH_PROVIDER=firebase` in production to enable live auth.

---

## Cross-Platform Integration

### Mobile Apps
- Account creation only allowed on iOS/Android via Apple/Google sign-in
- Use same `/auth/signin` endpoint
- Capture metadata: `capture_time`, `lat`, `lng`, `orientation`
- Skip watermarking (per plan)

### Web Platform
- Located in `/osp-web`
- Static site (HTML/CSS/JS)
- Leaflet.js for interactive map
- Search via date range and coordinates
- Host locally during dev:  
  ```bash
  cd osp-web && python3 -m http.server 8001 --directory public
  ```

---

## Verification of Completion

✅ **All done when:**
- [x] `POST /media/upload` accepts file + metadata → returns correct trust score
- [x] `GET /media/search` filters by location/time and returns results
- [x] JWT-protected routes reject unauthenticated requests (401) and allow valid ones (200)
- [x] Database schema contains required fields: `media_id`, `capture_time`, `lat`, `lng`, `orientation`, `trust_score`, `user_id`
- [x] Tests pass: `poetry run pytest` → 100% success
- [x] Manual check: Open `localhost:8001` → Map loads correctly

> *Deployment and monitoring are out of scope per project constraints.*

---

## License
MIT

---

## Author
OSP Team – Building verifiable truth for everyone.
