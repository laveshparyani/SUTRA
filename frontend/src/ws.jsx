import { createContext, useContext, useEffect, useRef, useState } from "react";

const AlertCtx = createContext({ live: [], toasts: [] });

export function AlertProvider({ children }) {
  const [live, setLive] = useState([]);   // alerts received this session, newest first
  const [toasts, setToasts] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    let closed = false;
    function connect() {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/api/watch/ws`);
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        try {
          const alert = JSON.parse(ev.data);
          if (alert.type !== "watchlist_alert") return;
          setLive((prev) => [alert, ...prev].slice(0, 200));
          const toastId = `${alert.alert_id}-${Date.now()}`;
          setToasts((prev) => [...prev, { ...alert, toastId }]);
          setTimeout(
            () => setToasts((prev) => prev.filter((t) => t.toastId !== toastId)),
            9000
          );
        } catch {
          /* non-JSON keepalive */
        }
      };
      ws.onclose = (ev) => {
        if (closed) return;
        // 4401 is the server refusing the media cookie. Reconnecting cannot
        // change that — only a fresh sign-in can — so a retry loop here just
        // emits a console error every few seconds and spends a connection from
        // a pool the video wall already contends for. Protected routes send the
        // user to /login on their own.
        if (ev.code === 4401) return;
        attempt += 1;
        const delay = Math.min(3000 * 2 ** (attempt - 1), 30000);
        setTimeout(connect, delay);
      };
      ws.onopen = () => { attempt = 0; };
    }
    let attempt = 0;
    connect();
    return () => {
      closed = true;
      wsRef.current?.close();
    };
  }, []);

  return <AlertCtx.Provider value={{ live, toasts }}>{children}</AlertCtx.Provider>;
}

export const useAlerts = () => useContext(AlertCtx);
