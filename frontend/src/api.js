import { getToken } from "./auth.jsx";

const json = (r) => {
  if (r.status === 401) {
    localStorage.removeItem("sutra_user");
    window.location.href = "/login";
    throw new Error("session expired");
  }
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
};

// Attach the bearer token to API calls. Guarded so Vite hot-reloads re-wrap the
// pristine fetch instead of stacking a new wrapper around the previous one.
if (!window.__sutraFetchPatched) {
  const nativeFetch = window.fetch.bind(window);
  window.__sutraNativeFetch = nativeFetch;
  window.__sutraFetchPatched = true;
  window.fetch = (url, opts = {}) => {
    const token = getToken();
    if (typeof url === "string" && url.startsWith("/api/") && token) {
      opts = { ...opts, headers: { ...(opts.headers || {}), Authorization: `Bearer ${token}` } };
    }
    return nativeFetch(url, opts);
  };
}

export const api = {
  cameras: () => fetch("/api/atlas/cameras").then(json),
  camera: (id) => fetch(`/api/atlas/cameras/${id}`).then(json),
  discover: () => fetch("/api/atlas/discover", { method: "POST" }).then(json),
  gapAnalysis: () => fetch("/api/atlas/gap-analysis").then(json),
  auditTrail: (limit = 100) => fetch(`/api/atlas/audit?limit=${limit}`).then(json),
  updateCamera: (id, body) =>
    fetch(`/api/atlas/cameras/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json),

  bridgeStatus: () => fetch("/api/bridge/status").then(json),
  schedulerStatus: () => fetch("/api/bridge/scheduler").then(json),
  pinCam: (id) => fetch(`/api/bridge/cameras/${id}/pin`, { method: "POST" }).then(json),
  unpinCam: (id) => fetch(`/api/bridge/cameras/${id}/unpin`, { method: "POST" }).then(json),
  startCam: (id) => fetch(`/api/bridge/cameras/${id}/start`, { method: "POST" }).then(json),
  stopCam: (id) => fetch(`/api/bridge/cameras/${id}/stop`, { method: "POST" }).then(json),
  startAll: () => fetch("/api/bridge/start-all", { method: "POST" }).then(json),

  insightStats: () => fetch("/api/insight/stats").then(json),
  detections: (params = {}) =>
    fetch(`/api/insight/detections?${new URLSearchParams(params)}`).then(json),
  vehicles: (params = {}) =>
    fetch(`/api/insight/vehicles?${new URLSearchParams(params)}`).then(json),
  sightings: (params = {}) =>
    fetch(`/api/insight/sightings?${new URLSearchParams(params)}`).then(json),
  alertEpisodes: (params = {}) =>
    fetch(`/api/watch/alerts/episodes?${new URLSearchParams(params)}`).then(json),
  ackEpisode: (alertIds) =>
    fetch("/api/watch/alerts/episodes/ack", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(alertIds),
    }).then(json),
  analytics: (hours = 24) => fetch(`/api/insight/analytics?hours=${hours}`).then(json),
  systemStatus: () => fetch("/api/system").then(json),
  route: (plate) => fetch(`/api/insight/route/${encodeURIComponent(plate)}`).then(json),

  watchlist: () => fetch("/api/watch/vehicles").then(json),
  addWatch: (body) =>
    fetch("/api/watch/vehicles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json),
  removeWatch: (id) => fetch(`/api/watch/vehicles/${id}`, { method: "DELETE" }).then(json),
  alerts: (params = {}) => fetch(`/api/watch/alerts?${new URLSearchParams(params)}`).then(json),
  ackAlert: (id) => fetch(`/api/watch/alerts/${id}/ack`, { method: "POST" }).then(json),

  health: () => fetch("/api/health").then(json),
};

/** Download an authenticated endpoint as a file (auth header ⇒ can't use <a href>). */
export async function downloadFile(url, filename) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

/** Day + time without seconds, for spans where the exact second is noise.
 *  A formatter rather than a substring of fmtTime(): slicing that string cuts
 *  a two-digit minute in half ("13:5") whenever the locale shifts by a char. */
export function fmtDayTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts.endsWith("Z") || ts.includes("+") ? ts : ts + "Z");
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function fmtTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts.endsWith("Z") || ts.includes("+") ? ts : ts + "Z");
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}
