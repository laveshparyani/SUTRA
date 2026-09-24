"""Insight read contract: detections, vehicles, sightings, route
reconstruction, analytics and the submission output report. The ANPR engine
is disabled in tests, so reads are inserted directly and the API is checked
for what it makes of them."""

import csv
import io
from datetime import datetime, timedelta, timezone

import pytest

from api_helpers import get_or_create_camera, seed_detections

PLATE = "GJ97IN0001"


@pytest.fixture(scope="module")
def trail(client, admin):
    """Two cameras; the plate is read twice at cam A, then once at cam B."""
    a = get_or_create_camera(client, admin, "apit-ins-a", name="Insight A", location="Paldi Circle",
                             department="Police")
    b = get_or_create_camera(client, admin, "apit-ins-b", name="Insight B", location="Visat Circle",
                             department="Police")
    ids_a = seed_detections(a["id"], PLATE, minutes_ago=[40, 38], conf=0.82,
                            snapshot_path="detections/apit/a.jpg")
    ids_b = seed_detections(b["id"], PLATE, minutes_ago=[12], conf=0.95)
    return {"a": a, "b": b, "ids": ids_a + ids_b}


def test_detections_filter_by_plate_and_camera(client, viewer, trail):
    r = client.get("/api/insight/detections", headers=viewer, params={"plate": "gj 97 in 0001"})
    assert r.status_code == 200
    rows = r.json()
    assert {d["id"] for d in rows} >= set(trail["ids"])
    assert all(d["plate_text"] == PLATE for d in rows)
    assert rows[0]["ts"] >= rows[-1]["ts"]                    # newest first
    assert {"id", "camera_id", "ts", "plate_conf", "snapshot_path", "bbox"} <= set(rows[0])

    only_b = client.get("/api/insight/detections", headers=viewer,
                        params={"plate": PLATE, "camera_id": trail["b"]["id"]}).json()
    assert [d["id"] for d in only_b] == trail["ids"][2:]
    assert len(client.get("/api/insight/detections?limit=1", headers=viewer).json()) == 1


def test_route_reconstructs_ordered_sightings(client, viewer, trail):
    r = client.get(f"/api/insight/route/gj-97-in-0001", headers=viewer)
    assert r.status_code == 200
    route = r.json()
    assert route["plate"] == PLATE
    assert route["total_detections"] == 3
    assert route["cameras_seen"] == 2
    s1, s2 = route["sightings"]
    assert s1["camera_id"] == trail["a"]["id"] and s1["detections"] == 2
    assert s1["location"] == "Paldi Circle" and s1["district"] == "Ahmedabad"
    assert s1["lat"] and s1["lon"]
    assert s1["snapshot"] == "/data/detections/apit/a.jpg"
    assert s2["camera_id"] == trail["b"]["id"] and s2["detections"] == 1
    assert s1["last_seen"] <= s2["first_seen"]               # chronological
    assert s2["best_conf"] == 0.95


def test_route_for_unknown_plate_is_empty_not_an_error(client, viewer):
    r = client.get("/api/insight/route/GJ00NO0000", headers=viewer)
    assert r.status_code == 200
    assert r.json() == {"plate": "GJ00NO0000", "sightings": [], "cameras_seen": 0, "total_detections": 0}


def test_vehicles_groups_by_plate_and_flags_watchlist(client, admin, viewer, trail):
    client.post("/api/watch/vehicles", headers=admin, json={"plate": PLATE, "reason": "suspect"})
    rows = client.get("/api/insight/vehicles", headers=viewer, params={"plate": PLATE, "hours": 2}).json()
    assert len(rows) == 1
    v = rows[0]
    assert v["reads"] == 3 and v["camera_count"] == 2
    assert v["cameras"] == sorted([trail["a"]["id"], trail["b"]["id"]])
    assert v["last_camera"] == "Insight B" and v["last_location"] == "Visat Circle"
    assert v["watchlisted"] is True
    assert v["best_conf"] == 0.95
    assert v["snapshot"] == "/data/detections/apit/a.jpg"
    assert v["first_seen"] < v["last_seen"]


