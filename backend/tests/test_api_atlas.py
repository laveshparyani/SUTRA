"""Atlas registry contract: CRUD, filters, CSV export, bulk import, discovery,
gap analysis and the audit trail (Model 1 deliverables)."""

import csv
import io

import httpx
import pytest

from api_helpers import RTSP, create_camera, operator


def test_create_camera_echoes_fields_and_geocodes_location(client, admin):
    cam = create_camera(client, admin, "apit-cr-1", name="Paldi Test", location="Paldi Circle",
                        department="Unassigned", camera_type="anpr", install_date="2019-04-01")
    assert cam["id"] > 0
    assert cam["external_id"] == "apit-cr-1"
    assert cam["onboarded_via"] == "api"
    assert cam["status"] == "unknown" and cam["health"] == "unknown"
    assert cam["monitoring"] is False
    # no coordinates supplied -> geocoded from the location hint, and the
    # unassigned department is filled from the same hint
    assert cam["lat"] and cam["lon"]
    assert cam["district"] == "Ahmedabad"
    assert cam["department"] == "Police"
    assert cam["coords_approx"] is True


def test_create_camera_keeps_explicit_coordinates(client, admin):
    cam = create_camera(client, admin, "apit-cr-2", lat=22.30, lon=70.80, district="Rajkot")
    assert (cam["lat"], cam["lon"], cam["district"]) == (22.30, 70.80, "Rajkot")


def test_duplicate_external_id_conflicts(client, admin):
    create_camera(client, admin, "apit-dup")
    r = client.post("/api/atlas/cameras", headers=admin,
                    json={"external_id": "apit-dup", "name": "x", "source_url": RTSP})
    assert r.status_code == 409


def test_create_validates_body(client, admin):
    assert client.post("/api/atlas/cameras", headers=admin, json={"name": "x"}).status_code == 422
    r = client.post("/api/atlas/cameras", headers=admin,
                    json={"external_id": "apit-bad", "name": "x", "source_url": "file:///etc/passwd"})
    assert r.status_code == 422


def test_get_camera_by_id(client, admin, viewer):
    cam = create_camera(client, admin, "apit-get")
    r = client.get(f"/api/atlas/cameras/{cam['id']}", headers=viewer)
    assert r.status_code == 200 and r.json()["external_id"] == "apit-get"
    assert client.get("/api/atlas/cameras/999999", headers=viewer).status_code == 404


def test_list_filters(client, admin):
    create_camera(client, admin, "apit-f-1", name="Filter Alpha Tower", location="Visat Circle",
                  department="apit-DeptA")
    create_camera(client, admin, "apit-f-2", name="Filter Beta Gate", location="Janpath",
                  department="apit-DeptB")

    def ids(**params):
        r = client.get("/api/atlas/cameras", headers=admin, params=params)
        assert r.status_code == 200
        return [c["external_id"] for c in r.json()]

    assert ids(department="apit-DeptA") == ["apit-f-1"]
    assert ids(district="Gandhinagar") and "apit-f-1" in ids(district="Gandhinagar")
    assert ids(q="Beta Gate") == ["apit-f-2"]
    assert ids(q="janpath") == ["apit-f-2"]           # location match, case-insensitive
    assert ids(status="live") == []
    assert set(ids(health="unknown")) >= {"apit-f-1", "apit-f-2"}
    listed = [c["id"] for c in client.get("/api/atlas/cameras", headers=admin).json()]
    assert listed == sorted(listed)                   # stable id order


def test_patch_camera(client, admin, viewer):
    cam = create_camera(client, admin, "apit-patch")
    r = client.patch(f"/api/atlas/cameras/{cam['id']}", headers=admin,
                     json={"name": "Renamed", "lat": 21.17, "lon": 72.83, "retention_days": 30})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Renamed"
    assert body["coords_approx"] is False          # operator-supplied coordinates are authoritative
    assert body["retention_days"] == 30
    assert body["source_url"] == RTSP              # untouched fields survive a partial update

    assert client.patch(f"/api/atlas/cameras/{cam['id']}", headers=admin,
                        json={"source_url": "gopher://x"}).status_code == 422
    assert client.patch("/api/atlas/cameras/999999", headers=admin, json={"name": "x"}).status_code == 404
    assert client.patch(f"/api/atlas/cameras/{cam['id']}", headers=viewer, json={"name": "x"}).status_code == 403


def test_export_is_csv_with_every_registered_camera(client, admin):
    create_camera(client, admin, "apit-exp", name="Export, With Comma")
    r = client.get("/api/atlas/export", headers=admin)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "sutra_camera_registry.csv" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert {"external_id", "name", "lat", "lon", "source_type", "health", "monitoring"} <= set(rows[0].keys())
    mine = [row for row in rows if row["external_id"] == "apit-exp"]
    assert mine and mine[0]["name"] == "Export, With Comma"   # quoting survives the round trip
    assert len(rows) == len(client.get("/api/atlas/cameras", headers=admin).json())


def test_export_is_department_scoped_for_operators(client, admin):
    create_camera(client, admin, "apit-exp-mun", department="Municipal")
    rows = list(csv.DictReader(io.StringIO(client.get("/api/atlas/export", headers=operator(client)).text)))
    assert rows and all(row["department"] == "Police" for row in rows)
    assert "apit-exp-mun" not in {row["external_id"] for row in rows}


