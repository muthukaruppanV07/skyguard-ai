"use client";

import { useEffect, useRef } from "react";
import type { GeoPoint } from "@/lib/types";

interface MapViewProps {
  points: GeoPoint[];
  center?: [number, number];
  zoom?: number;
  label?: (p: GeoPoint) => string;
}

declare global {
  interface Window {
    L?: any;
    leafletReady?: Promise<boolean>;
  }
}

function loadLeaflet(): Promise<boolean> {
  if (window.leafletReady) return window.leafletReady;
  window.leafletReady = new Promise<boolean>((resolve) => {
    if (window.L) return resolve(true);
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(css);

    const script = document.createElement("script");
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.head.appendChild(script);
  });
  return window.leafletReady;
}

export default function MapView({ points, center, zoom = 11, label }: MapViewProps) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markerLayer = useRef<any>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const ok = await loadLeaflet();
      if (!ok || cancelled || !ref.current) return;
      const L = window.L;

      const coords: [number, number][] = points
        .filter((p) => typeof p.lat === "number" && typeof p.lng === "number")
        .map((p) => [p.lat, p.lng]);

      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }

      const c = center ?? (coords.length ? coords[0] : [20.5937, 78.9629]);
      const map = L.map(ref.current).setView(c, zoom);
      mapRef.current = map;
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap contributors",
      }).addTo(map);

      markerLayer.current = L.layerGroup().addTo(map);
      coords.forEach(([lat, lng]) => {
        const p = points.find((pt) => pt.lat === lat && pt.lng === lng);
        const marker = L.marker([lat, lng]).addTo(markerLayer.current);
        if (p) {
          marker.bindPopup(
            (label ? label(p) : "") + `<br/><small>${lat.toFixed(4)}, ${lng.toFixed(4)}</small>`,
          );
        }
      });

      if (coords.length > 1) {
        map.fitBounds(L.latLngBounds(coords), { padding: [40, 40] });
      }
    })();

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [points, center, zoom, label]);

  return <div ref={ref} className="h-[420px] w-full rounded-xl" />;
}
