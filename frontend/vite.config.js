import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // permit tunnel hostnames (Cloudflare / ngrok) so the dev server can be
    // demoed over a public URL; production is served by nginx, not this server
    allowedHosts: [".trycloudflare.com", ".ngrok-free.app", ".ngrok.app"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        ws: true,
      },
      "/data": "http://127.0.0.1:8000",
    },
  },
});
