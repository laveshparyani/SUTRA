import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

// Browsers allow ~6 concurrent connections per host and an MJPEG stream holds
// one open indefinitely. Rendering a tile per camera therefore starves every
// other API call on the page, so only cameras actually delivering frames get a
// stream, and the grid is capped.
//
// The cap must stay BELOW that ceiling, not equal to it: at 6 the streams owned
// the entire pool, so this page's own 8-second refresh — and any navigation
// afterwards, including the login POST — queued behind them and never
// completed. The wall then rendered "no cameras onboarded" over a healthy core.
// Two spare connections keep the page able to talk to the API while watching.
const MAX_STREAMS = 4;

// A frame older than this is no longer "now". Ingest runs at 1 fps, so several
// seconds of silence already means the source has stopped feeding us; the
// previous 30 s tolerance let a tile hold a LIVE badge over a frozen picture,
// which is the exact dishonesty this page is supposed to avoid.
const STALE_AFTER_S = 8;

const STATES = {
  live: { cls: "ok", label: "Live", why: "delivering frames right now" },
  stalled: { cls: "warn", label: "Stalled", why: "last frame is seconds old — the source stopped feeding" },
  connecting: { cls: "warn", label: "Connecting", why: "holds an ingest slot, waiting for the first frame" },
  unreachable: { cls: "down", label: "Unreachable", why: "holds a slot but the source refuses the connection" },
  queued: { cls: "idle", label: "Queued", why: "in the pool, waiting for an ingest slot to free up" },
  off: { cls: "idle", label: "Not pooled", why: "monitoring is switched off for this camera" },
  central: {
    cls: "idle",
    label: "Edge-hosted",
    why: "video decodes on the edge node it belongs to; this command tier receives its detections, alerts and evidence",
  },
};

/** Truth comes from the ingest workers, not the cached health column: a camera
 *  either holds a slot right now (and is connecting, stalled or being refused)
 *  or it is waiting for one. On the central tier there are no ingest workers at
 *  all — video never leaves the edge — so "queued" would be a lie: no slot is
 *  ever going to free up here. Those tiles say what is actually happening. */
function stateOf(cam, worker, central) {
  if (worker?.has_frame) return worker.stale ? "stalled" : "live";
  if (central) return "central";
  if (!cam.monitoring) return "off";
  if (worker) return worker.last_error ? "unreachable" : "connecting";
  return "queued";
}

