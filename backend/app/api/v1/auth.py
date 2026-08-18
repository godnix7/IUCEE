import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.core.security import (
    verify_password, create_access_token, create_refresh_token_value,
    hash_token, hash_password
)
from app.models import User, RefreshToken
from app.schemas import UserLogin, UserRegister, UserResponse, TokenResponse, TokenRefreshResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Cookie configuration
REFRESH_COOKIE_NAME = "urbansense_refresh_token"
REFRESH_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # seconds
REFRESH_COOKIE_PATH = f"{settings.API_V1_STR}/auth"


def _set_refresh_cookie(response: Response, token_value: str) -> None:
    """Set the refresh token as an HttpOnly Secure SameSite cookie."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token_value,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",  # Secure=False only in dev (http://localhost)
        samesite="lax",
        max_age=REFRESH_COOKIE_MAX_AGE,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh token cookie."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
    )


def _create_and_persist_refresh_token(
    db: Session,
    user_id: int,
    family_id: str,
    request: Request,
) -> str:
    """Create a new refresh token, hash it, persist in DB, return raw value."""
    raw_token = create_refresh_token_value()
    token_hash_value = hash_token(raw_token)

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    db_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash_value,
        token_family_id=family_id,
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent", "")[:512] if request else None,
        ip_address=request.client.host if request and request.client else None,
    )
    db.add(db_token)
    db.flush()  # Get the id for replaced_by_id linking

    return raw_token, db_token


def _revoke_token_family(db: Session, family_id: str) -> int:
    """Revoke ALL tokens in a family. Returns count revoked."""
    now = datetime.now(timezone.utc)
    count = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .update({"revoked_at": now})
    )
    return count


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(login_data: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticate user and issue JWT Access Token + HttpOnly refresh cookie."""
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive",
        )

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})

    # Create new token family for this login session
    family_id = str(uuid.uuid4())
    raw_refresh, _ = _create_and_persist_refresh_token(db, user.id, family_id, request)
    db.commit()

    # Set refresh token as HttpOnly cookie
    _set_refresh_cookie(response, raw_refresh)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/register", response_model=UserResponse)
@limiter.limit("3/minute")
def register(user_in: UserRegister, request: Request, db: Session = Depends(get_db)):
    """Register a new user account."""
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Please try a different email."
        )
    
    # Restrict direct registration to planner or viewer roles
    allowed_role = user_in.role if user_in.role in ["planner", "viewer"] else "planner"
    
    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        role=allowed_role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Refresh JWT access token using the HttpOnly refresh cookie.
    Implements true rotation: old token is revoked, new token is issued.
    Reuse of a revoked token triggers family-level revocation.
    """
    # Extract refresh token from cookie
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not provided",
        )

    token_hash_value = hash_token(raw_token)

    # Look up the token in DB
    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash_value)
        .first()
    )

    if not db_token:
        # Token not found — could be expired and cleaned up, or invalid
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # REUSE DETECTION: If this token was already revoked, someone is replaying it.
    # Revoke the ENTIRE family to protect the user.
    if db_token.revoked_at is not None:
        _revoke_token_family(db, db_token.token_family_id)
        db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected — all sessions in this family have been revoked",
        )

    # Check expiration (handle naive datetimes from SQLite)
    expires_at = db_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if expires_at < datetime.now(timezone.utc):
        db_token.revoked_at = datetime.now(timezone.utc)
        db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Verify user still active
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user or not user.is_active:
        db_token.revoked_at = datetime.now(timezone.utc)
        db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or non-existent",
        )

    # ROTATION: Revoke the old token, create a new one in the same family
    db_token.revoked_at = datetime.now(timezone.utc)

    raw_new_token, new_db_token = _create_and_persist_refresh_token(
        db, user.id, db_token.token_family_id, request
    )
    db_token.replaced_by_id = new_db_token.id
    db.commit()

    # Issue new access token
    new_access_token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})

    # Set new refresh cookie
    _set_refresh_cookie(response, raw_new_token)

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Revoke the current refresh token and clear the cookie."""
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token:
        token_hash_value = hash_token(raw_token)
        db_token = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash_value)
            .first()
        )
        if db_token and db_token.revoked_at is None:
            db_token.revoked_at = datetime.now(timezone.utc)
            db.commit()

    _clear_refresh_cookie(response)
    return {"detail": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Fetch current authenticated user profile."""
    return current_user
