from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Camera(Base):
    """Atlas registry entry — one row per onboarded camera (Model 1)."""

    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(String, default="")
    department: Mapped[str] = mapped_column(String, default="Unassigned")
    district: Mapped[str] = mapped_column(String, default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    coords_approx: Mapped[bool] = mapped_column(Boolean, default=True)
    camera_type: Mapped[str] = mapped_column(String, default="")   # fixed|ptz|dome|bullet|anpr|analog
    ownership: Mapped[str] = mapped_column(String, default="government")  # government|private|society|commercial
    install_date: Mapped[str] = mapped_column(String, default="")  # YYYY-MM-DD; drives ageing analysis

    source_type: Mapped[str] = mapped_column(String, default="http-progressive")  # http-progressive|hls|rtsp|onvif|file
    source_url: Mapped[str] = mapped_column(String)
    codec: Mapped[str] = mapped_column(String, default="")
    container: Mapped[str] = mapped_column(String, default="")
    storage_type: Mapped[str] = mapped_column(String, default="unknown")
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String, default="unknown")  # live|offline|unknown
    monitoring: Mapped[bool] = mapped_column(Boolean, default=False)  # sampler enabled
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingest_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    health: Mapped[str] = mapped_column(String, default="unknown")  # ok|degraded|down|unknown
    health_detail: Mapped[str] = mapped_column(Text, default="")

    onboarded_via: Mapped[str] = mapped_column(String, default="manual")  # manual|bulk|api|discovery
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    detections: Mapped[list["Detection"]] = relationship(back_populates="camera")


class Detection(Base):
    """Insight output — one row per detected entity (vehicle/plate/person)."""

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    object_class: Mapped[str] = mapped_column(String, default="vehicle")  # car|truck|bike|person|...
    plate_text: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    plate_conf: Mapped[float | None] = mapped_column(Float, nullable=True)
    det_conf: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox: Mapped[str] = mapped_column(String, default="")  # "x1,y1,x2,y2"
    snapshot_path: Mapped[str] = mapped_column(String, default="")
    track_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    camera: Mapped[Camera] = relationship(back_populates="detections")


class WatchlistVehicle(Base):
    """Watch — representative watchlist entry (stolen/blacklisted/suspect vehicle)."""

    __tablename__ = "watchlist_vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plate: Mapped[str] = mapped_column(String, unique=True, index=True)  # normalised, e.g. GJ01AB1234
    reason: Mapped[str] = mapped_column(String, default="stolen")  # stolen|blacklisted|suspect|wanted
    fir_ref: Mapped[str] = mapped_column(String, default="")
    priority: Mapped[str] = mapped_column(String, default="high")  # high|medium|low
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_by: Mapped[str] = mapped_column(String, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    """Watch — fired when a detection matches a watchlist entry."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    detection_id: Mapped[int] = mapped_column(ForeignKey("detections.id"))
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlist_vehicles.id"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    severity: Mapped[str] = mapped_column(String, default="high")
    status: Mapped[str] = mapped_column(String, default="new")  # new|acknowledged|closed
    acked_by: Mapped[str | None] = mapped_column(String, nullable=True)

    detection: Mapped[Detection] = relationship()
    watchlist: Mapped[WatchlistVehicle] = relationship()


class User(Base):
    """RBAC principal: admin | operator (department-scoped) | viewer."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="viewer")
    department: Mapped[str] = mapped_column(String, default="")  # scopes operators
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Who did what, when — searches, exports, watchlist changes, acks."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String, default="system")
    action: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(Text, default="")
