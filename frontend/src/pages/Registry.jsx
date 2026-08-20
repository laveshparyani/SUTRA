import { useEffect, useState } from "react";
import { api, fmtTime } from "../api";
import { useAuth } from "../auth.jsx";

export function Registry() {
  const { canOperate } = useAuth();
  const [cams, setCams] = useState([]);
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [discovering, setDiscovering] = useState(false);
  const [sched, setSched] = useState(null);

  const load = () => {
    api.cameras().then(setCams).catch(() => {});
    api.schedulerStatus().then(setSched).catch(() => {});
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  async function toggle(cam) {
    setBusyId(cam.id);
    try {
      cam.monitoring ? await api.stopCam(cam.id) : await api.startCam(cam.id);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  async function discover() {
    setDiscovering(true);
    try {
      await api.discover();
      await load();
    } finally {
      setDiscovering(false);
    }
  }

  async function startAll() {
    setDiscovering(true);
    try {
      await api.startAll();
      await load();
    } finally {
      setDiscovering(false);
    }
  }

  async function togglePin(cam) {
    const pinned = sched?.pinned?.includes(cam.id);
    await (pinned ? api.unpinCam(cam.id) : api.pinCam(cam.id));
    await load();
  }

  const depts = [...new Set(cams.map((c) => c.department))].sort();
  const shown = cams.filter(
    (c) =>
      (!dept || c.department === dept) &&
      (!q || (c.name + c.location + c.external_id).toLowerCase().includes(q.toLowerCase()))
  );

  return (
    <div className="panel">
      <div className="panel-head">
        Asset Registry
        {sched && (
          <span className="badge neutral" title="Adaptive ingest scheduler: live connections are time-multiplexed within the concurrency budget">
            slots {(sched.residents?.length ?? 0) + (sched.active_rotating?.length ?? 0)}/{sched.budget} · queue {sched.queued?.length ?? 0}
            {sched.boosted && Object.keys(sched.boosted).length > 0 && " · ⚡boost"}
          </span>
        )}
        <span className="spacer" />
        <input placeholder="search…" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 180, padding: "5px 9px" }} />
        <select value={dept} onChange={(e) => setDept(e.target.value)} style={{ padding: "5px 9px" }}>
          <option value="">All departments</option>
          {depts.map((d) => <option key={d}>{d}</option>)}
        </select>
        {canOperate && (
          <>
            <button className="btn sm" onClick={discover} disabled={discovering}>
              {discovering ? "…" : "⟳ Discover"}
            </button>
            <button className="btn sm primary" onClick={startAll} disabled={discovering}>
              ▶ Monitor All
            </button>
          </>
        )}
      </div>
      <table className="grid">
        <thead>
          <tr>
            <th>ID</th>
            <th>Camera</th>
            <th>Department</th>
            <th>District</th>
            <th>Source</th>
            <th>Health</th>
            <th>Last Frame</th>
            <th>Ingest</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {shown.map((c) => (
            <tr key={c.id}>
              <td className="mono dim">{c.external_id}</td>
              <td>
                {c.name}
                <div className="small dim">{c.location}</div>
              </td>
              <td>{c.department}</td>
              <td>{c.district || "—"}</td>
              <td className="mono small">
                {c.source_type}
                <div className="dim">{c.codec || "?"}/{c.container || "?"}</div>
              </td>
              <td>
                <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <span className={`led ${c.health === "ok" ? "ok" : c.health === "degraded" ? "warn" : c.health === "down" ? "down" : "idle"}`} />
                  {c.health}
                </span>
              </td>
              <td className="mono small dim">{fmtTime(c.last_frame_at)}</td>
              <td className="mono small">{c.ingest_fps ? `${c.ingest_fps} fps` : "—"}</td>
              <td>
                {canOperate && (
                  <span style={{ display: "flex", gap: 6 }}>
                    <button
                      className={`btn sm${c.monitoring ? " danger" : ""}`}
                      onClick={() => toggle(c)}
                      disabled={busyId === c.id}
                    >
                      {busyId === c.id ? "…" : c.monitoring ? "Stop" : "Monitor"}
                    </button>
                    {c.monitoring && c.source_type !== "file" && (
                      <button
                        className="btn sm"
                        title="Pinned cameras hold a permanent ingest slot"
                        onClick={() => togglePin(c)}
                      >
                        {sched?.pinned?.includes(c.id) ? "★" : "☆"}
                      </button>
                    )}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
