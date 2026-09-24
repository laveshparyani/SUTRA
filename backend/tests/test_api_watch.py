"""Watch contract: watchlist lifecycle, alerts, acknowledgement, episodes,
the government-DB connector lookup and the alert WebSocket."""

import pytest
from starlette.websockets import WebSocketDisconnect

from api_helpers import get_or_create_camera, operator, seed_alert, seed_detections


def _watch_cam(client, admin):
    return get_or_create_camera(client, admin, "apit-watch-cam", name="Watch Cam", location="Paldi Circle")


def test_add_normalises_plate_and_records_who_added_it(client, admin):
    r = client.post("/api/watch/vehicles", headers=admin,
                    json={"plate": "gj 96-wl.0001", "reason": "stolen", "fir_ref": "FIR/APIT/1", "priority": "high",
                          "notes": "apit"})
    assert r.status_code == 201
    body = r.json()
    assert body["plate"] == "GJ96WL0001"
    assert body["active"] is True
    assert body["added_by"] == "admin"
    assert body["reason"] == "stolen" and body["fir_ref"] == "FIR/APIT/1"
    assert body["created_at"]

    listed = client.get("/api/watch/vehicles", headers=admin).json()
    assert any(w["plate"] == "GJ96WL0001" for w in listed)


def test_duplicate_plate_conflicts_even_when_spelled_differently(client, admin):
    client.post("/api/watch/vehicles", headers=admin, json={"plate": "GJ96WL0002"})
    r = client.post("/api/watch/vehicles", headers=admin, json={"plate": "gj-96 wl 0002"})
    assert r.status_code == 409


def test_add_validates_body(client, admin):
    assert client.post("/api/watch/vehicles", headers=admin, json={"reason": "stolen"}).status_code == 422


def test_deactivate_keeps_the_row_but_marks_it_inactive(client, admin, viewer):
    entry = client.post("/api/watch/vehicles", headers=admin, json={"plate": "GJ96WL0003"}).json()
    assert client.delete(f"/api/watch/vehicles/{entry['id']}", headers=viewer).status_code == 403
    r = client.delete(f"/api/watch/vehicles/{entry['id']}", headers=admin)
    assert r.status_code == 200 and r.json() == {"deactivated": "GJ96WL0003"}
    rows = {w["id"]: w for w in client.get("/api/watch/vehicles", headers=admin).json()}
    assert rows[entry["id"]]["active"] is False
    assert client.delete("/api/watch/vehicles/999999", headers=admin).status_code == 404
    # re-adding an inactive plate is still a conflict: the row exists
    assert client.post("/api/watch/vehicles", headers=admin, json={"plate": "GJ96WL0003"}).status_code == 409
    trail = client.get("/api/atlas/audit?limit=10", headers=admin).json()
    assert any(a["action"] == "watchlist.deactivate" and a["detail"] == "GJ96WL0003" for a in trail)


def test_alerts_list_filter_and_acknowledge(client, admin, viewer):
    cam = _watch_cam(client, admin)
    entry = client.post("/api/watch/vehicles", headers=admin,
                        json={"plate": "GJ96AL0001", "reason": "wanted", "priority": "high"}).json()
    det_ids = seed_detections(cam["id"], "GJ96AL0001", minutes_ago=[3, 2])
    alert_ids = [seed_alert(d, entry["id"]) for d in det_ids]

    r = client.get("/api/watch/alerts", headers=viewer)
    assert r.status_code == 200
    mine = [a for a in r.json() if a["id"] in alert_ids]
    assert len(mine) == 2
    assert all(a["status"] == "new" and a["acked_by"] is None for a in mine)
    assert mine[0]["watchlist_id"] == entry["id"] and mine[0]["match_type"] == "exact"
    assert mine[0]["ts"] >= mine[1]["ts"]           # newest first

    assert client.post(f"/api/watch/alerts/{alert_ids[0]}/ack", headers=viewer).status_code == 403
    r = client.post(f"/api/watch/alerts/{alert_ids[0]}/ack", headers=operator(client))
    assert r.status_code == 200 and r.json() == {"acknowledged": alert_ids[0]}

    acked = {a["id"]: a for a in client.get("/api/watch/alerts?status=acknowledged", headers=admin).json()}
    assert acked[alert_ids[0]]["acked_by"] == "operator_police"
    still_new = {a["id"] for a in client.get("/api/watch/alerts?status=new", headers=admin).json()}
    assert alert_ids[1] in still_new and alert_ids[0] not in still_new
    assert client.post("/api/watch/alerts/999999/ack", headers=admin).status_code == 404
    assert len(client.get("/api/watch/alerts?limit=1", headers=admin).json()) == 1


