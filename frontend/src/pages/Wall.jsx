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
  connecting: { cls: "warn", label: "Connecting", why: "holds an ingest slot, waiting for the first frame" },
  unreachable: { cls: "down", label: "Unreachable", why: "holds a slot but the source refuses the connection" },
  queued: { cls: "idle", label: "Queued", why: "in the pool, waiting for an ingest slot to free up" },
  off: { cls: "idle", label: "Not pooled", why: "monitoring is switched off for this camera" },
};

/** Truth comes from the ingest workers, not the cached health column: a camera
 *  either holds a slot right now (and is connecting or being refused) or it is
 *  waiting for one. */
function stateOf(cam, worker) {
  if (worker?.has_frame) return "live";
  if (!cam.monitoring) return "off";
  if (worker) return worker.last_error ? "unreachable" : "connecting";
  return "queued";
}

function Feed({ cam, worker, scene }) {
  const [err, setErr] = useState(false);
  useEffect(() => {
    if (!err) return;
    const t = setTimeout(() => setErr(false), 10000);   // a dropped stream must not blank the tile forever
    return () => clearTimeout(t);
  }, [err]);

  const state = stateOf(cam, worker);
  const st = STATES[state];
  const showStream = state === "live" && !err;
  const detail = state === "unreachable" && worker?.last_error ? worker.last_error : st.why;

  return (
    <div className="feed">
      {showStream ? (
        <>
          {/* preview=1 serves a 480px copy encoded once per frame and shared by
              all viewers: a wall of full-res MJPEG saturates the browser's
              decode budget and shows no more detail at tile size. */}
          <img src={`/api/bridge/cameras/${cam.id}/mjpeg?preview=1`} alt={`${cam.name} live view`}
            onError={() => setErr(true)} />
          <div className="rec"><i /> LIVE</div>
        </>
      ) : (
        <div className="offline" title={detail}>
          <span>{st.label.toUpperCase()}</span>
          <span className="mono small dim">{detail}</span>
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
  const [workers, setWorkers] = useState({});
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
        setWorkers(Object.fromEntries(bridge.workers.map((w) => [
          w.camera_id,
          { ...w, has_frame: w.has_frame && w.frame_age_s != null && w.frame_age_s < 30 },
        ])));
      } catch { /* transient */ }
    };
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  const depts = [...new Set(cams.map((c) => c.department))].sort();
  const inDept = (c) => !dept || c.department === dept;

  const shown = cams.filter(inDept);
  const liveCams = shown.filter((c) => workers[c.id]?.has_frame).slice(0, MAX_STREAMS);
  const liveIds = new Set(liveCams.map((c) => c.id));
  // non-streaming tiles are plain markup and cost no connections, so show them all
  const others = shown.filter((c) => !liveIds.has(c.id));

  const counts = shown.reduce((acc, c) => {
    const s = stateOf(c, workers[c.id]);
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, {});
  const unreachable = counts.unreachable ?? 0;

  return (
    <>
      <div className="explainer">
        <span className="ico">▦</span>
        <div>
          <b>Live viewing of federated feeds.</b> Only cameras currently delivering
          frames carry a video stream — a browser allows about six simultaneous
          streams per host, so SUTRA streams the live ones and labels the rest
          honestly rather than showing black rectangles that pretend to be live.
          {unreachable > 0 && (
            <>
              {" "}
              <b>{unreachable} source{unreachable > 1 ? "s are" : " is"} refusing connections.</b>{" "}
              SUTRA holds their slots and retries with backoff, so they resume the moment the
              upstream returns — the tile states below are read from the live ingest workers,
              not a cached status.
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
          streaming {liveCams.length} of {MAX_STREAMS} slots · showing all {shown.length} cameras
        </span>
      </div>

      <div className="wall">
        {liveCams.map((cam) => (
          <Feed cam={cam} worker={workers[cam.id]} scene={scenes[cam.id]} key={cam.id} />
        ))}
        {others.map((cam) => (
          <Feed cam={cam} worker={workers[cam.id]} scene={scenes[cam.id]} key={cam.id} />
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
