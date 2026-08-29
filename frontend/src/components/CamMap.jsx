import L from "leaflet";
import { useEffect, useRef } from "react";

// CARTO's basemaps started requiring an API key and now stamp "API KEY
// REQUIRED" across every tile. Esri's Dark Gray Canvas is keyless, natively
// dark (so no CSS inversion that would mangle label text), and serves the
// whole state at the zooms the registry map uses.
const ESRI = "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas";
const TILES = `${ESRI}/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`;
// Esri ships the basemap without place names; labels are a separate
// transparent overlay. Without it the registry map has no towns or districts,
// which is most of what makes a coverage map readable.
const LABELS = `${ESRI}/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`;
const ATTR = "&copy; OpenStreetMap &copy; Esri";
const MAX_TILE_ZOOM = 16;   // Dark Gray Canvas has no tiles past 16

const healthClass = (cam) =>
  cam.health === "ok" ? "ok" : cam.health === "degraded" ? "warn" : cam.health === "down" ? "down" : "idle";

// Leaflet popups render raw HTML; camera names/locations arrive from CSV
// imports and external APIs, so they must be escaped before interpolation
const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function camIcon(cam) {
  return L.divIcon({
    className: "",
    html: `<div class="cam-marker ${healthClass(cam)}"></div>`,
    iconSize: [13, 13],
    iconAnchor: [7, 7],
  });
}

function seqIcon(n) {
  return L.divIcon({
    className: "",
    html: `<div class="seq-marker">${n}</div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

/** Leaflet map showing cameras and (optionally) a traced route.
 *  `coverage` draws an approximate field-of-view radius around each camera so
 *  covered corridors and blind zones read directly off the map — the layer the
 *  gap-analysis table summarises in words. */
export function CamMap({ cameras = [], route = null, height = "100%", onCamClick, coverage = false }) {
  const holder = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);

  useEffect(() => {
    const map = L.map(holder.current, {
      center: [22.6, 71.6],
      zoom: 7,
      zoomControl: false,
      attributionControl: false,
    });
    L.control.attribution({ position: "bottomright", prefix: false }).addAttribution(ATTR).addTo(map);
    L.control.zoom({ position: "bottomright" }).addTo(map);
    // maxNativeZoom stops Leaflet requesting tiles that do not exist past 16;
    // it upscales the zoom-16 tile instead of rendering blank grey squares.
    // Both in the tile pane: the labels layer is added second so it draws over
    // the basemap, while markers and coverage circles keep their own higher
    // panes and stay above both.
    const tileOpts = { maxZoom: 19, maxNativeZoom: MAX_TILE_ZOOM };
    L.tileLayer(TILES, tileOpts).addTo(map);
    L.tileLayer(LABELS, tileOpts).addTo(map);
    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    return () => map.remove();
  }, []);

  useEffect(() => {
    const layer = layerRef.current;
    const map = mapRef.current;
    if (!layer || !map) return;
    layer.clearLayers();

    for (const cam of cameras) {
      if (cam.lat == null || cam.lon == null) continue;
      if (coverage) {
        // ~150 m effective ANPR/observation radius for a fixed roadside camera;
        // colour tracks health so a dead camera's zone reads as a gap, not cover
        L.circle([cam.lat, cam.lon], {
          radius: 150,
          weight: 1,
          color: cam.health === "ok" ? "#3fae6a" : cam.health === "down" ? "#c94f4f" : "#8a8f98",
          fillOpacity: cam.health === "ok" ? 0.18 : 0.08,
        }).addTo(layer);
      }
      const m = L.marker([cam.lat, cam.lon], { icon: camIcon(cam) }).addTo(layer);
      m.bindPopup(
        `<b>${esc(cam.name)}</b><br/>${esc(cam.location)}<br/>` +
          `<span style="opacity:.7">${esc(cam.department)} · ${esc(cam.district) || "—"} · ${esc(cam.health)}</span>`
      );
      if (onCamClick) m.on("click", () => onCamClick(cam));
    }

    if (route && route.sightings?.length) {
      const pts = route.sightings.filter((s) => s.lat != null).map((s) => [s.lat, s.lon]);
      route.sightings.forEach((s, i) => {
        if (s.lat == null) return;
        L.marker([s.lat, s.lon], { icon: seqIcon(i + 1), zIndexOffset: 500 })
          .addTo(layer)
          .bindPopup(`<b>#${i + 1} ${esc(s.location)}</b><br/>${esc(s.first_seen)} → ${esc(s.last_seen)}`);
      });
      if (pts.length > 1) {
        L.polyline(pts, { color: "#f0a428", weight: 3, opacity: 0.9, dashArray: "8 6" }).addTo(layer);
        map.fitBounds(L.latLngBounds(pts).pad(0.3));
      } else if (pts.length === 1) {
        map.setView(pts[0], 13);
      }
    }
  }, [cameras, route, onCamClick, coverage]);

  return <div className="map-wrap" style={{ height }} ref={holder} />;
}
