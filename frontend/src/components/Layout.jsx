import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth.jsx";
import { useAlerts } from "../ws.jsx";
import { PlateChip } from "./PlateChip.jsx";

const NAV = [
  { to: "/", label: "Overview", glyph: "◈" },
  { to: "/wall", label: "Video Wall", glyph: "▦" },
  { to: "/trace", label: "Trace", glyph: "◎" },
  { to: "/detections", label: "Detections", glyph: "⌗" },
  { to: "/alerts", label: "Alerts", glyph: "▲" },
  { to: "/registry", label: "Registry", glyph: "☰" },
  { to: "/atlas", label: "Atlas", glyph: "▤" },
  { to: "/watchlist", label: "Watchlist", glyph: "✚" },
];

const TITLES = {
  "/": "State Overview",
  "/wall": "Live Video Wall",
  "/trace": "Vehicle Trace",
  "/detections": "ANPR Detections",
  "/alerts": "Alert Centre",
  "/registry": "Camera Registry",
  "/atlas": "Atlas · Coverage",
  "/watchlist": "Watchlist",
};

function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <span className="clock">
      {now.toLocaleTimeString("en-IN", { hour12: false })} IST
    </span>
  );
}

function Toasts() {
  const { toasts } = useAlerts();
  return (
    <div className="toasts">
      {toasts.map((t) => (
        <div className="toast" key={t.toastId}>
          <div className="t-head">
            <span className="led down" /> Watchlist Hit — {t.reason}
          </div>
          <div className="t-body">
            <PlateChip plate={t.plate} />
            <span>
              {t.camera_name} · {t.location}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function Layout({ children }) {
  const { pathname } = useLocation();
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [health, setHealth] = useState(null);
  useEffect(() => {
    const load = () => api.health().then(setHealth).catch(() => setHealth(null));
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="shell">
      <aside className="rail">
        <div className="rail-brand">
          <div className="logo">SUTRA</div>
          <div className="sub">Statewide Unified Tracking,<br />Registry &amp; Analytics</div>
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}>
              <span className="glyph">{n.glyph}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          Gujarat Police<br />
          CCTV Integration Challenge 2026<br />
          <span className="mono dim">v0.1 · sandbox</span>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <span className="page-title">{TITLES[pathname] ?? "SUTRA"}</span>
          <span className="spacer" />
          <span className="sysdot">
            <span className={`led ${health ? "ok" : "down"}`} />
            {health ? `Core online · ${health.ingest_workers} ingest` : "Core offline"}
          </span>
          <span className="sysdot">
            <span className="badge neutral">{user?.role}</span>
            <span className="mono small">{user?.username}</span>
          </span>
          <Clock />
          <button
            className="btn sm"
            onClick={() => {
              logout();
              nav("/login");
            }}
          >
            Sign Out
          </button>
        </header>
        <main className="content">{children}</main>
      </div>
      <Toasts />
    </div>
  );
}
