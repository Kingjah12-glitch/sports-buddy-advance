import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app.routers import predictions
from app.routers import live_scores
from app.routers import matches
from app.services.ratings_store import get_state
from app.config import docs_enabled, extras_enabled
from app.services import sports_api

log = logging.getLogger("sports_buddy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the ratings in the background so the first page load is fast.

    There is deliberately NO background job that calls API-Football: the GitHub Action
    (daily.yml) refreshes results once a day. A server that wakes and sleeps (Render free tier)
    must never make provider calls on its own."""
    async def warm():
        try:
            await run_in_threadpool(get_state)
        except Exception as error:      # missing CSVs etc.: endpoints report it themselves
            app.state.warmup_error = str(error)
            log.warning("Ratings warm-up failed: %s", error)
    tasks = [asyncio.create_task(warm())]
    yield
    for task in tasks:
        task.cancel()


def allowed_origins() -> list[str]:
    """Local dev origins plus your website. Add more with ALLOWED_ORIGINS="https://a.io,https://b.io"
    (or "*" to allow any site; fine because the API is read-only and has no secrets)."""
    origins = ["http://127.0.0.1:5500", "http://localhost:5500", "http://127.0.0.1:5501",
               "http://localhost:5501", "https://kingjah12-glitch.github.io"]
    extra = [o.strip().rstrip("/") for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    return ["*"] if "*" in extra else origins + extra


app = FastAPI(
    title="Sports Buddy",
    description="Football market analysis and live scores.",
    version="1.2.0",
    lifespan=lifespan,
    # Public Swagger pages invite people to click "Execute" on every route; keep them off online.
    docs_url="/docs" if docs_enabled() else None,
    redoc_url=None,
    openapi_url="/openapi.json" if docs_enabled() else None,
)

# Allow the local frontend to communicate with the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(predictions.router)
if extras_enabled():                      # off by default, see app/config.py
    app.include_router(live_scores.router)
    app.include_router(matches.router)


@app.get("/")
def home():
    return {
        "app": "Sports Buddy",
        "status": "running",
        "message": "Welcome to Sports Buddy!",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/v1")
def api_info():
    return {
        "features": [
            "Football match analysis",
            "Goal market estimates",
            "Goal-market probabilities (V4 model) grouped by league",
            "Fair odds and value check against bookmaker prices",
            "No-bet recommendations",
            "Live scores",
        ]
    }


@app.get("/status", tags=["System"])
def status():
    """Plain-language health report: is the history, the model and the API key in place?"""
    from app.config import API_FOOTBALL_KEY
    from app.services import ratings_store
    state = ratings_store._state
    report = {
        "api_football_key_configured": bool(API_FOOTBALL_KEY),
        "history_and_ratings_ready": state is not None,
        "warmup_error": getattr(app.state, "warmup_error", None),
        "provider_usage": sports_api.usage(),
    }
    if state is not None:
        report.update({
            "data_through": str(state.last_date),
            "competitions": len(state.teams_by_group),
            "model_v4_loaded": state.model is not None,
            "outcome_model_loaded": state.outcome_model is not None,
            "calibration_loaded": bool(state.calibrators),
        })
    else:
        report["note"] = ("Still starting up (building ratings takes ~10 seconds)"
                          if not report["warmup_error"] else "Start-up failed: see warmup_error")
    return report