def test_bulk_import_creates_and_skips(client, admin):
    create_camera(client, admin, "apit-bulk-dup")
    csv_text = (
        "﻿external_id,name,location,department,lat,lon,source_type,source_url,install_date,retention_days\n"
        "apit-bulk-1,Bulk One,Paldi Circle,,,,rtsp,rtsp://192.0.2.20/one,2016-01-01,15\n"
        "apit-bulk-2,Bulk Two,Somewhere,Fire,21.5,72.5,http-progressive,http://192.0.2.21/two,,\n"
        "apit-bulk-dup,Duplicate,,,,,rtsp,rtsp://192.0.2.22/dup,,\n"
        "apit-bulk-bad,Bad Scheme,,,,,rtsp,ftp://192.0.2.23/bad,,\n"
        ",No Id,,,,,rtsp,rtsp://192.0.2.24/x,,\n"
    )
    r = client.post("/api/atlas/cameras/bulk", headers=admin,
                    files={"file": ("cams.csv", csv_text.encode("utf-8"), "text/csv")})
    assert r.status_code == 200
    assert r.json() == {"created": 2, "skipped": 3}

    cams = {c["external_id"]: c for c in client.get("/api/atlas/cameras", headers=admin).json()}
    one, two = cams["apit-bulk-1"], cams["apit-bulk-2"]
    assert one["onboarded_via"] == "bulk"
    assert one["district"] == "Ahmedabad" and one["department"] == "Police"   # geocoded
    assert one["coords_approx"] is True and one["retention_days"] == 15
    assert two["coords_approx"] is False and (two["lat"], two["lon"]) == (21.5, 72.5)
    assert two["department"] == "Fire"
    assert "apit-bulk-bad" not in cams

    # a repeat import is idempotent
    r = client.post("/api/atlas/cameras/bulk", headers=admin,
                    files={"file": ("cams.csv", csv_text.encode("utf-8"), "text/csv")})
    assert r.json()["created"] == 0


def test_bulk_import_requires_operator_role_and_a_file(client, admin, viewer):
    assert client.post("/api/atlas/cameras/bulk", headers=viewer,
                       files={"file": ("c.csv", b"external_id\n", "text/csv")}).status_code == 403
    assert client.post("/api/atlas/cameras/bulk", headers=admin).status_code == 422


def test_discover_upserts_portal_catalogue(client, admin, monkeypatch):
    async def fake_catalogue():
        return [{"id": "cam901", "name": "901 Apit Paldi Junction"},
                {"id": "cam902", "name": "902 Apit Visat Crossing", "status": "live"}]

    monkeypatch.setattr("app.routers.atlas.fetch_portal_cameras", fake_catalogue)
    r = client.post("/api/atlas/discover", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 2 and body["total_from_portal"] == 2

    cams = {c["external_id"]: c for c in client.get("/api/atlas/cameras", headers=admin).json()}
    cam = cams["sentinel-901"]
    assert cam["name"] == "Apit Paldi Junction"
    assert cam["location"] == "901 Apit Paldi Junction"
    assert cam["source_type"] == "rtsp"
    assert cam["source_url"].startswith("rtsp://") and "@" not in cam["source_url"]
    assert cam["onboarded_via"] == "discovery"
    assert cam["district"] == "Ahmedabad"

    # second run: same rows, no duplicates
    r = client.post("/api/atlas/discover", headers=admin)
    assert r.json()["created"] == 0 and r.json()["updated"] == 2
    ext_ids = [c["external_id"] for c in client.get("/api/atlas/cameras", headers=admin).json()]
    assert ext_ids.count("sentinel-901") == 1


def test_discover_reports_unreachable_portal(client, admin, monkeypatch):
    async def down():
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("app.routers.atlas.fetch_portal_cameras", down)
    r = client.post("/api/atlas/discover", headers=admin)
    assert r.status_code == 502
    assert "unreachable" in r.json()["detail"]


def test_gap_analysis_totals_match_registry(client, admin):
    create_camera(client, admin, "apit-gap-old", district="apit-Gap", install_date="2015-06-01")
    create_camera(client, admin, "apit-gap-new", district="apit-Gap", install_date="2026-01-01",
                  department="apit-GapDept")
    r = client.get("/api/atlas/gap-analysis", headers=admin)
    assert r.status_code == 200
    gap = r.json()
    cams = client.get("/api/atlas/cameras", headers=admin).json()
    assert gap["total_cameras"] == len(cams)
    assert gap["monitored"] == sum(1 for c in cams if c["monitoring"])
    assert gap["healthy"] == sum(1 for c in cams if c["health"] == "ok")
    d = gap["districts"]["apit-Gap"]
    assert d["cameras"] == 2
    assert d["ageing"] == 1                          # installed > 5 years ago
    assert "apit-GapDept" in d["departments"] and "Police" in d["departments"]


def test_audit_trail_records_registry_actions_newest_first(client, admin):
    create_camera(client, admin, "apit-audit")
    client.get("/api/atlas/export", headers=admin)
    trail = client.get("/api/atlas/audit?limit=5", headers=admin).json()
    assert len(trail) <= 5
    assert trail[0]["action"] == "registry.export" and trail[0]["actor"] == "admin"
    actions = [(a["action"], a["detail"]) for a in client.get("/api/atlas/audit?limit=50", headers=admin).json()]
    assert ("camera.create", "apit-audit") in actions
    assert len(client.get("/api/atlas/audit?limit=100000", headers=admin).json()) <= 500


@pytest.mark.parametrize("path", ["/api/atlas/export", "/api/atlas/gap-analysis", "/api/atlas/audit"])
def test_atlas_reads_need_authentication(client, path):
    assert client.get(path).status_code == 401
