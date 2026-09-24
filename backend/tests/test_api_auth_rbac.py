"""Auth contract and the role matrix across every router.

RBAC here is checked as a matrix rather than one endpoint at a time: a new
write endpoint that forgets `require_roles` shows up as a missing row, not as
a silent gap. Admin calls use ids that do not exist, so the assertion is
"got past the gate" (404/400/422, never 401/403) without touching ingest.
"""

import pytest

from api_helpers import login, operator


# ------------------------------------------------------------------ login


@pytest.mark.parametrize(
    "username,password,role,department",
    [
        ("admin", "SutraAdmin@26", "admin", ""),
        ("operator_police", "Operator@26", "operator", "Police"),
        ("viewer", "Viewer@26", "viewer", ""),
    ],
)
def test_login_returns_identity_and_me_agrees(client, username, password, role, department):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == username
    assert body["role"] == role
    assert body["department"] == department
    assert body["token"].count(".") == 2          # a JWT, three segments

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200
    assert me.json() == {"username": username, "role": role, "department": department}


def test_login_rejects_unknown_user_and_malformed_body(client):
    from app.routers import auth as auth_mod

    assert client.post("/api/auth/login", json={"username": "nobody", "password": "x"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin"}).status_code == 422
    assert client.post("/api/auth/login", json={}).status_code == 422
    auth_mod._fails.clear()   # keep the rate-limit budget for later modules


def test_failed_login_is_audited(client, admin):
    from app.routers import auth as auth_mod

    client.post("/api/auth/login", json={"username": "apit-ghost", "password": "x"})
    auth_mod._fails.clear()
    trail = client.get("/api/atlas/audit?limit=20", headers=admin).json()
    assert any(a["action"] == "auth.login_failed" and a["actor"] == "apit-ghost" for a in trail)


def test_token_validation(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_logout_clears_media_cookie(client):
    r = client.post("/api/auth/logout")
    assert r.status_code == 200 and r.json() == {"ok": True}
    set_cookie = r.headers.get("set-cookie", "")
    assert "sutra_media=" in set_cookie
    assert "max-age=0" in set_cookie.lower() or "expires=" in set_cookie.lower()


# ------------------------------------------------------------- role matrix

# (method, path, json) for every state-changing endpoint that must be
# admin/operator only. Ids are deliberately non-existent.
WRITE_ENDPOINTS = [
    ("POST", "/api/atlas/cameras", {"external_id": "apit-rbac", "name": "x", "source_url": "rtsp://192.0.2.1/x"}),
    ("PATCH", "/api/atlas/cameras/999999", {"name": "x"}),
    ("POST", "/api/atlas/discover", None),
    ("POST", "/api/bridge/cameras/999999/start", None),
    ("POST", "/api/bridge/cameras/999999/stop", None),
    ("POST", "/api/bridge/cameras/999999/pin", None),
    ("POST", "/api/bridge/cameras/999999/unpin", None),
    ("POST", "/api/bridge/start-all", None),
    ("POST", "/api/watch/vehicles", {"plate": "GJ99RB0001"}),
    ("DELETE", "/api/watch/vehicles/999999", None),
    ("POST", "/api/watch/alerts/999999/ack", None),
    ("POST", "/api/watch/alerts/episodes/ack", [999999]),
]

# Read endpoints every authenticated role may use.
READ_ENDPOINTS = [
    "/api/atlas/cameras",
    "/api/atlas/gap-analysis",
    "/api/atlas/export",
    "/api/atlas/audit",
    "/api/bridge/status",
    "/api/bridge/scheduler",
    "/api/insight/stats",
    "/api/insight/detections",
    "/api/insight/vehicles",
    "/api/insight/sightings",
    "/api/insight/analytics?hours=2",
    "/api/insight/route/GJ01AB1234",
    "/api/insight/report?fmt=json",
    "/api/insight/scene",
    "/api/watch/vehicles",
    "/api/watch/alerts",
    "/api/watch/alerts/episodes",
    "/api/system",
]


@pytest.mark.parametrize("method,path,body", WRITE_ENDPOINTS, ids=[f"{m} {p}" for m, p, _ in WRITE_ENDPOINTS])
def test_write_endpoints_reject_viewer_and_anonymous(client, viewer, method, path, body):
    anon = client.request(method, path, json=body)
    assert anon.status_code == 401, f"{method} {path} anonymous -> {anon.status_code}"
    r = client.request(method, path, headers=viewer, json=body)
    assert r.status_code == 403, f"{method} {path} viewer -> {r.status_code} {r.text}"


@pytest.mark.parametrize("method,path,body", WRITE_ENDPOINTS, ids=[f"{m} {p}" for m, p, _ in WRITE_ENDPOINTS])
def test_write_endpoints_admit_admin(client, admin, monkeypatch, method, path, body):
    # discover and start-all would reach out to real sources; stub them so the
    # gate is what is measured, not the network or the ingest engine
    if path.endswith("/discover"):
        async def no_portal():
            return []
        monkeypatch.setattr("app.routers.atlas.fetch_portal_cameras", no_portal)
    if path.endswith("/start-all"):
        pytest.skip("start-all pools every registered camera; covered by test_api_atlas via viewer only")
    if path == "/api/atlas/cameras":
        body = {**body, "external_id": "apit-rbac-admin"}
    r = client.request(method, path, headers=admin, json=body)
    assert r.status_code not in (401, 403), f"{method} {path} admin -> {r.status_code} {r.text}"


def test_operator_admitted_to_write_endpoints(client):
    op = operator(client)
    r = client.post("/api/watch/vehicles", headers=op, json={"plate": "GJ99RB0002", "reason": "suspect"})
    assert r.status_code == 201
    assert r.json()["added_by"] == "operator_police"
    assert client.post("/api/bridge/cameras/999999/pin", headers=op).status_code == 200
    assert client.post("/api/bridge/cameras/999999/unpin", headers=op).status_code == 200


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_read_endpoints_open_to_every_role(client, viewer, path):
    # login sets an HttpOnly media cookie that the shared client keeps; a
    # genuinely anonymous request must not carry it
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        assert client.get(path).status_code == 401, f"{path} must require auth"
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)
    r = client.get(path, headers=viewer)
    assert r.status_code == 200, f"{path} viewer -> {r.status_code} {r.text}"


def test_deactivated_user_cannot_authenticate(client):
    """A token issued earlier must stop working the moment the account is
    deactivated — the check is on every request, not only at login."""
    from app.db import SessionLocal
    from app.models import User
    from app.security import hash_password

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "apit-temp").one_or_none()
        if u is None:
            u = User(username="apit-temp", password_hash=hash_password("Temp@26"), role="viewer")
            db.add(u)
        u.active = True
        db.commit()
    finally:
        db.close()

    headers = login(client, "apit-temp", "Temp@26")
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    db = SessionLocal()
    try:
        db.query(User).filter(User.username == "apit-temp").update({"active": False})
        db.commit()
    finally:
        db.close()

    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.post("/api/auth/login", json={"username": "apit-temp", "password": "Temp@26"}).status_code == 401
    from app.routers import auth as auth_mod
    auth_mod._fails.clear()
