import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, engine
from .routers import atlas, auth, bridge, insight, watch
from .security import seed_default_users
from .services import sampler
from .services.insight import engine as insight_engine
from .services.scheduler import engine as ingest_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    if settings.insight_enabled:
        insight_engine.start()
        sampler.frame_subscribers.append(insight_engine.on_frame)
    from .db import SessionLocal

    db = SessionLocal()
    try:
        seed_default_users(db)
    finally:
        db.close()
    # the scheduler reconciles the monitoring pool against the concurrency
    # budget — this also resumes ingestion after a restart
    ingest_scheduler.start()
    yield
    ingest_scheduler.stop_flag.set()
    insight_engine.stop()
    sampler.stop_all()


app = FastAPI(
    title="SUTRA",
    description="Statewide Unified Tracking, Registry & Analytics — "
    "Gujarat Police CCTV Integration Hackathon 2026",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototype only — restrict before hosting
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(atlas.router)
app.include_router(bridge.router)
app.include_router(insight.router)
app.include_router(watch.router)

# evidence snapshots (detection crops, alert frames)
app.mount("/data", StaticFiles(directory=settings.data_dir), name="data")


@app.get("/api/health")
def health():
    return {"service": "sutra", "status": "ok", "ingest_workers": len(sampler.worker_status())}
