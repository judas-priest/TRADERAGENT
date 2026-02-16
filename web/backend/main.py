"""
Web backend entry point.
Run: uvicorn web.backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

from web.backend.app import create_app

app = create_app()


if __name__ == "__main__":
    import uvicorn

    from web.backend.config import web_config

    uvicorn.run(
        "web.backend.main:app",
        host=web_config.web_host,
        port=web_config.web_port,
        reload=True,
    )
