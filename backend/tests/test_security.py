"""Security properties: authentication, RBAC, media protection, input validation."""


def test_api_requires_auth(client):
    assert client.get("/api/atlas/cameras").status_code == 401
    assert client.get("/api/insight/detections").status_code == 401
    assert client.get("/api/watch/alerts").status_code == 401
    assert client.get("/api/bridge/status").status_code == 401
    assert client.get("/api/bridge/scheduler").status_code == 401


def test_wrong_password_rejected(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_rate_limited(client):
    from app.routers import auth as auth_mod

    auth_mod._fails.clear()
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    r = client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert r.status_code == 429
    auth_mod._fails.clear()  # don't poison later fixtures


def test_viewer_cannot_operate(client, viewer):
    assert client.post("/api/bridge/cameras/1/start", headers=viewer).status_code == 403
    assert client.post("/api/atlas/discover", headers=viewer).status_code == 403
    assert client.post(
        "/api/watch/vehicles", headers=viewer, json={"plate": "GJ01XX0001"}
    ).status_code == 403


def test_media_requires_cookie_or_bearer(client):
    client.cookies.clear()  # drop any media cookie earlier logins set
    assert client.get("/data/detections/1/whatever.jpg").status_code == 401
    assert client.get("/api/bridge/cameras/1/snapshot").status_code == 401


def test_media_path_traversal_blocked(client, admin):
    """Authenticated evidence access must never escape the data directory.

    Requests that still resolve through /data must 404 (including URL-encoded
    traversal, which survives client-side path normalisation). Whatever the
    status, no server file content may ever appear in the body — a normalised
    path lands on the SPA shell, which is fine, but must not be a file read.
    """
    escaping = (
        "/data/%2e%2e/backend/app/config.py",
        "/data/..%2f..%2fbackend/app/config.py",
        "/data/detections%2f..%2f..%2fbackend/app/config.py",
        "/data/.jwt_secret",
        "/data/sutra.db",
    )
    for path in escaping:
        r = client.get(path, headers=admin)
        assert r.status_code == 404, f"{path} -> {r.status_code}"

    # no request, however mangled, may return real file contents
    for path in escaping + ("/data/../backend/app/config.py",):
        body = client.get(path, headers=admin).text
        assert "jwt_secret" not in body and "SUTRA_SEED" not in body, path


def test_source_url_scheme_allowlist(client, admin):
    r = client.post(
        "/api/atlas/cameras",
        headers=admin,
        json={"external_id": "evil-1", "name": "x", "source_type": "rtsp",
              "source_url": "ftp://internal/secret"},
    )
    assert r.status_code == 422


def test_file_source_confined_to_data_dir(client, admin):
    r = client.post(
        "/api/atlas/cameras",
        headers=admin,
        json={"external_id": "evil-2", "name": "x", "source_type": "file",
              "source_url": "C:/Windows/System32/config/SAM"},
    )
    assert r.status_code == 422


def test_login_sets_httponly_media_cookie(client):
    r = client.post("/api/auth/login", json={"username": "viewer", "password": "Viewer@26"})
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert "sutra_media=" in set_cookie and "HttpOnly" in set_cookie


def test_operator_department_scoping(client, admin):
    # seed one Police and one Municipal camera, then check the operator sees only Police
    for ext, dept in (("scope-pol", "Police"), ("scope-mun", "Municipal")):
        client.post(
            "/api/atlas/cameras",
            headers=admin,
            json={"external_id": ext, "name": ext, "department": dept,
                  "source_type": "rtsp", "source_url": "rtsp://10.0.0.1/x"},
        )
    r = client.post("/api/auth/login", json={"username": "operator_police", "password": "Operator@26"})
    op = {"Authorization": f"Bearer {r.json()['token']}"}
    cams = client.get("/api/atlas/cameras", headers=op).json()
    assert cams and all(c["department"] == "Police" for c in cams)


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


def test_sync_endpoint_absent_in_full_mode(client, admin):
    """The edge->central channel is only exposed by a node running as central,
    so a normal deployment has no metadata-injection surface at all."""
    r = client.post("/api/sync/push", headers={"X-Sync-Key": "anything"}, json={})
    assert r.status_code in (404, 405)
