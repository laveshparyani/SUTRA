import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await login(username, password);
      nav("/");
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background:
          "radial-gradient(900px 480px at 50% -10%, rgba(240,164,40,0.07), transparent), var(--bg-0)",
      }}
    >
      <form
        onSubmit={submit}
        className="panel"
        style={{ width: 380, padding: "34px 34px 30px", display: "flex", flexDirection: "column", gap: 14 }}
      >
        <div style={{ textAlign: "center", marginBottom: 8 }}>
          <div
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: 42,
              letterSpacing: 12,
              color: "var(--amber)",
            }}
          >
            SUTRA
          </div>
          <div style={{ fontSize: 10, letterSpacing: 2, textTransform: "uppercase", color: "var(--text-2)", marginTop: 4 }}>
            Statewide Unified Tracking, Registry &amp; Analytics
          </div>
          <div style={{ fontSize: 10.5, color: "var(--text-2)", marginTop: 10 }}>
            Gujarat Police · Restricted Access
          </div>
        </div>
        <input placeholder="username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <input placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {err && <div className="small" style={{ color: "var(--red)" }}>{err}</div>}
        <button className="btn primary" disabled={busy} style={{ padding: "10px 0" }}>
          {busy ? "Authenticating…" : "Sign In"}
        </button>
        <div className="small dim" style={{ textAlign: "center", lineHeight: 1.7 }}>
          Sandbox accounts: admin · operator_police · viewer
        </div>
      </form>
    </div>
  );
}
