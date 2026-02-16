"""
Backend configuration using pydantic-settings.
"""

from pydantic_settings import BaseSettings


class WebConfig(BaseSettings):
    """Web backend configuration."""

    # Server
    web_host: str = "0.0.0.0"
    web_port: int = 8000

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Database (reused from bot)
    database_url: str = "sqlite+aiosqlite:///traderagent.db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Bot config
    config_path: str = "configs/production.yaml"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


web_config = WebConfig()
