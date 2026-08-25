from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """SUTRA backend configuration. Override via environment or .env."""

    # Deployment role — mirrors the tiering in the HLD:
    #   full    single machine does everything (development / on-prem all-in-one)
    #   edge    ingest + inference only; pushes metadata upstream to a central tier
    #   central command centre + registry + evidence; no video decode, no models
    #           (this is what runs on a small cloud instance)
    role: str = "full"
    central_url: str = ""        # edge -> where to push metadata
    sync_api_key: str = ""       # shared secret for the edge->central channel
    sync_interval_s: float = 30.0

    portal_base: str = "https://live.corp8.cloud"   # hackathon feed portal (moved from live.sentinelgujarat.in)
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    db_url: str = ""  # derived from data_dir when empty

    # Bridge sampler
    # 1 fps per camera keeps analytics load linear as the budget grows: 20
    # cameras cost ~0.7 of a core for ANPR, where 0.5 s sampling would cost 1.5.
    sample_interval_s: float = 1.0
    snapshot_every_s: float = 10.0     # seconds between JPEGs persisted to disk
    max_concurrent_cameras: int = 40   # safety cap on simultaneous ingest threads
    reconnect_backoff_s: float = 5.0
    file_sample_interval_s: float = 0.4  # video-time seconds between kept frames for file sources

    # Adaptive ingest scheduler (time-multiplexing under a concurrency budget)
    # Max simultaneous live-stream connections.
    #
    # Sized to the *source*, not to this node. The portal answers cheap range
    # requests happily (16/16) but sustains only a couple of concurrent decode
    # sessions, and the number varies minute to minute: independent FFmpeg
    # processes bypassing this code entirely decoded 6/12 on one attempt and
    # 2/6 on the next. Over-provisioning slots against that just multiplies
    # failing connections, so the budget stays modest and the scheduler rotates
    # every camera through it — all 30 get covered over time instead of 30
    # fighting for a handful of sessions at once.
    ingest_budget: int = 10
    # How long a rotating camera keeps its slot. Connecting to this portal costs
    # ~48 s before the first frame arrives, so a short dwell spends the whole
    # slot connecting and rotates away just as pictures start: a camera that has
    # successfully connected should keep streaming for a good while.
    rotation_dwell_s: float = 600.0
    alert_boost_s: float = 300.0      # alert camera + neighbours stay resident this long
    boost_neighbors: int = 3          # nearest cameras boosted alongside an alert camera
    connect_stagger_s: float = 1.5    # gap between connection attempts in one tick
    scheduler_tick_s: float = 5.0

    # Insight ANPR pipeline
    insight_enabled: bool = True
    plate_detector_model: str = "yolo-v9-t-640-license-plate-end2end"
    plate_ocr_model: str = "cct-s-v2-global-model"
    plate_det_min_conf: float = 0.35
    plate_ocr_min_conf: float = 0.55   # below this a read is not persisted (fuzzy matching absorbs marginal reads)
    inference_workers: int = 2
    inference_queue_size: int = 64
    detection_dedup_s: float = 20.0    # same plate+camera within window → update, not insert
    alert_cooldown_s: float = 900.0    # same plate+camera alert suppression (a parked
                                       # watchlist vehicle must not spam the operator)

    # Scene analytics (person/vehicle counting sidecar)
    scene_enabled: bool = True
    scene_interval_s: float = 20.0     # min seconds between scene analyses per camera

    # Retention housekeeping (central tier background task)
    evidence_budget_mb: int = 400          # keep well inside a 1 GB managed database
    detection_retention_days: int = 90     # metadata is small; imagery is the expensive part
    retention_interval_s: float = 3600.0

    # Auth
    jwt_secret: str = ""          # empty => auto-generated per install (data/.jwt_secret)
    token_ttl_s: int = 12 * 3600
    media_token_ttl_s: int = 12 * 3600
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # optional seed-password overrides (else generated defaults are logged as a warning)
    seed_admin_pw: str = ""
    seed_operator_pw: str = ""
    seed_viewer_pw: str = ""

    model_config = {"env_prefix": "SUTRA_", "env_file": ".env"}

    @property
    def database_url(self) -> str:
        url = self.db_url or f"sqlite:///{self.data_dir / 'sutra.db'}"
        # managed Postgres providers hand out postgres:// URLs; SQLAlchemy 2 wants postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def is_central(self) -> bool:
        return self.role == "central"

    @property
    def runs_ingest(self) -> bool:
        return self.role in ("full", "edge")

    @property
    def frames_dir(self) -> Path:
        return self.data_dir / "frames"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.frames_dir.mkdir(parents=True, exist_ok=True)

# JWT secret: never a hardcoded default. Use the env-provided value, else an
# auto-generated per-install secret persisted outside version control.
if not settings.jwt_secret:
    _keyfile = settings.data_dir / ".jwt_secret"
    if _keyfile.exists():
        settings.jwt_secret = _keyfile.read_text().strip()
    else:
        import secrets as _secrets

        settings.jwt_secret = _secrets.token_urlsafe(48)
        _keyfile.write_text(settings.jwt_secret)
