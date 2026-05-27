from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

try:
    from . import search
except ImportError:
    import search


@asynccontextmanager
async def lifespan(app: FastAPI):
    search.startup()
    yield


app = FastAPI(title="Fly Fairly Airport Search API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/search")
def search_airports(
    q: str = Query(...),
    limit: int = Query(default=10, ge=1, le=100),
):
    if not q.strip():
        return {
            "query": q,
            "results": [],
            "total": 0,
            "search_types": [],
        }

    try:
        return search.search_airports(q, limit)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Airport search backend unavailable: {error}",
        ) from error


@app.get("/health")
def health():
    return {
        "status": "ok",
        "typesense": search.health_status(),
    }
