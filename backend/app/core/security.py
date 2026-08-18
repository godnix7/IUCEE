import jwt
import bcrypt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from app.core.config import settings

def hash_password(password: str) -> str:
    """Hash password using bcrypt directly."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed string."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate short-lived JWT Access Token (default: 15 minutes)."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token_value() -> str:
    """Generate a cryptographically secure random refresh token string."""
    return secrets.token_urlsafe(48)

def hash_token(token: str) -> str:
    """Create a SHA-256 hash of a token for secure storage."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT Token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
