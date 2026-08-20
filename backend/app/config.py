from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """SUTRA backend configuration. Override via environment or .env."""

    portal_base: str = "https://live.sentinelgujarat.in"
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    db_url: str = ""  # derived from data_dir when empty

    # Bridge sampler
    sample_interval_s: float = 0.5     # seconds between kept frames per camera (denser => better temporal voting)
    snapshot_every_s: float = 10.0     # seconds between JPEGs persisted to disk
    max_concurrent_cameras: int = 40   # safety cap on simultaneous ingest threads
    reconnect_backoff_s: float = 5.0
    file_sample_interval_s: float = 0.4  # video-time seconds between kept frames for file sources

    # Adaptive ingest scheduler (time-multiplexing under a concurrency budget)
    ingest_budget: int = 8            # max simultaneous live-stream connections (portal caps ~8-10)
    rotation_dwell_s: float = 90.0    # seconds a rotating camera keeps its slot (connect cost ~15-40s)
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

    # Auth
    jwt_secret: str = "sutra-sandbox-secret-rotate-in-production"
    token_ttl_s: int = 12 * 3600

    model_config = {"env_prefix": "SUTRA_", "env_file": ".env"}

    @property
    def database_url(self) -> str:
        return self.db_url or f"sqlite:///{self.data_dir / 'sutra.db'}"

    @property
    def frames_dir(self) -> Path:
        return self.data_dir / "frames"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.frames_dir.mkdir(parents=True, exist_ok=True)
