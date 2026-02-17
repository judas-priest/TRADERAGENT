"""
Settings API endpoints.
"""

from fastapi import APIRouter, Depends, Request

from web.backend.auth.models import User
from web.backend.dependencies import get_current_admin, get_current_user
from web.backend.schemas.common import SuccessResponse

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("/config")
async def get_config(
    request: Request,
    _: User = Depends(get_current_user),
):
    """Get application config (redacted secrets)."""
    config_manager = getattr(request.app.state, "config_manager", None)

    if config_manager:
        try:
            app_config = config_manager.get_config()
            return {
                "monitoring": {
                    "metrics_port": 9100,
                    "alerts_port": 8080,
                },
                "web": {
                    "port": 8000,
                },
                "logging": {
                    "level": app_config.log_level,
                    "to_file": app_config.log_to_file,
                    "to_console": app_config.log_to_console,
                    "json_logs": app_config.json_logs,
                },
                "database": {
                    "pool_size": app_config.database_pool_size,
                },
                "bots_count": len(app_config.bots),
            }
        except Exception:
            pass

    # Fallback when config_manager is not available
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
    request: Request,
    _: User = Depends(get_current_user),
):
    """Get notification configuration."""
    config_manager = getattr(request.app.state, "config_manager", None)

    telegram_configured = False
    if config_manager:
        try:
            app_config = config_manager.get_config()
            # Check if any bot has telegram configured
            for bot in app_config.bots:
                if getattr(bot, "telegram", None):
                    telegram_configured = True
                    break
        except Exception:
            pass

    return {
        "telegram_configured": telegram_configured,
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
    # TODO: Persist notification preferences to database
    return SuccessResponse(message="Notifications updated")
