"""
Settings API endpoints.
"""

from fastapi import APIRouter, Depends

from web.backend.auth.models import User
from web.backend.dependencies import get_current_admin, get_current_user
from web.backend.schemas.common import SuccessResponse

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("/config")
async def get_config(
    _: User = Depends(get_current_user),
):
    """Get application config (redacted secrets)."""
    return {
        "monitoring": {
            "metrics_port": 9100,
            "alerts_port": 8080,
        },
        "web": {
            "port": 8000,
        },
    }


@router.get("/notifications")
async def get_notifications(
    _: User = Depends(get_current_user),
):
    """Get notification configuration."""
    return {
        "telegram_configured": False,
        "notify_on_trade": True,
        "notify_on_error": True,
        "notify_on_alert": True,
    }


@router.put("/notifications", response_model=SuccessResponse)
async def update_notifications(
    config: dict,
    _: User = Depends(get_current_admin),
):
    """Update notification configuration."""
    return SuccessResponse(message="Notifications updated")
