from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CameraBase(BaseModel):
    name: str
    location: str = ""
    department: str = "Unassigned"
    district: str = ""
    lat: float | None = None
    lon: float | None = None
    source_type: str = "http-progressive"
    source_url: str
    codec: str = ""
    container: str = ""
    storage_type: str = "unknown"
    retention_days: int | None = None


class CameraCreate(CameraBase):
    external_id: str


class CameraUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    department: str | None = None
    district: str | None = None
    lat: float | None = None
    lon: float | None = None
    source_type: str | None = None
    source_url: str | None = None
    monitoring: bool | None = None
    retention_days: int | None = None


class CameraOut(CameraBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    coords_approx: bool
    status: str
    monitoring: bool
    last_frame_at: datetime | None
    ingest_fps: float | None
    health: str
    health_detail: str
    onboarded_via: str


class WatchlistCreate(BaseModel):
    plate: str
    reason: str = "stolen"
    fir_ref: str = ""
    priority: str = "high"
    notes: str = ""


class WatchlistOut(WatchlistCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    active: bool
    added_by: str
    created_at: datetime


class DetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    ts: datetime
    object_class: str
    plate_text: str | None
    plate_conf: float | None
    det_conf: float | None
    bbox: str
    snapshot_path: str
    track_id: str | None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    detection_id: int
    watchlist_id: int
    ts: datetime
    severity: str
    status: str
    acked_by: str | None
