import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

// Browsers allow ~6 concurrent connections per host and an MJPEG stream holds
// one open indefinitely. Rendering a tile per camera therefore starves every
// other API call on the page, so only cameras actually delivering frames get a
// stream, and the grid is capped.
const MAX_STREAMS = 6;

const STATES = {
  live: { cls: "ok", label: "Live", why: "delivering frames right now" },
  connecting: { cls: "warn", label: "Connecting", why: "socket open, waiting for the first frame" },
  down: { cls: "down", label: "No signal", why: "source refused or dropped the connection" },
  queued: { cls: "idle", label: "Queued", why: "in the pool, waiting for an ingest slot" },
  off: { cls: "idle", label: "Not pooled", why: "monitoring is switched off" },
};

function stateOf(cam, isLive) {
  if (isLive) return "live";
  if (!cam.monitoring) return "off";
  if (cam.health === "down") return "down";
  if (cam.health === "connecting") return "connecting";
  return "queued";
}

function Feed({ cam, isLive, scene }) {
  const [err, setErr] = useState(false);
  useEffect(() => {
    if (!err) return;
    const t = setTimeout(() => setErr(false), 10000);   // a dropped stream must not blank the tile forever
    return () => clearTimeout(t);
  }, [err]);

  const st = STATES[stateOf(cam, isLive)];
  const showStream = isLive && !err;

  return (
    <div className="feed">
      {showStream ? (
        <>
          <img src={`/api/bridge/cameras/${cam.id}/mjpeg`} alt={`${cam.name} live view`}
            onError={() => setErr(true)} />
          <div className="rec"><i /> LIVE</div>
        </>
      ) : (
        <div className="offline" title={st.why}>
          <span>{st.label.toUpperCase()}</span>
          <span className="mono small dim">{st.why}</span>
        </div>
      )}
      <div className="feed-bar">
        <span className={`led ${st.cls}`} />
        <span className="feed-name">{cam.name}</span>
        <span className="dim small" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
          {cam.location}
        </span>
        {scene && (
          <span className="mono small" style={{ color: "var(--series-3)", whiteSpace: "nowrap" }}
            title="Live scene analytics: people and vehicles detected in view">
            {scene.persons}p · {scene.vehicles}v
          </span>
        )}
      </div>
    </div>
  );
}

export function Wall() {
  const [cams, setCams] = useState([]);
  const [flowing, setFlowing] = useState({});
  const [scenes, setScenes] = useState({});
  const [dept, setDept] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [cameras, bridge, scene] = await Promise.all([
          api.cameras(),
          api.bridgeStatus(),
          fetch("/api/insight/scene").then((r) => (r.ok ? r.json() : { cameras: {} })),
        ]);
        setCams(cameras);
        setScenes(scene.cameras || {});
        setFlowing(Object.fromEntries(
          bridge.workers
            .filter((w) => w.has_frame && w.frame_age_s != null && w.frame_age_s < 30)
            .map((w) => [w.camera_id, w.frame_age_s])
        ));
      } catch { /* transient */ }
    };
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  const depts = [...new Set(cams.map((c) => c.department))].sort();
  const inDept = (c) => !dept || c.department === dept;

  const liveCams = cams.filter((c) => inDept(c) && flowing[c.id] != null).slice(0, MAX_STREAMS);
  const liveIds = new Set(liveCams.map((c) => c.id));
  const others = cams.filter((c) => inDept(c) && !liveIds.has(c.id)).slice(0, 11);

  const counts = cams.filter(inDept).reduce((acc, c) => {
    const s = stateOf(c, flowing[c.id] != null);
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, {});

  return (
    <>
      <div className="explainer">
        <span className="ico">▦</span>
        <div>
          <b>Live viewing of federated feeds.</b> Only cameras currently delivering
          frames carry a video stream — a browser allows about six simultaneous
          streams per host, so SUTRA streams the live ones and labels the rest
          honestly rather than showing black rectangles that pretend to be live.
          {counts.down > 0 && (
            <>
              {" "}
              <b>{counts.down} source{counts.down > 1 ? "s are" : " is"} refusing connections</b> —
              the government feed portal is intermittent; SUTRA retries continuously and
              recovers automatically.
            </>
          )}
        </div>
      </div>

      <div className="form-row" style={{ marginBottom: 14 }}>
        <select value={dept} onChange={(e) => setDept(e.target.value)}>
          <option value="">All departments</option>
          {depts.map((d) => <option key={d}>{d}</option>)}
        </select>
        <div className="state-key">
          {Object.entries(STATES).map(([k, v]) =>
            counts[k] ? (
              <span key={k} title={v.why}>
                <i className={`led ${v.cls}`} /> {v.label} <b className="mono">{counts[k]}</b>
              </span>
            ) : null
          )}
        </div>
        <span style={{ flex: 1 }} />
        <span className="dim small">
          streaming {liveCams.length} of {MAX_STREAMS} slots · {cams.filter(inDept).length} cameras in view
        </span>
      </div>

      <div className="wall">
        {liveCams.map((cam) => (
          <Feed cam={cam} isLive scene={scenes[cam.id]} key={cam.id} />
        ))}
        {others.map((cam) => (
          <Feed cam={cam} isLive={false} scene={scenes[cam.id]} key={cam.id} />
        ))}
        {cams.length === 0 && (
          <div className="empty-state" style={{ gridColumn: "1/-1" }}>
            <div className="big">No cameras onboarded</div>
            Use <Link to="/registry" style={{ color: "var(--amber)" }}>Registry</Link> to discover
            or import cameras.
          </div>
        )}
      </div>
    </>
  );
}
