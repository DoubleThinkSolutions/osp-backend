from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.media import router as media_router
from app.api.v1.endpoints.comments import router as comments_router
from app.api.v1.endpoints.users import router as users_router

app = FastAPI(title="OSP Backend", version="0.1.0")

# Define the list of origins that are allowed to make requests.
# For development, you often need localhost.
# You can use ["*"] to allow all origins, but it's more secure to be specific.
origins = [
    "http://localhost:8001",
    "https://osp.doublethinksolutions.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # The list of origins that are allowed to make cross-origin requests.
    allow_credentials=True, # Allows cookies/authorization headers. Set to True even if some endpoints are public.
    allow_methods=["*"],    # Allows all methods (GET, POST, etc.).
    allow_headers=["*"],    # Allows all headers.
)

# Include routers
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(media_router, prefix="/api/v1")
app.include_router(comments_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to OSP Backend"}