function Feed({ cam, worker, scene, central }) {
  const [err, setErr] = useState(false);
  const imgRef = useRef(null);
  useEffect(() => {
    if (!err) return;
    const t = setTimeout(() => setErr(false), 10000);   // a dropped stream must not blank the tile forever
    return () => clearTimeout(t);
  }, [err]);

  // An MJPEG response never ends, so dropping the <img> from the tree does not
  // reliably free its socket — abandoned streams were observed outliving the
  // render that created them, pushing the tab past the per-host connection
  // limit even while the tile count stayed within it. Clearing src on the way
  // out aborts the request explicitly.
  useEffect(() => () => {
    if (imgRef.current) imgRef.current.src = "";
  }, []);

  const state = stateOf(cam, worker, central);
  const st = STATES[state];
  const showStream = state === "live" && !err;
  // a stalled tile names how long it has been frozen — "17s since last frame"
  // tells an operator whether to wait or escalate; "Stalled" alone does not
  const detail =
    state === "unreachable" && worker?.last_error
      ? worker.last_error
      : state === "stalled" && worker?.frame_age_s != null
        ? `${Math.round(worker.frame_age_s)}s since the last frame`
        : st.why;

  return (
    <div className="feed">
      {showStream ? (
        <>
          {/* preview=1 serves a 480px copy encoded once per frame and shared by
              all viewers: a wall of full-res MJPEG saturates the browser's
              decode budget and shows no more detail at tile size. */}
          <img ref={imgRef} src={`/api/bridge/cameras/${cam.id}/mjpeg?preview=1`}
            alt={`${cam.name} live view`} onError={() => setErr(true)} />
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
  const [central, setCentral] = useState(false);
  // null until the first load settles: an empty grid means "nothing onboarded"
  // only once we have actually heard back from the core
  const [loadFailed, setLoadFailed] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [cameras, bridge, scene, health] = await Promise.all([
          api.cameras(),
          api.bridgeStatus(),
          fetch("/api/insight/scene").then((r) => (r.ok ? r.json() : { cameras: {} })),
          fetch("/api/health").then((r) => (r.ok ? r.json() : {})),
        ]);
        setCentral(health.role === "central");
        setCams(cameras);
        setScenes(scene.cameras || {});
        setWorkers(Object.fromEntries(bridge.workers.map((w) => [
          w.camera_id,
          {
            ...w,
            // a frame we still hold but that has stopped refreshing stays
            // visible (the last picture is evidence) and is labelled stalled
            // rather than live
            has_frame: w.has_frame && w.frame_age_s != null,
            stale: w.frame_age_s == null || w.frame_age_s >= STALE_AFTER_S,
          },
        ])));
        setLoadFailed(false);
      } catch {
        // keep whatever was last shown; the grid must not claim the registry is
        // empty just because this request could not be answered
        setLoadFailed(true);
      }
    };
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  const depts = [...new Set(cams.map((c) => c.department))].sort();
  const inDept = (c) => !dept || c.department === dept;

  const shown = cams.filter(inDept);
  // only genuinely-live cameras earn a stream slot: a frozen source would
  // otherwise hold a connection a moving one could use
  const liveCams = shown.filter((c) => stateOf(c, workers[c.id], central) === "live").slice(0, MAX_STREAMS);
  const liveIds = new Set(liveCams.map((c) => c.id));
  // non-streaming tiles are plain markup and cost no connections, so show them all
  const others = shown.filter((c) => !liveIds.has(c.id));

  const counts = shown.reduce((acc, c) => {
    const s = stateOf(c, workers[c.id], central);
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, {});
  const unreachable = counts.unreachable ?? 0;

  return (
    <>
      <div className="explainer">
        <span className="ico">▦</span>
        <div>
          {central ? (
            <>
              <b>This is the command tier — video stays at the edge.</b> SUTRA
              deliberately never streams video to the centre: 80,000 cameras of
              footage would saturate any statewide link, so edge nodes decode
              locally and push up only what commands need — detections, alerts
              and evidence, within seconds. Every camera below is doing exactly
              that; see <Link to="/detections">Detections</Link> and{" "}
              <Link to="/alerts">Alerts</Link> for what they are producing right
              now. Live tiles appear on the edge node's own wall.
            </>
          ) : (
            <>
          <b>Live viewing of federated feeds.</b> Only cameras currently delivering
          frames carry a video stream — a browser allows about six simultaneous
          connections per host, so SUTRA streams at most {MAX_STREAMS} and keeps the rest
          free for the page's own data. The other tiles are labelled honestly
          rather than shown as black rectangles pretending to be live.
            </>
          )}
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
          {central
            ? `command tier — metadata view · showing all ${shown.length} cameras`
            : `streaming ${liveCams.length} of ${MAX_STREAMS} slots · showing all ${shown.length} cameras`}
        </span>
      </div>

      <div className="wall">
        {liveCams.map((cam) => (
          <Feed cam={cam} worker={workers[cam.id]} scene={scenes[cam.id]} central={central} key={cam.id} />
        ))}
        {others.map((cam) => (
          <Feed cam={cam} worker={workers[cam.id]} scene={scenes[cam.id]} central={central} key={cam.id} />
        ))}
        {cams.length === 0 && (
          <div className="empty-state" style={{ gridColumn: "1/-1" }}>
            {loadFailed === false ? (
              <>
                <div className="big">No cameras onboarded</div>
                Use <Link to="/registry" style={{ color: "var(--amber)" }}>Registry</Link> to discover
                or import cameras.
              </>
            ) : loadFailed ? (
              <>
                <div className="big">Cannot reach the core</div>
                The registry could not be read, so this grid is showing nothing rather than
                guessing. Retrying every 8 seconds.
              </>
            ) : (
              <div className="big">Loading cameras…</div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