def test_episodes_collapse_repeat_hits_and_ack_in_one_action(client, admin):
    cam = _watch_cam(client, admin)
    entry = client.post("/api/watch/vehicles", headers=admin,
                        json={"plate": "GJ96EP0001", "reason": "stolen", "fir_ref": "FIR/EP/1"}).json()
    det_ids = seed_detections(cam["id"], "GJ96EP0001", minutes_ago=[30, 20, 10])
    alert_ids = [seed_alert(d, entry["id"], severity=s) for d, s in zip(det_ids, ("medium", "high", "medium"))]
    # one probable (fuzzy) read on the same camera joins the episode and marks it
    fuzzy_det = seed_detections(cam["id"], "GJ96EPO001", minutes_ago=[5])[0]
    alert_ids.append(seed_alert(fuzzy_det, entry["id"], match_type="probable"))

    eps = client.get("/api/watch/alerts/episodes?hours=2", headers=admin).json()
    ep = next(e for e in eps if e["plate"] == "GJ96EP0001")
    assert ep["count"] == 4 and ep["unacknowledged"] == 4
    assert ep["severity"] == "high"                  # worst severity wins
    assert ep["match_type"] == "exact"               # an exact hit anywhere makes the episode exact
    assert "GJ96EPO001" in ep["read_as"]             # but the raw fuzzy read stays visible
    assert ep["camera_name"] == "Watch Cam" and ep["fir_ref"] == "FIR/EP/1"
    assert set(ep["alert_ids"]) == set(alert_ids)
    assert ep["first_seen"] <= ep["last_seen"]

    r = client.post("/api/watch/alerts/episodes/ack", headers=admin, json=ep["alert_ids"])
    assert r.status_code == 200 and r.json() == {"acknowledged": 4}
    ep = next(e for e in client.get("/api/watch/alerts/episodes?hours=2", headers=admin).json()
              if e["plate"] == "GJ96EP0001")
    assert ep["unacknowledged"] == 0
    # idempotent — nothing left to acknowledge
    assert client.post("/api/watch/alerts/episodes/ack", headers=admin, json=alert_ids).json() == {"acknowledged": 0}
    assert client.get("/api/watch/alerts/episodes?status=new&hours=2", headers=admin).status_code == 200


def test_vehicle_info_connector(client, viewer):
    r = client.get("/api/watch/vehicle-info/gj 01 ab 1234", headers=viewer)
    assert r.status_code == 200
    body = r.json()
    assert body["registration_no"] == "GJ01AB1234"
    assert body["source"].startswith("VAHAN")
    assert {"maker", "model", "owner_name"} <= set(body)
    assert client.get("/api/watch/vehicle-info/GJ00ZZ0000", headers=viewer).status_code == 404
    assert client.get("/api/watch/vehicle-info/GJ01AB1234").status_code == 401


def test_alert_websocket_requires_media_auth_and_receives_broadcasts(client, admin):
    from app.routers import watch

    client.cookies.clear()
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/watch/ws"):
            pass
    assert exc.value.code == 4401

    with client.websocket_connect("/api/watch/ws", headers=admin) as ws:
        watch.broadcast_alert({"type": "watchlist_alert", "plate": "GJ96WS0001", "reason": "stolen"})
        msg = ws.receive_json()
        assert msg["type"] == "watchlist_alert" and msg["plate"] == "GJ96WS0001"
