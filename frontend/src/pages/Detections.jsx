import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadFile, fmtTime } from "../api";
import { PlateChip } from "../components/PlateChip.jsx";

const dur = (a, b) => {
  const norm = (t) => new Date(t.endsWith?.("Z") || t.includes("+") ? t : t + "Z");
  const s = Math.max(0, (norm(b) - norm(a)) / 1000);
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${(s / 3600).toFixed(1)}h`;
  return `${(s / 86400).toFixed(1)}d`;
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

const MODES = {
  // Three levels of the same data. Vehicles is the default because the
  // operational question is "which vehicles have we seen", not "how many
  // frames matched" — a vehicle looping past one camera all afternoon is one
  // row here and dozens at the levels below.
  vehicles: {
    label: "Vehicles",
    title: "Vehicles seen",
    blurb: (
      <>
        <b>Vehicles.</b> One row per registration number, however many times it was read.
        Shows total reads, how many cameras saw it, the full time span and where it was last
        seen. Drill into <b>sightings</b> for each visit, or <b>raw reads</b> for the
        frame-by-frame evidence trail.
      </>
    ),
  },
  sightings: {
    label: "Sightings",
    title: "Vehicle sightings",
    blurb: (
      <>
        <b>Sightings.</b> One row per visit — consecutive reads of the same vehicle at the
        same camera collapsed into a single window, showing where it was and for how long.
      </>
    ),
  },
  raw: {
    label: "Raw reads",
    title: "ANPR reads",
    blurb: (
      <>
        <b>Raw reads.</b> Every individual frame-level detection, unaggregated — the evidence
        trail behind each sighting, and what the output report exports.
      </>
    ),
  },
};

export function Detections() {
  const [mode, setMode] = useState("vehicles");
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
        const fetchRows =
          mode === "vehicles" ? api.vehicles({ ...params, hours: 168, limit: 200 })
          : mode === "sightings" ? api.sightings({ ...params, hours: 168, limit: 200 })
          : api.detections({ ...params, limit: 200 });
        const [data, cameras] = await Promise.all([fetchRows, api.cameras()]);
        if (stop) return;
        setRows(data);
        setCams(Object.fromEntries(cameras.map((c) => [c.id, c])));
      } catch { /* transient */ }
    };
    load();
    const t = setInterval(load, 12000);
    return () => { stop = true; clearInterval(t); };
  }, [mode, plate, camId]);

  const totalReads = mode === "raw" ? rows.length : rows.reduce((s, r) => s + (r.reads || 0), 0);
  const m = MODES[mode];

  return (
    <>
      <div className="explainer">
        <span className="ico">⌗</span>
        <div>{m.blurb}</div>
      </div>

      <div className="panel">
        <div className="panel-head">
          {m.title}
          <div className="seg-toggle" style={{ marginLeft: 10 }}>
            {Object.entries(MODES).map(([key, cfg]) => (
              <button key={key} className={mode === key ? "on" : ""} onClick={() => setMode(key)}>
                {cfg.label}
              </button>
            ))}
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
            {rows.length} {mode === "vehicles" ? "vehicles" : mode === "sightings" ? "sightings" : "reads"}
            {mode !== "raw" && rows.length ? ` · ${totalReads} reads` : ""}
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
            {mode === "vehicles" ? (
              <tr>
                <th>Evidence</th><th>Vehicle</th><th>Last seen at</th><th>Active period</th>
                <th>Reads</th><th>Cameras</th><th>Best read</th><th>Trace</th>
              </tr>
            ) : mode === "sightings" ? (
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
            {mode === "vehicles" && rows.map((v) => (
              <tr key={v.plate} className="sighting-row">
                <td>
                  {v.snapshot ? (
                    <img className="evidence-thumb" src={v.snapshot} loading="lazy"
                      alt={`Plate crop for ${v.plate}`} onClick={() => setZoom(v.snapshot)} />
                  ) : <div className="evidence-none">NONE</div>}
                </td>
                <td>
                  <PlateChip plate={v.plate} />
                  {v.watchlisted && <div><span className="badge high">watchlisted</span></div>}
                </td>
                <td>
                  {v.last_camera}
                  <div className="small dim">{v.last_location}</div>
                </td>
                <td className="window-cell">
                  {fmtTime(v.last_seen)}
                  <div className="dur">spanning {dur(v.first_seen, v.last_seen)}</div>
                </td>
                <td><span className="reads-pill">{v.reads}×</span></td>
                <td>
                  <span className="hit-count" title={`Seen by camera ids ${v.cameras.join(", ")}`}>
                    {v.camera_count}
                  </span>
                </td>
                <td><Confidence value={v.best_conf} /></td>
                <td>
                  <Link to={`/trace?plate=${v.plate}`} className="small" style={{ color: "var(--amber)" }}>
                    trace →
                  </Link>
                </td>
              </tr>
            ))}

            {mode === "sightings" && rows.map((s, i) => (
              <tr key={i} className="sighting-row">
                <td>
                  {s.snapshot ? (
                    <img className="evidence-thumb" src={`/data/${s.snapshot}`} loading="lazy"
                      alt={`Plate crop for ${s.plate}`} onClick={() => setZoom(`/data/${s.snapshot}`)} />
                  ) : <div className="evidence-none">NONE</div>}
                </td>
                <td><PlateChip plate={s.plate} /></td>
                <td>
                  {s.camera_name}
                  <div className="small dim">{s.location}</div>
                </td>
                <td className="window-cell">
                  {fmtTime(s.first_seen)}
                  <div className="dur">for {dur(s.first_seen, s.last_seen)}</div>
                </td>
                <td><span className="reads-pill">{s.reads}×</span></td>
                <td><Confidence value={s.best_conf} /></td>
                <td>
                  <Link to={`/trace?plate=${s.plate}`} className="small" style={{ color: "var(--amber)" }}>
                    trace →
                  </Link>
                </td>
              </tr>
            ))}

            {mode === "raw" && rows.map((d) => {
              const c = cams[d.camera_id];
              const votes = d.track_id?.startsWith("votes:") ? d.track_id.slice(6) : "1";
              return (
                <tr key={d.id}>
                  <td>
                    {d.snapshot_path ? (
                      <img className="evidence-thumb" src={`/data/${d.snapshot_path}`} loading="lazy"
                        alt={`Plate crop for ${d.plate_text}`}
                        onClick={() => setZoom(`/data/${d.snapshot_path}`)} />
                    ) : <div className="evidence-none">NONE</div>}
                  </td>
                  <td><PlateChip plate={d.plate_text} /></td>
                  <td>
                    {c?.name ?? `#${d.camera_id}`}
                    <div className="small dim">{c?.location}</div>
                  </td>
                  <td className="mono small">{fmtTime(d.ts)}</td>
                  <td><Confidence value={d.plate_conf} /></td>
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
              <tr><td colSpan={8}>
                <div className="empty-state">
                  <div className="big">Nothing to show</div>
                  No plate reads match this filter yet.
                </div>
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {zoom && (
        <div className="lightbox" onClick={() => setZoom(null)}>
          <img src={zoom} alt="Plate evidence, full size" />
        </div>
      )}
    </>
  );
}
