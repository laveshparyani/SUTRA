import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadFile, fmtTime } from "../api";
import { PlateChip } from "../components/PlateChip.jsx";

const dur = (a, b) => {
  const s = Math.max(0, (new Date(b + "Z") - new Date(a + "Z")) / 1000);
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${(s / 3600).toFixed(1)}h`;
};

function Confidence({ value }) {
  if (value == null) return <span className="dim">—</span>;
  const pct = Math.round(value * 100);
  const color =
    pct >= 90 ? "var(--status-good)" : pct >= 75 ? "var(--seq-3)" : pct >= 60 ? "var(--status-warning)" : "var(--status-serious)";
  return (
    <span className="conf-meter" title={`OCR confidence ${pct}%`}>
      <span className="track"><span className="fill" style={{ width: `${pct}%`, background: color }} /></span>
      <span className="mono small">{pct}%</span>
    </span>
  );
}

export function Detections() {
  const [mode, setMode] = useState("grouped");   // grouped = vehicle sightings
  const [rows, setRows] = useState([]);
  const [cams, setCams] = useState({});
  const [plate, setPlate] = useState("");
  const [camId, setCamId] = useState("");
  const [zoom, setZoom] = useState(null);

  useEffect(() => {
    let stop = false;
    const load = async () => {
      const params = {};
      if (plate.trim()) params.plate = plate.trim();
      if (camId) params.camera_id = camId;
      try {
        const [data, cameras] = await Promise.all([
          mode === "grouped"
            ? api.sightings({ ...params, hours: 168, limit: 200 })
            : api.detections({ ...params, limit: 200 }),
          api.cameras(),
        ]);
        if (stop) return;
        setRows(data);
        setCams(Object.fromEntries(cameras.map((c) => [c.id, c])));
      } catch { /* transient */ }
    };
    load();
    const t = setInterval(load, 12000);
    return () => { stop = true; clearInterval(t); };
  }, [mode, plate, camId]);

  const grouped = mode === "grouped";
  const totalReads = grouped ? rows.reduce((s, r) => s + r.reads, 0) : rows.length;

  return (
    <>
      <div className="explainer">
        <span className="ico">⌗</span>
        <div>
          {grouped ? (
            <>
              <b>Vehicle sightings.</b> A vehicle in view produces dozens of near-identical
              reads, so consecutive reads of the same plate on the same camera are grouped
              into one sighting — showing where it was, for how long, and how many reads
              back it. Switch to <b>raw reads</b> for the frame-by-frame audit trail.
            </>
          ) : (
            <>
              <b>Raw reads.</b> Every individual frame-level detection, unaggregated —
              the evidence trail behind each sighting. Switch to <b>sightings</b> for the
              operational view.
            </>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          {grouped ? "Vehicle sightings" : "ANPR reads"}
          <div className="seg-toggle" style={{ marginLeft: 10 }}>
            <button className={grouped ? "on" : ""} onClick={() => setMode("grouped")}>Sightings</button>
            <button className={!grouped ? "on" : ""} onClick={() => setMode("raw")}>Raw reads</button>
          </div>
          <span className="spacer" />
          <input placeholder="filter plate…" value={plate}
            onChange={(e) => setPlate(e.target.value.toUpperCase())}
            style={{ width: 150, padding: "5px 9px", textTransform: "uppercase" }} />
          <select value={camId} onChange={(e) => setCamId(e.target.value)} style={{ padding: "5px 9px" }}>
            <option value="">All cameras</option>
            {Object.values(cams).map((c) => (
              <option key={c.id} value={c.id}>{c.name} — {c.location}</option>
            ))}
          </select>
          <span className="dim small">
            {rows.length} {grouped ? "sightings" : "reads"}
            {grouped && rows.length ? ` · ${totalReads} reads` : ""}
          </span>
          <button className="btn sm primary"
            title="Detected plates with timestamps — the evaluation output report"
            onClick={() => downloadFile(
              `/api/insight/report?fmt=csv${camId ? `&camera_id=${camId}` : ""}`,
              "sutra_anpr_output_report.csv"
            )}>
            ⬇ Output report
          </button>
        </div>

        <table className="grid">
          <thead>
            {grouped ? (
              <tr>
                <th>Evidence</th><th>Vehicle</th><th>Seen at</th><th>Time window</th>
                <th>Reads</th><th>Best read</th><th>Trace</th>
              </tr>
            ) : (
              <tr>
                <th>Evidence</th><th>Plate</th><th>Camera</th><th>Timestamp</th>
                <th>Confidence</th><th>Votes</th><th>Trace</th>
              </tr>
            )}
          </thead>
          <tbody>
            {grouped
              ? rows.map((s, i) => (
                  <tr key={i} className="sighting-row">
                    <td>
                      {s.snapshot ? (
                        <img className="evidence-thumb" src={`/data/${s.snapshot}`} loading="lazy"
                          alt={`Plate crop for ${s.plate}`}
                          onClick={() => setZoom(`/data/${s.snapshot}`)} />
                      ) : (
                        <div className="evidence-none">NONE</div>
                      )}
                    </td>
                    <td><PlateChip plate={s.plate} /></td>
                    <td>
                      {s.camera_name}
                      <div className="small dim">{s.location}</div>
                    </td>
                    <td className="window-cell">
                      {fmtTime(s.first_seen)}
                      <div className="dur">
                        for {dur(s.first_seen, s.last_seen)} · until {fmtTime(s.last_seen).split(", ")[1]}
                      </div>
                    </td>
                    <td><span className="reads-pill">{s.reads}×</span></td>
                    <td><Confidence value={s.best_conf} /></td>
                    <td>
                      <Link to={`/trace?plate=${s.plate}`} className="small" style={{ color: "var(--amber)" }}>
                        trace →
                      </Link>
                    </td>
                  </tr>
                ))
              : rows.map((d) => {
                  const c = cams[d.camera_id];
                  const votes = d.track_id?.startsWith("votes:") ? d.track_id.slice(6) : "1";
                  return (
                    <tr key={d.id}>
                      <td>
                        {d.snapshot_path ? (
                          <img className="evidence-thumb" src={`/data/${d.snapshot_path}`} loading="lazy"
                            alt={`Plate crop for ${d.plate_text}`}
                            onClick={() => setZoom(`/data/${d.snapshot_path}`)} />
                        ) : (
                          <div className="evidence-none">NONE</div>
                        )}
                      </td>
                      <td><PlateChip plate={d.plate_text} /></td>
                      <td>
                        {c?.name ?? `#${d.camera_id}`}
                        <div className="small dim">{c?.location}</div>
                      </td>
                      <td className="mono small">{fmtTime(d.ts)}</td>
                      <td><Confidence value={d.plate_conf} /></td>
                      <td className="mono small dim" title="frames that voted on this plate">{votes}×</td>
                      <td>
                        <Link to={`/trace?plate=${d.plate_text}`} className="small" style={{ color: "var(--amber)" }}>
                          trace →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7}>
                  <div className="empty-state">
                    <div className="big">Nothing yet</div>
                    {plate || camId
                      ? "No reads match this filter."
                      : "Reads appear here as cameras deliver frames."}
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {zoom && (
        <div className="lightbox" onClick={() => setZoom(null)}>
          <img src={zoom} alt="" />
        </div>
      )}
    </>
  );
}
