"""
Production-grade FastAPI application for SentiNews AI.
Features:
- Async architecture for high performance
- Security: Rate limiting, JWT auth, input validation
- Database: Async SQLAlchemy with connection pooling
- Error handling: Comprehensive exception handling
- Monitoring: Health checks, logging, performance tracking
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
import logging
from typing import Dict, Any
import time

from src.core.config import settings
from src.database.session import init_db, close_db
from src.core.middleware import limiter, handle_rate_limit_exceeded
from src.api.v1.endpoints import auth, analysis, market, features

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.
    Handles startup and shutdown events.
    """
    # STARTUP
    try:
        logger.info("🚀 Starting SentiNews AI Backend...")
        await init_db()
        logger.info("✅ Database initialized")
        logger.info("✅ All services ready - API server online")
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        if settings.ENVIRONMENT == "development":
            logger.warning(
                "Database is unavailable; continuing in development mode. "
                "Guest research can run, but auth/history persistence may fail."
            )
        else:
            raise
    
    yield
    
    # SHUTDOWN
    try:
        logger.info("🛑 Shutting down SentiNews AI Backend...")
        await close_db()
        logger.info("✅ Database connections closed")
        logger.info("✅ Graceful shutdown complete")
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="SentiNews AI API",
    description="Production-grade AI financial intelligence platform with real-time analysis",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# ============================================================================
# MIDDLEWARE STACK (ORDER MATTERS)
# ============================================================================

# 1. Rate Limiting (slowapi)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# 2. CORS
app.add_middleware(
    CORSMiddleware,
    # Frontend URLs (adjust for production)
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ] if settings.ENVIRONMENT == "development" else [
        "https://sentinews.ai",
        "https://www.sentinews.ai",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Page-Number"],
    max_age=3600,  # Cache preflight for 1 hour
)

# 3. Request timing (for performance monitoring)
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Track and log request processing time."""
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log slow requests
        if process_time > 5.0:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time:.2f}s"
            )
        
        return response
    except Exception as e:
        logger.error(f"Request processing error: {e}")
        raise

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "Rate limit exceeded",
            "limit_info": str(exc.detail),
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    logger.warning(f"Validation error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors(),
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: RequestValidationError):
    """Catch-all error handler for unexpected errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
        }
    )

# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """
    Basic health check - confirms API is running.
    """
    return {
        "status": "healthy",
        "service": "SentiNews AI API",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
    }

@app.get("/health/ready", tags=["Health"])
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check - confirms all dependencies are ready.
    Returns 503 if not ready, 200 if ready.
    """
    try:
        from sqlalchemy import text
        from src.database.session import engine
        
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        
        return {
            "status": "ready",
            "database": "connected",
            "services": {
                "llm": "groq" if settings.GROQ_API_KEY else "unavailable",
                "vector_db": "qdrant",
                "news_api": "enabled" if settings.NEWS_API_KEY else "unavailable",
            }
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "error": str(e),
            }
        )

# ============================================================================
# API ROUTERS
# ============================================================================

# Include endpoint routers
app.include_router(auth.router)
app.include_router(analysis.router)
app.include_router(market.router)
app.include_router(features.router)

# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/", tags=["Info"])
async def root() -> Dict[str, Any]:
    """
    Root endpoint with API information.
    """
    return {
        "name": "SentiNews AI API",
        "version": "1.0.0",
        "description": "AI-powered financial intelligence platform",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "readiness": "/health/ready",
            "auth": "/api/v1/auth",
            "research": "/api/v1/research",
            "features": "/api/features/public",
        }
    }

# ============================================================================
# STARTUP COMPLETE
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level="info",
    )
