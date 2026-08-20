import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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
    from .db import migrate_sqlite

    migrate_sqlite()
    if settings.insight_enabled:
        insight_engine.start()
        sampler.frame_subscribers.append(insight_engine.on_frame)
    if settings.scene_enabled and (settings.data_dir / "models" / "yolox_nano.onnx").exists():
        from .services.objects import scene

        scene.start()
        sampler.frame_subscribers.append(scene.on_frame)
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
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

app.include_router(auth.router)
app.include_router(atlas.router)
app.include_router(bridge.router)
app.include_router(insight.router)
app.include_router(watch.router)

# evidence snapshots (detection crops, alert frames) — authenticated, path-safe
_DATA_ROOT = Path(settings.data_dir).resolve()


@app.get("/data/{rel_path:path}")
def evidence_file(rel_path: str, request: Request):
    from .security import verify_media_access

    if not verify_media_access(request):
        raise HTTPException(401, "not authenticated")
    target = (_DATA_ROOT / rel_path).resolve()
    # confine to the data directory and to image evidence only
    if _DATA_ROOT not in target.parents or target.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(404, "not found")
    if not target.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(target, headers={"Cache-Control": "private, max-age=300"})


@app.get("/api/health")
def health():
    return {"service": "sutra", "status": "ok", "ingest_workers": len(sampler.worker_status())}
