import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtTime } from "../api";
import { PlateChip } from "../components/PlateChip.jsx";

export function Detections() {
  const [rows, setRows] = useState([]);
  const [cams, setCams] = useState({});
  const [plate, setPlate] = useState("");
  const [camId, setCamId] = useState("");
  const [zoom, setZoom] = useState(null);

  const load = async () => {
    const params = { limit: 200 };
    if (plate.trim()) params.plate = plate.trim();
    if (camId) params.camera_id = camId;
    const [dets, cameras] = await Promise.all([api.detections(params), api.cameras()]);
    setRows(dets);
    setCams(Object.fromEntries(cameras.map((c) => [c.id, c])));
  };

  useEffect(() => {
    load().catch(() => {});
    const t = setInterval(() => load().catch(() => {}), 10000);
    return () => clearInterval(t);
  }, [plate, camId]);

  return (
    <div className="panel">
      <div className="panel-head">
        ANPR Detections
        <span className="spacer" />
        <input
          placeholder="filter plate…"
          value={plate}
          onChange={(e) => setPlate(e.target.value.toUpperCase())}
          style={{ width: 150, padding: "5px 9px", textTransform: "uppercase" }}
        />
        <select value={camId} onChange={(e) => setCamId(e.target.value)} style={{ padding: "5px 9px" }}>
          <option value="">All cameras</option>
          {Object.values(cams).map((c) => (
            <option key={c.id} value={c.id}>{c.name} — {c.location}</option>
          ))}
        </select>
        <span className="dim small">{rows.length} shown</span>
      </div>
      <table className="grid">
        <thead>
          <tr>
            <th>Evidence</th>
            <th>Plate</th>
            <th>Camera</th>
            <th>Time</th>
            <th>OCR Conf</th>
            <th>Reads</th>
            <th>Trace</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => {
            const c = cams[d.camera_id];
            const votes = d.track_id?.startsWith("votes:") ? d.track_id.slice(6) : "1";
            return (
              <tr key={d.id}>
                <td>
                  {d.snapshot_path && (
                    <img
                      src={`/data/${d.snapshot_path}`}
                      alt=""
                      style={{ height: 28, borderRadius: 3, cursor: "zoom-in", border: "1px solid var(--line-bright)" }}
                      onClick={() => setZoom(`/data/${d.snapshot_path}`)}
                    />
                  )}
                </td>
                <td><PlateChip plate={d.plate_text} /></td>
                <td>
                  {c?.name ?? `#${d.camera_id}`}
                  <div className="small dim">{c?.location}</div>
                </td>
                <td className="mono small">{fmtTime(d.ts)}</td>
                <td className="mono small">{d.plate_conf != null ? `${(d.plate_conf * 100).toFixed(0)}%` : "—"}</td>
                <td className="mono small dim">{votes}×</td>
                <td>
                  <Link to={`/trace?plate=${d.plate_text}`} className="small" style={{ color: "var(--amber)" }}>
                    trace →
                  </Link>
                </td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr><td colSpan={7}><div className="empty-state"><div className="big">No detections</div></div></td></tr>
          )}
        </tbody>
      </table>
      {zoom && (
        <div className="lightbox" onClick={() => setZoom(null)}>
          <img src={zoom} alt="" />
        </div>
      )}
    </div>
  );
}
