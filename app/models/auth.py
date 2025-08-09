from pydantic import BaseModel

class SignInRequest(BaseModel):
    provider: str
    token: str

class SignInResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