def test_sightings_collapse_consecutive_reads_per_camera(client, viewer, trail):
    rows = client.get("/api/insight/sightings", headers=viewer, params={"plate": PLATE, "hours": 2}).json()
    by_cam = {s["camera_id"]: s for s in rows}
    assert set(by_cam) == {trail["a"]["id"], trail["b"]["id"]}
    assert by_cam[trail["a"]["id"]]["reads"] == 2
    assert by_cam[trail["a"]["id"]]["camera_name"] == "Insight A"
    assert by_cam[trail["b"]["id"]]["reads"] == 1
    assert rows[0]["camera_id"] == trail["b"]["id"]              # most recent sighting first


def test_analytics_reflects_seeded_reads(client, viewer, trail):
    r = client.get("/api/insight/analytics?hours=2", headers=viewer)
    assert r.status_code == 200
    an = r.json()
    assert an["window_hours"] == 2 and len(an["activity"]) == 2
    assert an["totals"]["detections"] >= 3
    assert an["totals"]["cameras_registered"] == len(client.get("/api/atlas/cameras", headers=viewer).json())
    assert an["totals"]["watchlist_active"] >= 1
    assert any(v["plate"] == PLATE for v in an["top_vehicles"])
    assert {c["camera"] for c in an["by_camera"]} >= {"Insight A", "Insight B"}
    assert sum(b["count"] for b in an["confidence_bands"]) >= 3
    assert {"camera_health", "alerts_by_reason", "alerts_by_severity", "by_department"} <= set(an)


def test_report_csv_columns_and_ist_conversion(client, viewer, trail):
    r = client.get("/api/insight/report", headers=viewer, params={"camera_id": trail["a"]["id"]})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "sutra_anpr_output_report.csv" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert list(rows[0].keys()) == ["sr_no", "camera", "location", "district", "plate_number", "ocr_confidence",
                                    "reads_in_vote", "timestamp_utc", "timestamp_ist", "evidence_snapshot"]
    mine = [row for row in rows if row["plate_number"] == PLATE]
    assert len(mine) == 2 and mine[0]["sr_no"] == "1"
    assert mine[0]["camera"] == "Insight A" and mine[0]["ocr_confidence"] == "0.82"
    utc = datetime.fromisoformat(mine[0]["timestamp_utc"])
    ist = datetime.fromisoformat(mine[0]["timestamp_ist"])
    assert ist - utc == timedelta(hours=5, minutes=30)
    assert mine[0]["evidence_snapshot"] == "detections/apit/a.jpg"


def test_report_json_and_time_bounds(client, viewer, trail):
    r = client.get("/api/insight/report", headers=viewer, params={"fmt": "json", "camera_id": trail["b"]["id"]})
    assert r.status_code == 200
    body = r.json()
    assert body["generated_by"] == "viewer" and body["total"] == 1
    assert body["detections"][0]["plate"] == PLATE and body["detections"][0]["camera"] == "Insight B"

    since = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat().replace("+00:00", "Z")
    recent = client.get("/api/insight/report", headers=viewer,
                        params={"fmt": "json", "since": since}).json()
    assert all(d["plate"] != PLATE or d["camera"] == "Insight B" for d in recent["detections"])
    assert client.get("/api/insight/report", headers=viewer,
                      params={"since": "not-a-date"}).status_code == 422


def test_stats_and_scene_are_available_with_engines_disabled(client, viewer):
    assert isinstance(client.get("/api/insight/stats", headers=viewer).json(), dict)
    scene = client.get("/api/insight/scene", headers=viewer).json()
    assert scene["frames_analysed"] == 0 and scene["cameras"] == {}


def test_analyse_rejects_non_image_upload(client, viewer):
    r = client.post("/api/insight/analyse", headers=viewer,
                    files={"file": ("x.jpg", b"definitely not a jpeg", "image/jpeg")})
    assert r.status_code == 400
