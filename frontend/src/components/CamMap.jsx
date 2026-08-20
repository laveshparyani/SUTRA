import L from "leaflet";
import { useEffect, useRef } from "react";

const TILES = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const ATTR = '&copy; OpenStreetMap &copy; CARTO';

const healthClass = (cam) =>
  cam.health === "ok" ? "ok" : cam.health === "degraded" ? "warn" : cam.health === "down" ? "down" : "idle";

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

/** Leaflet map showing cameras and (optionally) a traced route. */
export function CamMap({ cameras = [], route = null, height = "100%", onCamClick }) {
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
    L.tileLayer(TILES, { maxZoom: 19 }).addTo(map);
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
      const m = L.marker([cam.lat, cam.lon], { icon: camIcon(cam) }).addTo(layer);
      m.bindPopup(
        `<b>${cam.name}</b><br/>${cam.location}<br/>` +
          `<span style="opacity:.7">${cam.department} · ${cam.district || "—"} · ${cam.health}</span>`
      );
      if (onCamClick) m.on("click", () => onCamClick(cam));
    }

    if (route && route.sightings?.length) {
      const pts = route.sightings.filter((s) => s.lat != null).map((s) => [s.lat, s.lon]);
      route.sightings.forEach((s, i) => {
        if (s.lat == null) return;
        L.marker([s.lat, s.lon], { icon: seqIcon(i + 1), zIndexOffset: 500 })
          .addTo(layer)
          .bindPopup(`<b>#${i + 1} ${s.location}</b><br/>${s.first_seen} → ${s.last_seen}`);
      });
      if (pts.length > 1) {
        L.polyline(pts, { color: "#f0a428", weight: 3, opacity: 0.9, dashArray: "8 6" }).addTo(layer);
        map.fitBounds(L.latLngBounds(pts).pad(0.3));
      } else if (pts.length === 1) {
        map.setView(pts[0], 13);
      }
    }
  }, [cameras, route, onCamClick]);

  return <div className="map-wrap" style={{ height }} ref={holder} />;
}
