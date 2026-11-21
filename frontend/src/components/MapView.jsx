import { MapContainer, TileLayer, Marker, Polyline, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { useEffect } from 'react'
const CENTER = [31.235, 75.745]
function Fit({ points }) {
  const map = useMap()
  useEffect(() => {
    const pts = (points || []).filter(p => p && p[0] != null)
    if (pts.length > 1) map.fitBounds(pts, { padding: [30, 30] })
    else if (pts.length === 1) map.setView(pts[0], 14)
  }, [JSON.stringify(points)])
  return null
}
function busIcon(v) {
  const cls = v.is_stale ? 'bus-marker stale' : (v.crowd_level === 'high' ? 'bus-marker high' : 'bus-marker')
  return L.divIcon({ className: '', html: `<div class="${cls}">🚌 ${v.registration_number || ''}</div>`, iconSize: null })
}
const stopIcon = L.divIcon({ className: '', html: '<div class="stop-dot"></div>', iconSize: [14, 14], iconAnchor: [7, 7] })
export default function MapView({ vehicles = [], routes = [], stops = [], height = '420px', fit = true, onStopClick }) {
  const points = [...vehicles.filter(v => v.latitude != null).map(v => [v.latitude, v.longitude]), ...stops.filter(s => s.latitude != null).map(s => [s.latitude, s.longitude])]
  return (
    <div className="rounded-2xl border-[2.5px] border-ink overflow-hidden shadow-hard bg-white" style={{ height }}>
      <MapContainer center={CENTER} zoom={12} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
        <TileLayer attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {fit && <Fit points={points} />}
        {routes.map((r, i) => Array.isArray(r.polyline) && r.polyline.length > 1 ? (
          <Polyline key={r.id || i} positions={r.polyline} pathOptions={{ color: i % 2 ? '#2F6BFF' : '#141414', weight: 5, opacity: 0.85 }} />
        ) : null)}
        {stops.map(s => s.latitude != null ? (
          <Marker key={s.id} position={[s.latitude, s.longitude]} icon={stopIcon} eventHandlers={onStopClick ? { click: () => onStopClick(s) } : undefined}>
            <Popup><b>{s.name}</b><br />Tap “ETA” in the list for live arrivals.</Popup>
          </Marker>
        ) : null)}
        {vehicles.map(v => v.latitude != null ? (
          <Marker key={v.id} position={[v.latitude, v.longitude]} icon={busIcon(v)}>
            <Popup>
              <b>{v.registration_number}</b> — {v.route_name || 'No route'}<br />
              Speed: {v.speed_kmph ?? '—'} km/h · Seats free: {v.seats_available ?? '—'} / {v.capacity ?? '—'}<br />
              Crowd: {v.crowd_level || '—'}{v.is_stale ? ' · ⚠ stale data' : ''}
            </Popup>
          </Marker>
        ) : null)}
      </MapContainer>
    </div>
  )
}
