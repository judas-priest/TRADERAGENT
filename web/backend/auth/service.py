"""
Authentication service: JWT tokens, password hashing.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from web.backend.auth.models import User, UserSession
from web.backend.config import web_config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=web_config.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, web_config.jwt_secret, algorithm=web_config.jwt_algorithm)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token, web_config.jwt_secret, algorithms=[web_config.jwt_algorithm]
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(User.id)))
    return result.scalar_one()


async def create_user_session(
    session: AsyncSession,
    user_id: int,
    refresh_token: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserSession:
    token_hash = hash_refresh_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=web_config.jwt_refresh_token_expire_days
    )
    user_session = UserSession(
        user_id=user_id,
        refresh_token_hash=token_hash,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(user_session)
    await session.flush()
    return user_session


async def validate_refresh_token(
    session: AsyncSession, refresh_token: str
) -> UserSession | None:
    token_hash = hash_refresh_token(refresh_token)
    result = await session.execute(
        select(UserSession).where(
            UserSession.refresh_token_hash == token_hash,
            UserSession.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(session: AsyncSession, refresh_token: str) -> None:
    token_hash = hash_refresh_token(refresh_token)
    await session.execute(
        delete(UserSession).where(UserSession.refresh_token_hash == token_hash)
    )
