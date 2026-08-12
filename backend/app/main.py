"""FastAPI application entrypoint.

Boot order matters: configure logging first, then build the app, register the
request-logging middleware, exception handlers, and mount routers under
``/api/v1``.  Everything below ``/api/v1`` except health checks and auth
requires a valid Supabase JWT via the dependency layer.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import configure_logging, get_logger
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks.  Verifies DB connectivity, never logs the URL."""
    configure_logging()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("database connectivity ok")
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("database connectivity check failed: %s", type(exc).__name__)
    logger.info("starting %s (env=%s)", settings.APP_NAME, settings.ENVIRONMENT)
    yield
    logger.info("shutdown complete")


is_production = settings.ENVIRONMENT.lower() == "production"

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Backend API for AI Employee OS. Authentication is Supabase JWT.",
    lifespan=lifespan,
    # Never expose the interactive Swagger/ReDoc docs in production.
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

# Allow the Next.js frontend to call the API from the browser.
# FRONTEND_ORIGIN may be a single origin or a comma-separated list.
_allowed_origins = [
    o.strip()
    for o in (
        str(settings.FRONTEND_ORIGIN or "").split(",")
        + ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(_allowed_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuditMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.debug("validation_error path=%s errors=%s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request payload", "errors": exc.errors()},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last-resort handler so clients never receive raw stack traces."""
    logger.exception("unhandled error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(router, prefix="/api/v1")


from app.api.v1.health.routes import router as health_router  # noqa: E402

app.include_router(health_router, prefix="/health", tags=["Health"])


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "status": "running"}