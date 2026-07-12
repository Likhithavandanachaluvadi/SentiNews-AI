"""
Production-grade security utilities:
- Bcrypt password hashing
- JWT token generation & verification
- CORS & rate limiting configuration
"""
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Optional
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Bcrypt context for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class TokenData(BaseModel):
    """JWT token payload structure."""
    sub: str  # user_id
    email: str
    exp: datetime
    iat: datetime
    scope: str = "analyze"  # Default scope for API usage

class Token(BaseModel):
    """API response token model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration

def hash_password(password: str) -> str:
    """
    Hash a plain-text password using bcrypt.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a bcrypt hash.
    """
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(
    user_id: str,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> Token:
    """
    Generate a JWT access token.
    
    Args:
        user_id: UUID of the user
        email: User's email address
        expires_delta: Token expiration time (default: from settings)
    
    Returns:
        Token object with access_token and expiration info
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    now = datetime.utcnow()
    expire = now + expires_delta
    
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "scope": "analyze",
    }
    
    try:
        encoded_jwt = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        return Token(
            access_token=encoded_jwt,
            token_type="bearer",
            expires_in=int(expires_delta.total_seconds()),
        )
    except Exception as e:
        logger.error(f"Failed to create access token: {e}")
        raise

def verify_token(token: str) -> TokenData:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        TokenData with decoded payload
    
    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        
        if user_id is None or email is None:
            raise JWTError("Invalid token payload")
        
        # jose stores exp and iat as integers
        return TokenData(
            sub=user_id,
            email=email,
            exp=datetime.utcfromtimestamp(payload.get("exp")),
            iat=datetime.utcfromtimestamp(payload.get("iat")),
            scope=payload.get("scope", "analyze"),
        )
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        raise
