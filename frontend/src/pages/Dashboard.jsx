import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtTime } from "../api";
import { CamMap } from "../components/CamMap.jsx";
import { PlateChip } from "../components/PlateChip.jsx";
import { useAlerts } from "../ws.jsx";

export function Dashboard() {
  const [cams, setCams] = useState([]);
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const { live } = useAlerts();

  useEffect(() => {
    const load = () => {
      api.cameras().then(setCams).catch(() => {});
      api.insightStats().then(setStats).catch(() => {});
      api.alerts({ limit: 12 }).then(setAlerts).catch(() => {});
    };
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [live.length]);

  const monitored = cams.filter((c) => c.monitoring).length;
  const healthy = cams.filter((c) => c.health === "ok").length;

  return (
    <div className="dash">
      <div className="left">
        <div className="kpis">
          <div className="kpi">
            <div className="label">Cameras Onboarded</div>
            <div className="value">{cams.length}</div>
            <div className="hint">{new Set(cams.map((c) => c.department)).size} departments</div>
          </div>
          <div className="kpi green">
            <div className="value">{healthy}<span className="dim" style={{ fontSize: 18 }}>/{monitored}</span></div>
            <div className="label">Feeds Healthy</div>
            <div className="hint">of monitored</div>
          </div>
          <div className="kpi teal">
            <div className="label">Plates Read</div>
            <div className="value">{stats?.plates_read ?? "—"}</div>
            <div className="hint">{stats ? `${stats.last_inference_ms} ms inference` : ""}</div>
          </div>
          <div className="kpi red">
            <div className="label">Alerts Fired</div>
            <div className="value">{stats?.alerts_fired ?? "—"}</div>
            <div className="hint">watchlist correlations</div>
          </div>
        </div>
        <CamMap cameras={cams} height="calc(100vh - 248px)" />
      </div>

      <div className="panel" style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div className="panel-head">
          <span className="led down" /> Live Alerts
          <span className="spacer" />
          <Link to="/alerts" className="dim small" style={{ color: "inherit" }}>
            all →
          </Link>
        </div>
        <div className="alert-feed" style={{ overflow: "auto" }}>
          {live.length === 0 && alerts.length === 0 && (
            <div className="empty-state">
              <div className="big">No Alerts</div>
              Continuous watchlist correlation is running.
            </div>
          )}
          {live.map((a) => (
            <div className={`alert-row ${a.priority === "high" ? "high" : "medium"}`} key={`l${a.alert_id}-${a.ts}`}>
              {a.snapshot && <img className="thumb" src={a.snapshot} alt="" />}
              <div className="meta">
                <div className="row1">
                  <PlateChip plate={a.plate} />
                  <span className={`badge ${a.priority === "high" ? "high" : "medium"}`}>{a.reason}</span>
                  {a.match_type === "probable" && <span className="badge neutral">probable</span>}
                </div>
                <div className="where">{a.camera_name} · {a.location}</div>
                <div className="when">{fmtTime(a.ts)}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
