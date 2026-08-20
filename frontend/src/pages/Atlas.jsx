import { useEffect, useState } from "react";
import { api } from "../api";

export function Atlas() {
  const [gap, setGap] = useState(null);

  useEffect(() => {
    api.gapAnalysis().then(setGap).catch(() => {});
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
    </>
  );
}
