from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt as PyJWT
from datetime import datetime, timedelta

SECRET_KEY = "9ff4412bec11bb73296122965fd46ca810b148e17cadfd2f64fc9eb635573539"
security = HTTPBearer()


class LoginRequest(BaseModel):
    """
        Model for user login requests.

        Attributes:
            username (str): The username of the user attempting to log in.
            password (str): The user's password.
    """
    username: str
    password: str

class RegisterRequest(BaseModel):
    """
        Model for user registration requests.

        Attributes:
            username (str): The desired username for the new user.
            password (str): The password for the new user.
    """
    username: str
    password: str

class TokenResponse(BaseModel):
    """
        Model for token response after successful authentication.

        Attributes:
            access_token (str): The generated JWT token.
            token_type (str): The type of the token, default is "bearer".
    """
    access_token: str
    token_type: str = "bearer"

def create_token(username: str) -> str:
    """
        Create a unique JWT token for a specified user.

        Args:
            username (str): The username for which the token is generated.

        Returns:
            str: The generated JWT token as a string.

        The token includes:
            - "username": The associated username.
            - "exp": Expiration time set to 30 minutes from creation.
    """
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
    """
        Verify the validity of a JWT token.

        Args:
            credentials (HTTPAuthorizationCredentials): The token extracted from the request header.

        Returns:
            str: The username associated with the valid token.

        Raises:
            HTTPException (401): If the token is expired, invalid, or any other authentication error occurs.
    """
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