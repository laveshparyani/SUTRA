import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtTime } from "../api";
import { AreaChart, BandChart, BarList, ChartCard, StatTile, StatusDonut } from "../components/charts.jsx";
import { CamMap } from "../components/CamMap.jsx";
import { PlateChip } from "../components/PlateChip.jsx";
import { useAlerts } from "../ws.jsx";

const WINDOWS = [
  { h: 6, label: "6h" },
  { h: 24, label: "24h" },
  { h: 72, label: "3d" },
  { h: 168, label: "7d" },
];

export function Dashboard() {
  const [cams, setCams] = useState([]);
  const [an, setAn] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [hours, setHours] = useState(24);
  const { live } = useAlerts();

  useEffect(() => {
    const load = () => {
      api.cameras().then(setCams).catch(() => {});
      api.analytics(hours).then(setAn).catch(() => {});
      api.alerts({ limit: 8 }).then(setAlerts).catch(() => {});
    };
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [hours, live.length]);

  const t = an?.totals;
  const spark = an?.activity?.map((a) => a.count) ?? [];
  const newAlerts = alerts.filter((a) => a.status === "new").length;

  return (
    <>
      <div className="explainer">
        <span className="ico">◈</span>
        <div>
          <b>State overview.</b> Everything here is measured from cameras SUTRA has
          actually processed — no sample data. Figures cover the last{" "}
          {WINDOWS.find((w) => w.h === hours)?.label ?? `${hours}h`}; the map shows
          every registered camera coloured by live health.
        </div>
      </div>

      <div className="form-row" style={{ marginBottom: 14 }}>
        <span className="dim small" style={{ letterSpacing: 1.4, textTransform: "uppercase" }}>
          Time window
        </span>
        <div className="seg-toggle">
          {WINDOWS.map((w) => (
            <button key={w.h} className={hours === w.h ? "on" : ""} onClick={() => setHours(w.h)}>
              {w.label}
            </button>
          ))}
        </div>
        <span style={{ flex: 1 }} />
        {an && <span className="dim small mono">updated {fmtTime(an.generated_at)}</span>}
      </div>

      {/* headline numbers */}
      <div className="stat-row" style={{ marginBottom: 14 }}>
        <StatTile label="Plates read" value={t?.detections} spark={spark}
          hint={t?.unique_vehicles != null ? `${t.unique_vehicles} distinct vehicles` : ""} />
        <StatTile label="Watchlist alerts" value={t?.alerts} tone={t?.alerts ? "critical" : "default"}
          hint={newAlerts ? `${newAlerts} unacknowledged` : "none pending"} />
        <StatTile label="Cameras onboarded" value={t?.cameras_registered} tone="amber"
          hint={`${new Set(cams.map((c) => c.department)).size} departments`} />
        <StatTile label="Feeds healthy" value={t ? `${t.cameras_healthy}/${t.cameras_registered}` : null}
          tone={t?.cameras_healthy ? "good" : "warn"} hint="delivering frames now" />
        <StatTile label="Mean read quality"
          value={t?.avg_confidence != null ? `${Math.round(t.avg_confidence * 100)}%` : "—"}
          hint="OCR confidence" />
      </div>

      {/* charts */}
      <div className="chart-grid" style={{ marginBottom: 14 }}>
        <ChartCard wide title="Detection activity" subtitle="Plates read per hour"
          hint="Gaps are periods with no camera delivering frames — the source portal is intermittent.">
          <AreaChart data={an?.activity ?? []} />
        </ChartCard>

        <ChartCard title="Camera health" subtitle="Live state of every registered camera">
          <StatusDonut data={an?.camera_health ?? []} centerLabel="cameras" />
        </ChartCard>

        <ChartCard title="Most-seen vehicles" subtitle="By number of reads in window"
          actions={<Link to="/detections" className="btn sm">Browse</Link>}>
          <BarList data={an?.top_vehicles ?? []} labelKey="plate" valueKey="detections" colorBy="series" />
        </ChartCard>

        <ChartCard title="Busiest cameras" subtitle="Where the reads are coming from">
          <BarList data={an?.by_camera ?? []} labelKey="camera" valueKey="detections" />
        </ChartCard>

        <ChartCard title="Read quality distribution" subtitle="OCR confidence of stored reads"
          hint="Close-range cameras read high; wide-angle PTZ views read lower — voting and fuzzy matching absorb the difference.">
          <BandChart data={an?.confidence_bands ?? []} />
        </ChartCard>

        <ChartCard title="Activity by department" subtitle="Which owners the traffic belongs to">
          <BarList data={an?.by_department ?? []} labelKey="department" valueKey="detections" colorBy="series" />
        </ChartCard>
      </div>

      {/* map + live alerts */}
      <div className="dash">
        <div className="left">
          <ChartCard title="Camera network" subtitle="Registered cameras across Gujarat, coloured by health">
            <div className="state-key" style={{ marginBottom: 10 }}>
              <span><i className="led ok" /> delivering frames</span>
              <span><i className="led warn" /> connecting</span>
              <span><i className="led down" /> no signal</span>
              <span><i className="led idle" /> not monitored</span>
            </div>
            <CamMap cameras={cams} height="440px" />
          </ChartCard>
        </div>

        <div className="panel" style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
          <div className="panel-head">
            <span className="led down" /> Live alerts
            <span className="spacer" />
            <Link to="/alerts" className="dim small" style={{ color: "inherit" }}>all →</Link>
          </div>
          <div className="alert-feed" style={{ overflow: "auto" }}>
            {live.length === 0 && (
              <div className="empty-state">
                <div className="big">Watching</div>
                Every plate read is cross-checked against the watchlist. Matches
                appear here instantly.
              </div>
            )}
            {live.map((a) => (
              <div className={`alert-row ${a.priority === "high" ? "high" : "medium"}`}
                key={`${a.alert_id}-${a.ts}`}>
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
    </>
  );
}
