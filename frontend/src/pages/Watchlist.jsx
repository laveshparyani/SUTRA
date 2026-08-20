import { useEffect, useState } from "react";
import { api, fmtTime } from "../api";
import { useAuth } from "../auth.jsx";
import { PlateChip } from "../components/PlateChip.jsx";

export function Watchlist() {
  const { canOperate } = useAuth();
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ plate: "", reason: "stolen", fir_ref: "", priority: "high" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = () => api.watchlist().then(setRows).catch(() => {});
  useEffect(() => { load(); }, []);

  async function add(e) {
    e.preventDefault();
    if (!form.plate.trim()) return;
    setBusy(true);
    setErr("");
    try {
      await api.addWatch(form);
      setForm({ ...form, plate: "", fir_ref: "" });
      await load();
    } catch (ex) {
      setErr(String(ex.message || ex));
    } finally {
      setBusy(false);
    }
  }

  async function deactivate(id) {
    await api.removeWatch(id);
    await load();
  }

  return (
    <>
      {canOperate && (
      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="panel-head">Add Entry</div>
        <form className="form-row" style={{ padding: 14 }} onSubmit={add}>
          <input
            placeholder="GJ01AB1234"
            style={{ textTransform: "uppercase", width: 160 }}
            value={form.plate}
            onChange={(e) => setForm({ ...form, plate: e.target.value.toUpperCase() })}
          />
          <select value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}>
            <option>stolen</option>
            <option>blacklisted</option>
            <option>suspect</option>
            <option>wanted</option>
          </select>
          <input
            placeholder="FIR reference"
            style={{ width: 170 }}
            value={form.fir_ref}
            onChange={(e) => setForm({ ...form, fir_ref: e.target.value })}
          />
          <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
            <option>high</option>
            <option>medium</option>
            <option>low</option>
          </select>
          <button className="btn primary" disabled={busy}>Add to Watchlist</button>
          {err && <span className="small" style={{ color: "var(--red)" }}>{err}</span>}
        </form>
      </div>
      )}

      <div className="panel">
        <div className="panel-head">
          Active Watchlist <span className="spacer" />
          <span className="dim small">{rows.filter((r) => r.active).length} active</span>
        </div>
        <table className="grid">
          <thead>
            <tr>
              <th>Plate</th><th>Reason</th><th>FIR</th><th>Priority</th><th>Added</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((w) => (
              <tr key={w.id} style={{ opacity: w.active ? 1 : 0.45 }}>
                <td><PlateChip plate={w.plate} /></td>
                <td><span className={`badge ${w.priority}`}>{w.reason}</span></td>
                <td className="mono small dim">{w.fir_ref || "—"}</td>
                <td>{w.priority}</td>
                <td className="mono small dim">{fmtTime(w.created_at)}</td>
                <td><span className={`badge ${w.active ? "ok" : "neutral"}`}>{w.active ? "active" : "inactive"}</span></td>
                <td>
                  {w.active && canOperate && (
                    <button className="btn sm danger" onClick={() => deactivate(w.id)}>Deactivate</button>
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
