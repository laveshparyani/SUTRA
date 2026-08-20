import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, fmtTime } from "../api";
import { CamMap } from "../components/CamMap.jsx";
import { PlateChip } from "../components/PlateChip.jsx";

export function Trace() {
  const [params] = useSearchParams();
  const [plate, setPlate] = useState(params.get("plate") ?? "");
  const [route, setRoute] = useState(null);
  const [busy, setBusy] = useState(false);
  const [zoom, setZoom] = useState(null);

  async function search(e) {
    e?.preventDefault();
    if (!plate.trim()) return;
    setBusy(true);
    try {
      setRoute(await api.route(plate.trim()));
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

      <CamMap cameras={[]} route={route} height="calc(100vh - 108px)" />
      {zoom && (
        <div className="lightbox" onClick={() => setZoom(null)}>
          <img src={zoom} alt="" />
        </div>
      )}
    </div>
  );
}
