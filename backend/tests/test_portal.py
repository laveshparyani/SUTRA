"""The feed portal moved behind a login (Sep 2026): the catalogue is
`/cameras.json`, RTSP wants credentials in the URL, HLS wants a session
cookie plus a browser UA. Credentials must never reach the registry, the
logs, or an operator's screen."""

import pytest

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Camera
from app.services import discovery, portal
from app.services.ffreader import FFmpegFrameReader, is_join_noise


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setattr(settings, "portal_email", "ops@example.in")
    monkeypatch.setattr(settings, "portal_password", "AB12-CD34-EF56")
    monkeypatch.setattr(portal, "_cookie", {})
    yield


@pytest.fixture
def no_creds(monkeypatch):
    monkeypatch.setattr(settings, "portal_email", "")
    monkeypatch.setattr(settings, "portal_password", "")
    monkeypatch.setattr(portal, "_cookie", {})
    yield


def test_catalogue_record_maps_to_credential_free_rtsp_source():
    meta = discovery._metadata({"id": "cam04", "name": "04 Paldi Circle"})
    assert meta["name"] == "Paldi Circle"
    assert meta["location"] == "04 Paldi Circle"
    assert meta["source_type"] == "rtsp"
    assert meta["source_url"] == f"rtsp://{settings.portal_rtsp_host}:{settings.portal_rtsp_port}/stream/cam04"
    assert "@" not in meta["source_url"]
    assert meta["alt_hls_url"] == f"{settings.portal_base}/cam04/index.m3u8"


def test_grid_ids_keep_the_original_registry_identity():
    # "cam07" is the camera the first portal published as id 7: the same
    # external_id means its detection history stays attached
    assert discovery.external_id_for("cam07") == "sentinel-7"
    assert discovery.external_id_for("cam30") == "sentinel-30"
    assert discovery.external_id_for("weird") == "sentinel-weird"


def test_upsert_updates_existing_rows_and_retires_unlisted_ones():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        for ext in ("sentinel-4", "sentinel-99"):
            db.query(Camera).filter(Camera.external_id == ext).delete()
        old = Camera(external_id="sentinel-4", name="Camera 4", location="04 Paldi Circle",
                     source_type="http-progressive", source_url="https://old.example/stream/4",
                     codec="h264", status="live", monitoring=True)
        gone = Camera(external_id="sentinel-99", name="Camera 99", source_url="x", status="live",
                      monitoring=True)
        db.add_all([old, gone])
        db.commit()
        old_id = old.id

        result = discovery.upsert_cameras(db, [{"id": "cam04", "name": "04 Paldi Circle"}])

        assert result["updated"] == 1 and result["created"] == 0
        row = db.query(Camera).filter(Camera.external_id == "sentinel-4").one()
        assert row.id == old_id                      # same row, history intact
        assert row.source_type == "rtsp"
        assert row.source_url.startswith("rtsp://")
        assert row.codec == "h264"                   # the catalogue carries no codec; keep what we knew
        retired = db.query(Camera).filter(Camera.external_id == "sentinel-99").one()
        assert retired.status == "offline" and retired.monitoring is False
    finally:
        db.rollback()
        for ext in ("sentinel-4", "sentinel-99"):
            db.query(Camera).filter(Camera.external_id == ext).delete()
        db.commit()
        db.close()


def test_rtsp_credentials_are_injected_only_for_the_portal_gateway(creds):
    url = f"rtsp://{settings.portal_rtsp_host}:{settings.portal_rtsp_port}/stream/cam04"
    auth = portal.authenticate_url(url)
    assert auth.startswith("rtsp://ops%40example.in:AB12-CD34-EF56@")
    assert auth.endswith("/stream/cam04")
    # idempotent, and other cameras are not touched
    assert portal.authenticate_url(auth) == auth
    other = "rtsp://192.168.1.20:554/live"
    assert portal.authenticate_url(other) == other


def test_credentials_never_survive_redaction(creds):
    auth = portal.authenticate_url(
        f"rtsp://{settings.portal_rtsp_host}:{settings.portal_rtsp_port}/stream/cam04"
    )
    assert "AB12-CD34-EF56" not in portal.redact_url(auth)
    assert "ops%40example.in" not in portal.redact_url(auth)
    line = f"[rtsp @ 0x1] method DESCRIBE failed for {auth}"
    assert "AB12-CD34-EF56" not in portal.redact(line)
    assert "ops@example.in" not in portal.redact(line.replace("ops%40", "ops@"))


def test_missing_credentials_are_reported_not_hidden(no_creds):
    with pytest.raises(portal.PortalAuthError):
        portal.login()
    # a non-portal URL needs no session, so ingest of other cameras carries on
    assert portal.http_headers("rtsp://192.168.1.20:554/live") == {}


def test_discover_endpoint_explains_a_missing_portal_login(client, admin, no_creds):
    r = client.post("/api/atlas/discover", headers=admin)
    assert r.status_code == 502
    assert "credentials" in r.json()["detail"]


def test_join_time_decoder_noise_is_not_an_error():
    assert is_join_noise("[hevc @ 0x1] Could not find ref with POC 12")
    assert is_join_noise("[h264 @ 0x1] non-existing PPS 0 referenced")
    assert not is_join_noise("rtsp://x: Server returned 401 Unauthorized")


def test_reader_passes_cookie_and_ua_to_ffmpeg(monkeypatch):
    captured = {}

    class FakeProc:
        stdout = None
        stderr = None

    def fake_popen(cmd, **kw):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr("app.services.ffreader.subprocess.Popen", fake_popen)
    monkeypatch.setattr("app.services.ffreader.ffmpeg_path", lambda: "ffmpeg")
    r = FFmpegFrameReader("https://cctv.example/cam04/index.m3u8",
                          headers={"User-Agent": "UA/1", "Cookie": "sentinel=abc"})
    assert r.start()
    cmd = captured["cmd"]
    assert cmd[cmd.index("-user_agent") + 1] == "UA/1"
    assert cmd[cmd.index("-headers") + 1] == "Cookie: sentinel=abc\r\n"
    assert "-rtsp_transport" not in cmd


def test_keyframe_only_mode_changes_the_rtsp_command(monkeypatch):
    captured = {}

    class FakeProc:
        stdout = None
        stderr = None

    monkeypatch.setattr("app.services.ffreader.subprocess.Popen", lambda cmd, **kw: captured.setdefault("cmd", cmd) and FakeProc())
    monkeypatch.setattr("app.services.ffreader.ffmpeg_path", lambda: "ffmpeg")

    monkeypatch.setattr(settings, "rtsp_keyframes_only", False)
    assert FFmpegFrameReader("rtsp://cam/1", is_rtsp=True, fps=1.0).start()
    full = captured.pop("cmd")
    assert "-skip_frame" not in full and any(v.startswith("fps=1") for v in full)
    assert "-timeout" in full and "-rw_timeout" not in full

    monkeypatch.setattr(settings, "rtsp_keyframes_only", True)
    assert FFmpegFrameReader("rtsp://cam/1", is_rtsp=True, fps=1.0).start()
    lite = captured.pop("cmd")
    assert lite[lite.index("-skip_frame") + 1] == "nokey"
    assert "-fps_mode" in lite and not any(v.startswith("fps=") for v in lite)
    # HTTP sources are untouched by the RTSP-only switch
    assert FFmpegFrameReader("https://x/cam/index.m3u8", is_rtsp=False).start()
    assert "-skip_frame" not in captured["cmd"]
