"""
Aggregate v1 API router.
"""

from fastapi import APIRouter

from web.backend.api.v1.bots import router as bots_router
from web.backend.api.v1.dashboard import router as dashboard_router

v1_router = APIRouter()
v1_router.include_router(bots_router)
v1_router.include_router(dashboard_router)
