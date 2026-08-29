import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Backend origin the dev server proxies to. Defaults to the documented port;
// override with SUTRA_API_URL when 8000 is already taken on the machine.
const API = process.env.SUTRA_API_URL || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // permit tunnel hostnames (Cloudflare / ngrok) so the dev server can be
    // demoed over a public URL; production is served by nginx, not this server
    allowedHosts: [".trycloudflare.com", ".ngrok-free.app", ".ngrok.app"],
    proxy: {
      "/api": {
        target: API,
        ws: true,
      },
      "/data": API,
    },
  },
});
