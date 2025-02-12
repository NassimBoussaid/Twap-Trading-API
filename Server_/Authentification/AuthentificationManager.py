from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt as PyJWT
from datetime import datetime, timedelta

SECRET_KEY = "9ff4412bec11bb73296122965fd46ca810b148e17cadfd2f64fc9eb635573539"
security = HTTPBearer()

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

def create_token(username: str) -> str:
    """Create a JWT Token"""
    expiration = datetime.utcnow() + timedelta(minutes=30)
    return PyJWT.encode(
        {
            "username": username,
            "exp": expiration
        },
        SECRET_KEY,
        algorithm="HS256"
    )

async def verify_token(credentials : HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT Token"""
    token = credentials.credentials
    try:
        payload = PyJWT.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["username"]
    except PyJWT.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except PyJWT.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")