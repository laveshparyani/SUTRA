import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
    from .db import migrate_schema

    migrate_schema()
    logging.getLogger("sutra").info("starting in role=%s", settings.role)

    # The central tier serves the command centre only: no decoders, no models,
    # no scheduler — that is what keeps it inside a small cloud instance.
    if settings.runs_ingest:
        if settings.insight_enabled:
            insight_engine.start()
            sampler.frame_subscribers.append(insight_engine.on_frame)
        if settings.scene_enabled and (settings.data_dir / "models" / "yolox_nano.onnx").exists():
            from .services.objects import scene

            scene.start()
            sampler.frame_subscribers.append(scene.on_frame)
        if settings.central_url and settings.sync_api_key:
            from .services.syncer import syncer

            syncer.start()
    if settings.is_central:
        # the centre accumulates evidence indefinitely otherwise
        from .services.retention import retention

        retention.start()
    from .db import SessionLocal

    db = SessionLocal()
    try:
        seed_default_users(db)
    finally:
        db.close()
    # the scheduler reconciles the monitoring pool against the concurrency
    # budget — this also resumes ingestion after a restart
    if settings.runs_ingest:
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
if settings.is_central:
    from .routers import sync

    app.include_router(sync.router)
app.include_router(bridge.router)
app.include_router(insight.router)
app.include_router(watch.router)

# evidence snapshots (detection crops, alert frames) — authenticated, path-safe
_DATA_ROOT = Path(settings.data_dir).resolve()


@app.get("/data/{rel_path:path}")
def evidence_file(rel_path: str, request: Request):
    """Serve detection/alert imagery.

    Edge and all-in-one nodes hold evidence on local disk. The central tier's
    disk is ephemeral, so its evidence lives in the database — checked first,
    with the filesystem as fallback.
    """
    from fastapi.responses import Response

    from .db import SessionLocal
    from .models import Evidence
    from .security import verify_media_access

    if not verify_media_access(request):
        raise HTTPException(401, "not authenticated")

    db = SessionLocal()
    try:
        row = db.query(Evidence).filter(Evidence.path == rel_path).one_or_none()
        if row:
            return Response(
                content=row.content,
                media_type=row.content_type,
                headers={"Cache-Control": "private, max-age=300"},
            )
    finally:
        db.close()

    target = (_DATA_ROOT / rel_path).resolve()
    # confine to the data directory and to image evidence only
    if _DATA_ROOT not in target.parents or target.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(404, "not found")
    if not target.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(target, headers={"Cache-Control": "private, max-age=300"})


@app.get("/api/health")
def health():
    return {
        "service": "sutra",
        "status": "ok",
        "role": settings.role,
        "ingest_workers": len(sampler.worker_status()),
    }


@app.get("/api/system")
def system_status(request: Request):
    """Operational view of every background task on this node."""
    from .security import verify_media_access

    if not verify_media_access(request):
        raise HTTPException(401, "not authenticated")

    tasks: dict = {"role": settings.role}
    if settings.runs_ingest:
        tasks["ingest_scheduler"] = ingest_scheduler.status()
        tasks["analytics"] = insight_engine.stats()
        if settings.central_url and settings.sync_api_key:
            from .services.syncer import syncer

            tasks["edge_sync"] = syncer.status()
        else:
            tasks["edge_sync"] = {"enabled": False}
    if settings.is_central:
        from .services.retention import retention

        tasks["retention"] = retention.status()
    return tasks


# In a single-service deployment (e.g. the central tier on a small cloud
# instance) the API also serves the built Command UI. Mounted last so it never
# shadows /api or /data.
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="ui")

    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc):
        """Client-side routes (/trace, /alerts…) must return the SPA shell."""
        if request.url.path.startswith(("/api", "/data")):
            return JSONResponse({"detail": "not found"}, status_code=404)
        return FileResponse(_FRONTEND_DIST / "index.html")
