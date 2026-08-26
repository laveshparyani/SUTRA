import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, fmtTime } from "../api";
import { CamMap } from "../components/CamMap.jsx";
import { PlateChip } from "../components/PlateChip.jsx";

export function Trace() {
  const [params] = useSearchParams();
  const [plate, setPlate] = useState(params.get("plate") ?? "");
  const [route, setRoute] = useState(null);
  const [vinfo, setVinfo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [zoom, setZoom] = useState(null);
  const [cams, setCams] = useState([]);

  // the network itself is context: an operator needs to see which cameras
  // could have seen this vehicle, not just where it was found
  useEffect(() => {
    api.cameras().then(setCams).catch(() => {});
  }, []);

  async function search(e) {
    e?.preventDefault();
    if (!plate.trim()) return;
    setBusy(true);
    setVinfo(null);
    try {
      const r = await api.route(plate.trim());
      setRoute(r);
      // government-DB correlation (representative VAHAN connector)
      fetch(`/api/watch/vehicle-info/${encodeURIComponent(r.plate)}`)
        .then((res) => (res.ok ? res.json() : null))
        .then(setVinfo)
        .catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (params.get("plate")) search();
  }, []);

  return (
    <div className="trace-layout">
      <div className="panel trace-timeline">
        <div className="panel-head">Movement History</div>
        <form className="form-row" style={{ padding: "13px 14px" }} onSubmit={search}>
          <input
            style={{ flex: 1, textTransform: "uppercase" }}
            placeholder="GJ01AB1234"
            value={plate}
            onChange={(e) => setPlate(e.target.value.toUpperCase())}
          />
          <button className="btn primary" disabled={busy}>
            {busy ? "…" : "Trace"}
          </button>
        </form>

        {route && (
          <div style={{ padding: "0 14px 10px", display: "flex", gap: 9, alignItems: "center", flexWrap: "wrap" }}>
            <PlateChip plate={route.plate} />
            <span className="badge neutral">{route.cameras_seen} cameras</span>
            <span className="badge neutral">{route.total_detections} detections</span>
          </div>
        )}
        {vinfo && (
          <div style={{ margin: "0 14px 12px", padding: "10px 12px", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: 6, fontSize: 12.5, lineHeight: 1.75 }}>
            <div className="dim small" style={{ letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 4 }}>
              {vinfo.source}
            </div>
            <b>{vinfo.maker} {vinfo.model}</b> · {vinfo.colour}<br />
            {vinfo.vehicle_class} · {vinfo.fuel} · Reg. {vinfo.registration_date}<br />
            {vinfo.rto}<br />
            Owner: <span className="mono">{vinfo.owner_name}</span> · Insurance:{" "}
            <span className={`badge ${vinfo.insurance_valid ? "ok" : "high"}`}>
              {vinfo.insurance_valid ? "valid" : "lapsed"}
            </span>
          </div>
        )}

        {route && route.sightings.length === 1 && (
          <div className="explainer" style={{ margin: "0 14px 12px" }}>
            <span className="ico">◎</span>
            <div>
              Seen at <b>one location only</b>, so there is no route line to draw yet — a path
              appears as soon as this vehicle is read by a second camera. The sighting below
              carries its full time window and evidence.
            </div>
          </div>
        )}

        {route && route.sightings.length === 0 && (
          <div className="empty-state">
            <div className="big">Not Sighted</div>
            No detections for this registration number in the integrated network.
          </div>
        )}

        {route?.sightings.map((s, i) => (
          <div className="sighting" key={i}>
            <div className="seq">{i + 1}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="s-loc">{s.location}</div>
              <div className="s-time">
                {fmtTime(s.first_seen)}
                {s.last_seen !== s.first_seen && <> → {fmtTime(s.last_seen)}</>}
              </div>
              <div className="s-extra">
                {s.district || "—"} · {s.detections} reads · conf {(s.best_conf * 100).toFixed(0)}%
              </div>
            </div>
            {s.snapshot && <img src={s.snapshot} alt="" onClick={() => setZoom(s.snapshot)} style={{ cursor: "zoom-in" }} />}
          </div>
        ))}

        {!route && (
          <div className="empty-state">
            <div className="big">Vehicle Trace</div>
            Enter a registration number to reconstruct its route across the integrated CCTV network.
          </div>
        )}
      </div>

      <CamMap cameras={cams} route={route} height="calc(100vh - 108px)" />
      {zoom && (
        <div className="lightbox" onClick={() => setZoom(null)}>
          <img src={zoom} alt="" />
        </div>
      )}
    </div>
  );
}
