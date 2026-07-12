"""
Authentication and user management endpoints.
Handles user registration, login, token refresh, and profile management.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import timedelta
from src.database.session import get_session
from src.models.user import User
from src.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    Token,
)
from src.core.middleware import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class UserRegister(BaseModel):
    """User registration request."""
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    """User login request."""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """User profile response (no sensitive data)."""
    id: str
    email: str
    username: Optional[str]
    full_name: Optional[str]
    is_premium: bool
    is_active: bool
    created_at: str
    
    class Config:
        from_attributes = True

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegister,
    session: AsyncSession = Depends(get_session),
) -> Token:
    """
    Register a new user account.
    
    Returns: JWT access token for immediate authentication
    """
    try:
        # Check if user already exists
        existing = await session.execute(
            select(User).where(User.email == payload.email.lower())
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        
        # Create new user
        user = User(
            email=payload.email.lower(),
            username=payload.username,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            is_active=True,
            is_premium=False,  # New users on free tier
        )
        
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        logger.info(f"New user registered: {user.email}")
        
        # Return access token
        return create_access_token(str(user.id), user.email)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )

@router.post("/login", response_model=Token)
async def login(
    payload: UserLogin,
    session: AsyncSession = Depends(get_session),
) -> Token:
    """
    Authenticate user and return JWT access token.
    """
    try:
        # Find user by email
        result = await session.execute(
            select(User).where(User.email == payload.email.lower())
        )
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )
        
        # Update last login timestamp
        from datetime import datetime
        user.last_login = datetime.utcnow()
        session.add(user)
        await session.commit()
        
        logger.info(f"User logged in: {user.email}")
        
        return create_access_token(str(user.id), user.email)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )

@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get current authenticated user's profile.
    Requires valid JWT token.
    """
    return UserResponse.from_orm(current_user)

