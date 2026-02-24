"""
FastAPI application factory.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import Response

from web.backend.config import web_config
from web.backend.rate_limit import limiter


def create_app(bot_app=None) -> FastAPI:
    """Create FastAPI application with optional shared BotApplication."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan: initialize shared bot components."""
        if bot_app:
            # Shared mode: bot_app already initialized externally
            app.state.db_manager = bot_app.db_manager
            app.state.orchestrators = bot_app.orchestrators
            app.state.config_manager = bot_app.config_manager
        else:
            # Standalone mode: initialize BotApplication
            from bot.main import BotApplication

            _bot_app = BotApplication()
            try:
                await _bot_app.initialize()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "BotApplication init failed (web-only mode): %s", e
                )
            app.state.db_manager = _bot_app.db_manager
            app.state.orchestrators = getattr(_bot_app, "orchestrators", {})
            app.state.config_manager = _bot_app.config_manager
            app.state._bot_app = _bot_app

        # Create web-specific tables (users, sessions)
        if app.state.db_manager and app.state.db_manager._engine:
            from bot.database.models import Base, BotStateSnapshot  # noqa: F401
            from web.backend.auth.models import User, UserSession  # noqa: F401

            async with app.state.db_manager._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        # Start Redis → WebSocket bridge
        redis_bridge = None
        try:
            from web.backend.ws.events import RedisBridge
            from web.backend.ws.router import manager as ws_manager

            redis_bridge = RedisBridge(
                redis_url=web_config.redis_url,
                manager=ws_manager,
            )
            await redis_bridge.start()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "RedisBridge start failed (WebSocket events disabled): %s", e
            )

        yield

        # Stop Redis bridge
        if redis_bridge:
            await redis_bridge.stop()

        # Cleanup standalone bot_app
        if not bot_app and hasattr(app.state, "_bot_app"):
            await app.state._bot_app.cleanup()

    app = FastAPI(
        title="TRADERAGENT Web API",
        description="Web UI Dashboard API for TRADERAGENT trading bot",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=web_config.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting (60 req/min default for all endpoints)
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
        response = JSONResponse(
            {"detail": f"Rate limit exceeded: {exc.detail}"},
            status_code=429,
        )
        response = request.app.state.limiter._inject_headers(
            response, request.state.view_rate_limit
        )
        response.headers["Retry-After"] = str(60)
        return response

    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # Include routers
    from web.backend.api.v1.router import v1_router
    from web.backend.auth.router import router as auth_router
    from web.backend.ws.router import router as ws_router

    app.include_router(auth_router)
    app.include_router(v1_router)
    app.include_router(ws_router)

    # Health check
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
