import { useEffect, useState } from "react";
import { api, fmtTime } from "../api";
import { useAuth } from "../auth.jsx";
import { PlateChip } from "../components/PlateChip.jsx";
import { useAlerts } from "../ws.jsx";

export function Alerts() {
  const { canOperate } = useAuth();
  const [rows, setRows] = useState([]);
  const [detail, setDetail] = useState({});
  const [zoom, setZoom] = useState(null);
  const { live } = useAlerts();

  const load = async () => {
    const alerts = await api.alerts({ limit: 100 });
    setRows(alerts);
    // hydrate detections + watchlist for display
    const [dets, wl, cams] = await Promise.all([
      api.detections({ limit: 500 }),
      api.watchlist(),
      api.cameras(),
    ]);
    setDetail({
      det: Object.fromEntries(dets.map((d) => [d.id, d])),
      wl: Object.fromEntries(wl.map((w) => [w.id, w])),
      cam: Object.fromEntries(cams.map((c) => [c.id, c])),
    });
  };

  useEffect(() => {
    load().catch(() => {});
  }, [live.length]);

  async function ack(id) {
    await api.ackAlert(id);
    load().catch(() => {});
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="led down" /> Alert Log
        <span className="spacer" />
        <span className="dim small">{rows.length} shown</span>
      </div>
      <table className="grid">
        <thead>
          <tr>
            <th>Evidence</th>
            <th>Plate</th>
            <th>Reason</th>
            <th>Camera</th>
            <th>Time</th>
            <th>Severity</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => {
            const d = detail.det?.[a.detection_id];
            const w = detail.wl?.[a.watchlist_id];
            const c = d && detail.cam?.[d.camera_id];
            return (
              <tr key={a.id}>
                <td>
                  {d?.snapshot_path && (
                    <img
                      src={`/data/${d.snapshot_path}`}
                      alt=""
                      style={{ height: 30, borderRadius: 3, cursor: "zoom-in", border: "1px solid var(--line-bright)" }}
                      onClick={() => setZoom(`/data/${d.snapshot_path}`)}
                    />
                  )}
                </td>
                <td><PlateChip plate={d?.plate_text ?? w?.plate} /></td>
                <td>
                  <span className={`badge ${a.severity}`}>{w?.reason ?? "—"}</span>
                  {w?.fir_ref && <div className="small dim mono">{w.fir_ref}</div>}
                </td>
                <td>
                  {c ? (
                    <>
                      {c.name}
                      <div className="small dim">{c.location}</div>
                    </>
                  ) : "—"}
                </td>
                <td className="mono small">{fmtTime(a.ts)}</td>
                <td><span className={`badge ${a.severity}`}>{a.severity}</span></td>
                <td>
                  <span className={`badge ${a.status === "new" ? "high" : "ok"}`}>{a.status}</span>
                </td>
                <td>
                  {a.status === "new" && canOperate && (
                    <button className="btn sm" onClick={() => ack(a.id)}>Ack</button>
                  )}
                </td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={8}>
                <div className="empty-state">
                  <div className="big">No alerts recorded</div>
                </div>
              </td>
            </tr>
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
