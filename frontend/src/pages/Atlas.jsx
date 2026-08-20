import { useEffect, useState } from "react";
import { api, fmtTime } from "../api";

export function Atlas() {
  const [gap, setGap] = useState(null);
  const [audit, setAudit] = useState([]);

  useEffect(() => {
    api.gapAnalysis().then(setGap).catch(() => {});
    api.auditTrail(50).then(setAudit).catch(() => {});
  }, []);

  if (!gap) return <div className="empty-state"><div className="big">Loading…</div></div>;

  const districts = Object.entries(gap.districts);

  return (
    <>
      <div className="kpis" style={{ marginBottom: 14 }}>
        <div className="kpi">
          <div className="label">Registered</div>
          <div className="value">{gap.total_cameras}</div>
        </div>
        <div className="kpi teal">
          <div className="label">Monitored</div>
          <div className="value">{gap.monitored}</div>
        </div>
        <div className="kpi green">
          <div className="label">Healthy</div>
          <div className="value">{gap.healthy}</div>
        </div>
        <div className="kpi red">
          <div className="label">Coverage Gap</div>
          <div className="value">{gap.total_cameras - gap.monitored}</div>
          <div className="hint">registered but not monitored</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">District Coverage &amp; Gap Analysis</div>
        <table className="grid">
          <thead>
            <tr>
              <th>District</th>
              <th>Cameras</th>
              <th>Unhealthy</th>
              <th>Ageing (5y+)</th>
              <th>Departments</th>
              <th>Assessment</th>
            </tr>
          </thead>
          <tbody>
            {districts.map(([name, d]) => (
              <tr key={name}>
                <td style={{ fontWeight: 600 }}>{name}</td>
                <td className="mono">{d.cameras}</td>
                <td className="mono" style={{ color: d.unhealthy ? "var(--red)" : "var(--text-2)" }}>
                  {d.unhealthy}
                </td>
                <td className="mono" style={{ color: d.ageing ? "var(--amber)" : "var(--text-2)" }}>
                  {d.ageing ?? 0}
                </td>
                <td className="small">{d.departments.join(" · ")}</td>
                <td>
                  {d.cameras < 3 ? (
                    <span className="badge medium">thin coverage</span>
                  ) : d.unhealthy > d.cameras / 2 ? (
                    <span className="badge high">degraded zone</span>
                  ) : (
                    <span className="badge ok">adequate</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <div className="panel-head">
          Metadata Audit Trail
          <span className="spacer" />
          <span className="dim small">last {audit.length} actions</span>
        </div>
        <table className="grid">
          <thead>
            <tr><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th></tr>
          </thead>
          <tbody>
            {audit.map((a, i) => (
              <tr key={i}>
                <td className="mono small dim">{fmtTime(a.ts)}</td>
                <td className="mono small">{a.actor}</td>
                <td><span className="badge neutral">{a.action}</span></td>
                <td className="small dim">{a.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
