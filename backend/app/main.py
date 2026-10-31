import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import make_engine
from .models import Idea

logger = logging.getLogger("idea_board")
REQUESTS = Counter(
    "idea_board_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
LATENCY = Histogram("idea_board_http_duration_seconds", "Request latency", ["route"])


@asynccontextmanager
async def lifespan(app):
    app.state.engine = make_engine()
    yield
    app.state.engine.dispose()


app = FastAPI(title="Idea Board API", version="1.0.0", lifespan=lifespan)


def session(request: Request):
    with Session(request.app.state.engine) as db:
        yield db


class IdeaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content", mode="before")
    @classmethod
    def trim_content(cls, value):
        return value.strip() if isinstance(value, str) else value


class IdeaOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    content: str
    created_at: datetime


@app.middleware("http")
async def metrics(request: Request, call_next):
    start = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        REQUESTS.labels(request.method, route, str(status)).inc()
        LATENCY.labels(route).observe(time.monotonic() - start)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    # Never expose database connection strings or SQL parameters in responses/logs.
    logger.error("Database operation failed: %s", type(exc).__name__)
    return Response(
        '{"detail":"Database temporarily unavailable"}',
        status_code=503,
        media_type="application/json",
    )


@app.get("/health/live", include_in_schema=False)
def live():
    return {"status": "ok"}


@app.get("/health/release", include_in_schema=False)
def release():
    return {"release_id": os.environ.get("RELEASE_ID", "local")}


@app.get("/health/ready", include_in_schema=False)
def ready(db: Session = Depends(session)):
    try:
        db.execute(text("SELECT 1 FROM ideas LIMIT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Database unavailable or not migrated"
        ) from None
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics_endpoint():
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})


@app.get("/api/ideas", response_model=list[IdeaOutput])
def list_ideas(db: Session = Depends(session)):
    return db.scalars(
        select(Idea).order_by(Idea.created_at.desc(), Idea.id.desc())
    ).all()


@app.post("/api/ideas", response_model=IdeaOutput, status_code=201)
def create_idea(idea: IdeaInput, db: Session = Depends(session)):
    record = Idea(content=idea.content)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
