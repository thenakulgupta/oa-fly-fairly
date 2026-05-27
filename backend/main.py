from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

try:
    from . import search
except ImportError:
    import search


@asynccontextmanager
async def lifespan(app: FastAPI):
    search.startup()
    yield


RATE_LIMIT_WINDOW_SECONDS = 60

limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
app = FastAPI(title="Fly Fairly Airport Search API", lifespan=lifespan)
app.state.limiter = limiter


def calculate_retry_after_remaining(reset_timestamp: int | None) -> int:
    if reset_timestamp is None:
        return RATE_LIMIT_WINDOW_SECONDS

    try:
        return int(max(reset_timestamp - time.time(), 0))
    except Exception:
        return RATE_LIMIT_WINDOW_SECONDS


def read_rate_limit_from_request(request: Request) -> dict[str, int | None]:
    try:
        current_limit = request.state.view_rate_limit
        rate_limit_item, storage_args = current_limit
        reset_timestamp, remaining = limiter.limiter.get_window_stats(
            rate_limit_item,
            *storage_args,
        )
        reset_timestamp = int(reset_timestamp) + 1

    except Exception:
        return {
            "limit": None,
            "remaining": None,
            "reset_timestamp": None,
            "retry_after_remaining": RATE_LIMIT_WINDOW_SECONDS,
        }

    return {
        "limit": int(rate_limit_item.amount),
        "remaining": max(int(remaining), 0),
        "reset_timestamp": reset_timestamp,
        "retry_after_remaining": calculate_retry_after_remaining(reset_timestamp),
    }


def rate_limit_headers(rate_limit: dict[str, int | None]) -> dict[str, str]:
    headers = {}

    if rate_limit["limit"] is not None:
        headers["X-RateLimit-Limit"] = str(rate_limit["limit"])

    if rate_limit["remaining"] is not None:
        headers["X-RateLimit-Remaining"] = str(rate_limit["remaining"])

    if rate_limit["reset_timestamp"] is not None:
        headers["X-RateLimit-Reset"] = str(rate_limit["reset_timestamp"])

    headers["Retry-After"] = str(rate_limit["retry_after_remaining"])
    return headers


def success_rate_limit_block(request: Request, response: Response) -> dict[str, int | None]:
    return read_rate_limit_from_request(request)


@app.exception_handler(RateLimitExceeded)
def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    rate_limit = read_rate_limit_from_request(request)

    return JSONResponse(
        status_code=429,
        headers=rate_limit_headers(rate_limit),
        content={
            "error": "Too many requests",
            "retry_after_seconds": RATE_LIMIT_WINDOW_SECONDS,
            "retry_after_remaining": rate_limit["retry_after_remaining"],
            "rate_limit": rate_limit,
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/search")
@limiter.limit("30/minute")
def search_airports(
    request: Request,
    response: Response,
    q: str = Query(...),
    limit: int = Query(default=10, ge=1, le=100),
):
    rate_limit = success_rate_limit_block(request, response)

    if not q.strip():
        return {
            "query": q,
            "results": [],
            "total": 0,
            "search_types": [],
            "rate_limit": rate_limit,
        }

    try:
        result = search.search_airports(q, limit)
        result["rate_limit"] = rate_limit
        return result
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Airport search backend unavailable: {error}",
        ) from error


@app.get("/health")
@limiter.limit("10/minute")
def health(request: Request, response: Response):
    return {
        "status": "ok",
        "typesense": search.health_status(),
        "rate_limit": success_rate_limit_block(request, response),
    }


@app.get("/stats")
@limiter.limit("20/minute")
def stats(request: Request, response: Response):
    rate_limit = success_rate_limit_block(request, response)

    try:
        result = search.airport_stats()
        result["rate_limit"] = rate_limit
        return result
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Airport stats unavailable: {error}",
        ) from error
