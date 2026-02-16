"""
Tests for auth endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """Test health endpoint."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_register_first_user_is_admin(client: AsyncClient):
    """First registered user should be admin."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "admin1",
            "email": "admin1@example.com",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "admin1"
    assert data["is_admin"] is True


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """Duplicate username should fail."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "dupuser",
            "email": "dup1@example.com",
            "password": "securepass123",
        },
    )
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "dupuser",
            "email": "dup2@example.com",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    """Short password should be rejected."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "shortpw",
            "email": "shortpw@example.com",
            "password": "short",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Login with correct credentials should succeed."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "securepass123",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "loginuser", "password": "securepass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Login with wrong password should fail."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "wrongpw",
            "email": "wrongpw@example.com",
            "password": "securepass123",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "wrongpw", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Login with nonexistent user should fail."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "noexist", "password": "whatever123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    """Refresh token should return new tokens."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "refreshuser",
            "email": "refresh@example.com",
            "password": "securepass123",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "refreshuser", "password": "securepass123"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Old token should be rotated
    assert data["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    """Invalid refresh token should fail."""
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-token-here"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    """Unauthenticated /me should return 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(auth_client: AsyncClient):
    """Authenticated /me should return user profile."""
    resp = await auth_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"
    assert data["is_admin"] is True


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Logout should invalidate refresh token."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "logoutuser",
            "email": "logout@example.com",
            "password": "securepass123",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "logoutuser", "password": "securepass123"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Logout
    resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 204

    # Try to use the old refresh token
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 401
