import asyncio
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from aura.api.deps import get_ollama_client
from aura.api.routes import chat, health, models, ws
from aura.config import get_config
from aura.events import get_event_bus


def configure_logging():
    """
    Configures structlog for JSON output.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds a unique request ID and logs request details.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        # Attach request ID to context for structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
            )
            raise e

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        
        logger.info(
            "request_finished",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown logic for the Aura Core API.
    """
    # 1. Configure Logging
    configure_logging()
    
    # 2. Start Event Bus Dispatch Loop
    event_bus = get_event_bus()
    dispatch_task = asyncio.create_task(event_bus.dispatch_loop())
    
    # 3. Setup WebSocket Forwarding
    await ws.forward_events_to_ws()
    
    # 4. Verify Ollama Health with Retries
    ollama_client = get_ollama_client()
    ollama_ready = False
    logger.info("waiting_for_ollama")
    
    for i in range(30):
        if await ollama_client.health():
            ollama_ready = True
            logger.info("ollama_connected")
            break
        await asyncio.sleep(1)
        
    if not ollama_ready:
        logger.warning("ollama_connection_timeout", message="Core starting anyway, but Ollama features may fail.")

    # Store startup time for health endpoint
    app.state.start_time = time.time()
    
    yield
    
    # Shutdown logic
    dispatch_task.cancel()
    try:
        await dispatch_task
    except asyncio.CancelledError:
        pass
    logger.info("aura_core_shutdown")


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.
    """
    config = get_config()
    
    app = FastAPI(
        title="Aura Core",
        description="Privacy-first AI desktop layer",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restricted by localhost binding but allowing for local UI
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LoggingMiddleware)

    # Routes
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(ws.router)
    app.include_router(models.router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    config = get_config()
    logger.info("starting_aura_core", port=config.core_port)
    uvicorn.run(app, host="127.0.0.1", port=config.core_port, log_level="info")
