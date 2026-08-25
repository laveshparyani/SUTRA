import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtDayTime, fmtTime } from "../api";
import { useAuth } from "../auth.jsx";
import { PlateChip } from "../components/PlateChip.jsx";
import { useAlerts } from "../ws.jsx";

/** Relative age, so an operator reads "4m ago" instead of doing date arithmetic. */
function ago(ts) {
  if (!ts) return "—";
  const secs = (Date.now() - new Date(ts.endsWith?.("Z") || ts.includes("+") ? ts : ts + "Z")) / 1000;
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

/** Says so when a hit is an OCR inference rather than a character-exact read.
 *  A stolen-vehicle alert an operator may act on must never present a
 *  one-character guess as a confirmed identification. */
function MatchNote({ plate, readAs, match }) {
  if (match !== "probable") return null;
  const others = (readAs ?? []).filter((p) => p && p !== plate);
  return (
    <div className="small" style={{ color: "var(--warn, #e0a030)", marginTop: 3 }}>
      <span title="Matched after folding OCR-confusable characters (O/0, I/1, B/8…)">
        ⚠ probable match
      </span>
      {others.length > 0 && (
        <> · read as <span className="mono">{others.join(", ")}</span></>
      )}
    </div>
  );
}

export function Alerts() {
  const { canOperate } = useAuth();
  const [episodes, setEpisodes] = useState([]);
  const [raw, setRaw] = useState([]);
  const [mode, setMode] = useState("episodes");   // episodes = one row per vehicle+camera
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [busy, setBusy] = useState(null);
  const [zoom, setZoom] = useState(null);
  const [detail, setDetail] = useState({});
  const { live } = useAlerts();

  const load = async () => {
    if (mode === "episodes") {
      setEpisodes(await api.alertEpisodes({ hours: 168, limit: 200 }));
      return;
    }
    const [alerts, dets, wl, cams] = await Promise.all([
      api.alerts({ limit: 200 }),
      api.detections({ limit: 800 }),
      api.watchlist(),
      api.cameras(),
    ]);
    setRaw(alerts);
    setDetail({
      det: Object.fromEntries(dets.map((d) => [d.id, d])),
      wl: Object.fromEntries(wl.map((w) => [w.id, w])),
      cam: Object.fromEntries(cams.map((c) => [c.id, c])),
    });
  };

  useEffect(() => {
    load().catch(() => {});
    const t = setInterval(() => load().catch(() => {}), 15000);
    return () => clearInterval(t);
  }, [mode, live.length]);

  async function ackEpisode(ep) {
    setBusy(ep.latest_alert_id);
    try {
      await api.ackEpisode(ep.alert_ids);
      await load();
    } finally {
      setBusy(null);
    }
  }

  async function ackOne(id) {
    setBusy(id);
    try {
      await api.ackAlert(id);
      await load();
    } finally {
      setBusy(null);
    }
  }

  const shown = mode === "episodes" ? episodes.filter((e) => !onlyOpen || e.unacknowledged > 0) : raw;
  const openCount = episodes.reduce((n, e) => n + (e.unacknowledged > 0 ? 1 : 0), 0);
  const totalHits = episodes.reduce((n, e) => n + e.count, 0);

  return (
    <>
      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="panel-head">
          <span className="led down" /> Alert Centre
          <span className="spacer" />
          <div className="seg-toggle" style={{ marginLeft: 10 }}>
            <button className={mode === "episodes" ? "on" : ""} onClick={() => setMode("episodes")}>
              Episodes
            </button>
            <button className={mode === "raw" ? "on" : ""} onClick={() => setMode("raw")}>
              Every hit
            </button>
          </div>
          {mode === "episodes" && (
            <label className="small" style={{ display: "flex", gap: 6, alignItems: "center", color: "var(--text-1)" }}>
              <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
              needs action only
            </label>
          )}
        </div>
      </div>

      <div className="explainer">
        <span className="ico">▲</span>
        <div>
          {mode === "episodes" ? (
            <>
              <b>Alert episodes.</b> A watchlisted vehicle standing in one camera's view
              re-triggers every cooldown window, so these <b>{episodes.length} episodes</b>{" "}
              summarise <b>{totalHits} individual hits</b> — one row per vehicle per camera with
              its time window and how many hits are still unacknowledged.
              {openCount > 0 && <> <b>{openCount} need action.</b></>}
            </>
          ) : (
            <>
              <b>Every hit.</b> Each individual alert, newest first — the audit trail behind
              the episode summary. Switch to <b>episodes</b> for the operational view.
            </>
          )}
        </div>
      </div>

      <div className="panel">
        {mode === "episodes" ? (
          <table className="grid">
            <thead>
              <tr>
                <th>Evidence</th>
                <th>Vehicle</th>
                <th>Why</th>
                <th>Where</th>
                <th>When</th>
                <th>Hits</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {shown.map((ep) => (
                <tr key={`${ep.plate}-${ep.camera_id}-${ep.latest_alert_id}`}>
                  <td>
                    {ep.snapshot && (
                      <img src={ep.snapshot} alt={`Evidence for ${ep.plate}`} className="evidence-thumb"
                        onClick={() => setZoom(ep.snapshot)} />
                    )}
                  </td>
                  <td>
                    <PlateChip plate={ep.plate} />
                    <MatchNote plate={ep.plate} readAs={ep.read_as} match={ep.match_type} />
                    <div className="small">
                      <Link to={`/trace?plate=${ep.plate}`} style={{ color: "var(--amber)" }}>trace route →</Link>
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${ep.severity}`}>{ep.reason}</span>
                    {ep.fir_ref && <div className="small dim mono">{ep.fir_ref}</div>}
                  </td>
                  <td>
                    {ep.camera_name}
                    <div className="small dim">{ep.location}</div>
                  </td>
                  <td className="mono small">
                    {ago(ep.last_seen)}
                    {ep.count > 1 && (
                      <div className="dim">since {fmtDayTime(ep.first_seen)}</div>
                    )}
                  </td>
                  <td>
                    <span className="hit-count" title={`${ep.count} alerts in this episode`}>
                      {ep.count}×
                    </span>
                  </td>
                  <td>
                    {ep.unacknowledged > 0 ? (
                      <span className="badge high">{ep.unacknowledged} open</span>
                    ) : (
                      <span className="badge ok">cleared</span>
                    )}
                  </td>
                  <td>
                    {canOperate && ep.unacknowledged > 0 && (
                      <button className="btn sm" disabled={busy === ep.latest_alert_id}
                        onClick={() => ackEpisode(ep)}>
                        {busy === ep.latest_alert_id ? "…" : `Ack all ${ep.unacknowledged}`}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {shown.length === 0 && (
                <tr><td colSpan={8}>
                  <div className="empty-state">
                    <div className="big">{onlyOpen ? "Nothing needs action" : "No alerts"}</div>
                    Continuous watchlist correlation is running.
                  </div>
                </td></tr>
              )}
            </tbody>
          </table>
        ) : (
          <table className="grid">
            <thead>
              <tr><th>Evidence</th><th>Plate</th><th>Reason</th><th>Camera</th><th>Time</th><th>Severity</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {raw.map((a) => {
                const d = detail.det?.[a.detection_id];
                const w = detail.wl?.[a.watchlist_id];
                const c = d && detail.cam?.[d.camera_id];
                return (
                  <tr key={a.id}>
                    <td>
                      {d?.snapshot_path && (
                        <img src={`/data/${d.snapshot_path}`} alt="" className="evidence-thumb"
                          onClick={() => setZoom(`/data/${d.snapshot_path}`)} />
                      )}
                    </td>
                    <td>
                      {/* the watchlisted vehicle is the subject of the alert;
                          the camera's raw read is shown beneath it when the two
                          differ, so this view and the episode view can never
                          appear to disagree about which vehicle was hit */}
                      <PlateChip plate={w?.plate ?? d?.plate_text} />
                      <MatchNote plate={w?.plate} readAs={[d?.plate_text]} match={a.match_type} />
                    </td>
                    <td><span className={`badge ${a.severity}`}>{w?.reason ?? "—"}</span></td>
                    <td>{c ? <>{c.name}<div className="small dim">{c.location}</div></> : "—"}</td>
                    <td className="mono small">{fmtTime(a.ts)}</td>
                    <td><span className={`badge ${a.severity}`}>{a.severity}</span></td>
                    <td><span className={`badge ${a.status === "new" ? "high" : "ok"}`}>{a.status}</span></td>
                    <td>
                      {a.status === "new" && canOperate && (
                        <button className="btn sm" disabled={busy === a.id} onClick={() => ackOne(a.id)}>
                          {busy === a.id ? "…" : "Ack"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {zoom && (
        <div className="lightbox" onClick={() => setZoom(null)}>
          <img src={zoom} alt="Alert evidence, full size" />
        </div>
      )}
    </>
  );
}
