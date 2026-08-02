"""
Public feature flags and platform capabilities endpoints.
"""
from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/api/features", tags=["features"])

@router.get("/public", response_model=Dict[str, Any])
@router.get("/v1/features/public", response_model=Dict[str, Any])
async def get_public_features() -> Dict[str, Any]:
    """
    Returns public feature flags and platform capabilities.
    Prevents 404 errors when clients request feature configuration.
    """
    return {
        "status": "active",
        "features": {
            "research_analysis": True,
            "market_data": True,
            "sentiment_pulse": True,
            "theme_analysis": True,
            "guest_access": True,
        }
    }
