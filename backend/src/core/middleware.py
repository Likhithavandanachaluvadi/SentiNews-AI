"""
Production security middleware:
- JWT authentication dependency
- Rate limiting with tier-based limits
- Input validation & sanitization
- Comprehensive error handling
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database.session import get_session
from src.models.user import User
from src.core.security import verify_token
from jose import JWTError
from typing import Optional
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)

# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)

class RateLimitConfig:
    """Rate limit configuration by user tier."""
    # Free tier: 10 requests per minute
    FREE_LIMIT = "10/minute"
    # Premium tier: 100 requests per minute
    PREMIUM_LIMIT = "100/minute"
    # Admin/System: Unlimited (no limit applied)
    ADMIN_LIMIT = "1000/minute"

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Validate JWT token and retrieve current user from database.
    
    Dependencies:
    - HTTPBearer token extraction
    - JWT verification
    - Database lookup
    
    Raises:
        HTTPException: 401 if token invalid/expired
        HTTPException: 404 if user not found
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    
    try:
        token_data = verify_token(token)
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch user from database
    try:
        result = await session.execute(
            select(User).where(User.id == token_data.sub)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )
        
        return user
        
    except Exception as e:
        logger.error(f"Database lookup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user",
        )

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """
    Optional authentication - returns user if token provided, None otherwise.
    Useful for endpoints that work for both authenticated and public users.
    """
    if credentials is None:
        return None
    
    return await get_current_user(credentials, session)

def get_user_rate_limit(user: User) -> str:
    """
    Determine rate limit based on user tier.
    
    Args:
        user: User object with is_premium flag
    
    Returns:
        Rate limit string (e.g., "10/minute" or "100/minute")
    """
    if user.is_premium:
        return RateLimitConfig.PREMIUM_LIMIT
    return RateLimitConfig.FREE_LIMIT

async def validate_ticker(ticker: str) -> str:
    """
    Validate and sanitize ticker symbol.
    
    Args:
        ticker: Ticker string to validate
    
    Returns:
        Uppercase sanitized ticker
    
    Raises:
        ValueError: If ticker is invalid
    """
    ticker = ticker.upper().strip()
    
    # Validate: 1-15 characters supporting global and Indian (NSE) tickers
    if not ticker or len(ticker) > 15:
        raise ValueError(f"Invalid ticker: {ticker}")
    
    import re
    if not re.match(r"^[A-Z0-9&\-._]+$", ticker):
        raise ValueError(f"Ticker must contain only letters, numbers, and symbols like & or -: {ticker}")
    
    return ticker

async def validate_query(query: str, max_length: int = 500, check_multiple_companies: bool = True) -> str:
    """
    Validate and sanitize user query.
    Enforces basic syntax/length constraints and optionally the single-company constraint.
    """
    query = query.strip()
    
    if not query or len(query) == 0:
        raise ValueError("Query cannot be empty")
    
    if len(query) > max_length:
        raise ValueError(f"Query exceeds {max_length} character limit")
    
    # Remove potentially dangerous characters (but allow & for stocks like M&M)
    dangerous_chars = ["<", ">", ";", "$", "`", "|"]
    for char in dangerous_chars:
        if char in query:
            raise ValueError(f"Query contains invalid character: {char}")
            
    if not check_multiple_companies:
        return query

    # Check if user query references multiple companies using EntityResolver normalization
    query_lower = query.lower()
    cleaned_query = query_lower
    for connector in [" vs ", " versus ", " compared to ", " compare ", " and ", " or ", " with "]:
        cleaned_query = cleaned_query.replace(connector, " | ")
    
    segments = [s.strip() for s in cleaned_query.split("|") if s.strip()]
    matched_tickers = set()
    from src.services.entity_resolver import EntityResolver
    for seg in segments:
        resolved_ticker, _ = EntityResolver.resolve_sync(seg)
        if resolved_ticker:
            matched_tickers.add(resolved_ticker)
            
    # Check for comparison indicators with one or more matched tickers
    comparison_indicators = [" vs ", " versus ", " compare ", " comparison ", " compared to "]
    has_comparison_word = any(indicator in query_lower for indicator in comparison_indicators)
    
    if len(matched_tickers) > 1 or (has_comparison_word and len(matched_tickers) >= 1):
        raise ValueError("Please proceed with only one stock or company at a time.")
    
    return query

def validate_query_multiple_companies(query: str, intent: str, entity_collection: Optional[dict] = None) -> None:
    """
    Validates company constraints post intent-classification:
    - STOCK_ANALYSIS, FUNDAMENTAL_ANALYSIS, TECHNICAL_ANALYSIS, NEWS_ANALYSIS, RISK_ANALYSIS, COMPANY_OVERVIEW: max 1
    - COMPARISON: max 2 (or 5 if collection is used)
    - PEER_COMPARISON: 2 or more
    - Other/fallback: max 1
    """
    if entity_collection:
        from src.services.entity_models import EntityCollection
        collection = EntityCollection.from_dict(entity_collection)
        num_companies = len(collection.entities)
    else:
        query_lower = query.lower()
        cleaned_query = query_lower
        for connector in [" vs ", " versus ", " compared to ", " compare ", " and ", " or ", " with "]:
            cleaned_query = cleaned_query.replace(connector, " | ")
        
        segments = [s.strip() for s in cleaned_query.split("|") if s.strip()]
        matched_tickers = set()
        from src.services.entity_resolver import EntityResolver
        for seg in segments:
            resolved_ticker, _ = EntityResolver.resolve_sync(seg)
            if resolved_ticker:
                matched_tickers.add(resolved_ticker)
                
        num_companies = len(matched_tickers)
        
    logger.info(f"validate_query_multiple_companies: intent={intent}, matched_companies={num_companies}")
    
    single_company_intents = {
        "STOCK_ANALYSIS",
        "FUNDAMENTAL_ANALYSIS",
        "TECHNICAL_ANALYSIS",
        "NEWS_ANALYSIS",
        "RISK_ANALYSIS",
        "COMPANY_OVERVIEW"
    }
    
    if intent in single_company_intents:
        if num_companies > 1:
            raise ValueError("Please proceed with only one stock or company at a time.")
    elif intent in {"COMPARISON", "COMPANY_COMPARISON"}:
        max_allowed = 5 if entity_collection else 2
        if num_companies > max_allowed:
            raise ValueError(f"Please proceed with up to {max_allowed} stocks or companies at a time for comparison.")
    elif intent == "PEER_COMPARISON":
        # Allow two or more.
        pass
    else:
        # Default fallback for other intents (e.g. GENERALIZED / EDUCATIONAL)
        max_allowed = 2 if (intent == "GENERALIZED" and entity_collection) else 1
        if num_companies > max_allowed:
            raise ValueError("Please proceed with only one stock or company at a time.")

async def handle_rate_limit_exceeded(request, exc):
    """
    Custom handler for rate limit exceeded errors.
    Returns proper JSON response instead of default HTML.
    """
    logger.warning(f"Rate limit exceeded for {get_remote_address(request)}")
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Free tier: 10/min, Premium: 100/min",
    )
