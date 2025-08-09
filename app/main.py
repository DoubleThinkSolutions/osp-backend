from fastapi import FastAPI
from app.api.v1.endpoints.auth import router as auth_router

app = FastAPI(title="OSP Backend", version="0.1.0")

# Include routers
app.include_router(auth_router, prefix="/api/v1/auth")

@app.get("/")
def read_root():
    return {"message": "Welcome to OSP Backend"}
