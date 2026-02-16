"""
FastAPI dependency injection.
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from web.backend.auth.models import User
from web.backend.auth.service import decode_access_token, get_user_by_id

security = HTTPBearer(auto_error=False)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get database session from app state."""
    db_manager = request.app.state.db_manager
    async with db_manager.session() as session:
        yield session


def get_orchestrators(request: Request) -> dict:
    """Get bot orchestrators from app state."""
    return request.app.state.orchestrators


def get_config_manager(request: Request):
    """Get config manager from app state."""
    return request.app.state.config_manager


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    """Extract and validate JWT token, return current user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload["sub"])
    db_manager = request.app.state.db_manager
    async with db_manager.session() as session:
        user = await get_user_by_id(session, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or disabled",
            )
        return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
