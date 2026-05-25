"""
FastAPI application factory: creates the app, adds middleware, registers routes.
"""

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from agentmatrix import __version__
from .lifecycle import lifespan
from .routes import register_all_routes


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AgentMatrix",
        description="An intelligent agent framework with pluggable skills and LLM integrations",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS middleware for Tauri desktop app
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request timing middleware
    @app.middleware("http")
    async def add_timing_header(request: Request, call_next):
        """Add request timing header, log slow requests (>100ms)"""
        start = time.time()
        response = await call_next(request)
        process_time = time.time() - start
        response.headers["X-Process-Time"] = f"{process_time:.3f}"

        if process_time > 0.1:
            print(
                f"⚠️ Slow request: {request.method} {request.url.path} took {process_time:.3f}s"
            )

        return response

    # Register all route modules
    register_all_routes(app)

    return app
