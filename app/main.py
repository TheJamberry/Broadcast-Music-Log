import asyncio
import logging
import logging.config
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import settings
from .db import Play, SessionLocal, Song, Station, init_db
from .monitor import monitor_loop

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "root": {"handlers": ["console"], "level": "INFO"},
        # Set to DEBUG for the app's own modules only.
        "loggers": {
            "app": {"level": "DEBUG", "propagate": True},
        },
    }
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — replaces the deprecated @app.on_event("startup/shutdown")
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stop_event = asyncio.Event()
    monitor_task = asyncio.create_task(monitor_loop(stop_event))
    app.state.stop_event = stop_event
    app.state.monitor_task = monitor_task
    logger.info("Broadcast Music Logger started.")
    yield
    logger.info("Shutting down — waiting for monitor loop to finish...")
    stop_event.set()
    await monitor_task
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Broadcast Music Logger", lifespan=lifespan)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def get_db():
    with SessionLocal() as session:
        yield session


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    now = datetime.utcnow()
    today = datetime(now.year, now.month, now.day)
    week_ago = now - timedelta(days=7)

    recent_play = (
        db.query(Play)
        .order_by(Play.detected_at.desc())
        .limit(1)
        .first()
    )

    song_stats = (
        db.query(
            Song,
            func.count(Play.id).label("play_count"),
            func.max(Play.detected_at).label("last_played"),
        )
        .join(Play)
        .group_by(Song.id)
        .order_by(func.count(Play.id).desc())
        .all()
    )

    total_plays_today = (
        db.query(func.count(Play.id)).filter(Play.detected_at >= today).scalar() or 0
    )
    total_plays_week = (
        db.query(func.count(Play.id)).filter(Play.detected_at >= week_ago).scalar() or 0
    )
    play_history = (
        db.query(Play)
        .order_by(Play.detected_at.desc())
        .limit(100)
        .all()
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "recent_play": recent_play,
            "song_stats": song_stats,
            "plays_today": total_plays_today,
            "plays_week": total_plays_week,
            "play_history": play_history,
        },
    )
