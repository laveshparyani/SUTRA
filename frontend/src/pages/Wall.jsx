import { useEffect, useState } from "react";
import { api } from "../api";

// Browsers allow ~6 concurrent connections per host and an MJPEG stream holds
// one open indefinitely. Rendering a tile per camera therefore starves every
// other API call on the page, so only cameras that are actually delivering
// frames get a stream, and the grid is capped.
const MAX_STREAMS = 6;

function healthClass(cam) {
  return cam.health === "ok"
    ? "ok"
    : cam.health === "degraded" || cam.health === "connecting"
      ? "warn"
      : cam.health === "down"
        ? "down"
        : "idle";
}

function Feed({ cam, live, scene }) {
  const [err, setErr] = useState(false);
  // a dropped stream must not blank the tile forever — retry shortly after a
  // failure so the feed returns on its own once the source recovers
  useEffect(() => {
    if (!err) return;
    const t = setTimeout(() => setErr(false), 10000);
    return () => clearTimeout(t);
  }, [err]);
  const showStream = live && !err;
  return (
    <div className="feed">
      {showStream ? (
        <>
          <img src={`/api/bridge/cameras/${cam.id}/mjpeg`} alt={cam.name} onError={() => setErr(true)} />
          <div className="rec"><i /> LIVE</div>
        </>
      ) : (
        <div className="offline">
          <span>
            {!cam.monitoring
              ? "NOT POOLED"
              : cam.health === "down"
                ? "NO SIGNAL"
                : cam.health === "connecting"
                  ? "CONNECTING"
                  : "AWAITING SLOT"}
          </span>
          <span className="mono small dim">{cam.codec || "?"}/{cam.container || "?"}</span>
        </div>
      )}
      <div className="feed-bar">
        <span className={`led ${healthClass(cam)}`} />
        <span className="feed-name">{cam.name}</span>
        <span className="dim small" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
          {cam.location}
        </span>
        {scene && (
          <span className="mono small" style={{ color: "var(--teal)", whiteSpace: "nowrap" }}
            title="Live scene analytics (person/vehicle detection)">
            ⬤ {scene.persons}p · {scene.vehicles}v
          </span>
        )}
      </div>
    </div>
  );
}

export function Wall() {
  const [cams, setCams] = useState([]);
  const [flowing, setFlowing] = useState({});   // camera_id -> frame_age_s
  const [scenes, setScenes] = useState({});     // camera_id -> {persons, vehicles}
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
        setFlowing(
          Object.fromEntries(
            bridge.workers
              .filter((w) => w.has_frame && w.frame_age_s != null && w.frame_age_s < 30)
              .map((w) => [w.camera_id, w.frame_age_s])
          )
        );
      } catch {
        /* transient */
      }
    };
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  const depts = [...new Set(cams.map((c) => c.department))].sort();
  const inDept = (c) => !dept || c.department === dept;

  // live feeds first (capped), then a few context tiles so the wall isn't bare
  const liveCams = cams.filter((c) => inDept(c) && flowing[c.id] != null).slice(0, MAX_STREAMS);
  const liveIds = new Set(liveCams.map((c) => c.id));
  const others = cams.filter((c) => inDept(c) && !liveIds.has(c.id)).slice(0, 12);

  return (
    <>
      <div className="form-row" style={{ marginBottom: 14 }}>
        <select value={dept} onChange={(e) => setDept(e.target.value)}>
          <option value="">All departments</option>
          {depts.map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
        <span className="badge ok">{liveCams.length} streaming</span>
        <span className="badge neutral">stream cap {MAX_STREAMS}</span>
        <span style={{ flex: 1 }} />
        <span className="dim small">
          {cams.filter(inDept).length} cameras in view · showing {liveCams.length + others.length}
        </span>
      </div>
      <div className="wall">
        {liveCams.map((cam) => (
          <Feed cam={cam} live scene={scenes[cam.id]} key={cam.id} />
        ))}
        {others.map((cam) => (
          <Feed cam={cam} live={false} scene={scenes[cam.id]} key={cam.id} />
        ))}
        {cams.length === 0 && (
          <div className="empty-state" style={{ gridColumn: "1/-1" }}>
            <div className="big">No cameras</div>
            Onboard cameras from the Registry page.
          </div>
        )}
      </div>
    </>
  );
}
