import { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, CircleMarker } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { STATION_COORDS } from '../../utils/constants'
import { getSeverityColor } from '../../utils/formatters'

const iconRetinaUrl = 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png'
const iconUrl = 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png'
const shadowUrl = 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'

const DefaultIcon = L.icon({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

function CustomMarker({ station, onClick }) {
  const color = getSeverityColor(station?.severity)
  const markerRef = useRef(null)
  const stationId = station?.station_id || ''
  const stationName = station?.name || 'Unknown'

  useEffect(() => {
    if (markerRef.current) {
      const icon = L.divIcon({
        className: 'custom-station-marker',
        html: `
          <div style="
            width: 24px; height: 24px; border-radius: 50%;
            background: ${color}; border: 3px solid white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            display: flex; align-items: center; justify-content: center;
            font-size: 10px; font-weight: bold; color: white;
          ">
            ${stationId.replace('AWS', '')}
          </div>
        `,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      })
      markerRef.current.setIcon(icon)
    }
  }, [color, stationId])

  if (!station?.latitude || !station?.longitude) {
    return null
  }

  return (
    <Marker
      position={[station.latitude, station.longitude]}
      ref={markerRef}
      icon={DefaultIcon}
      onClick={onClick}
    >
      <Popup>
        <div className="p-2 min-w-[200px]">
          <h4 className="font-bold text-gray-900">{stationName} ({stationId})</h4>
          <div className="mt-2 space-y-1 text-sm">
            <p><span className="font-medium">Temp:</span> {station.temperature?.toFixed(1)}°C</p>
            <p><span className="font-medium">Pressure:</span> {station.pressure?.toFixed(1)} hPa</p>
            <p><span className="font-medium">Humidity:</span> {station.humidity?.toFixed(1)}%</p>
            <p>
              <span className="font-medium">Status:</span>
              <span className="ml-2 px-2 py-0.5 rounded text-xs font-medium" style={{ backgroundColor: `${color}20`, color }}>
                {station.severity || 'NORMAL'}
              </span>
            </p>
            <p><span className="font-medium">Score:</span> {station.anomaly_score?.toFixed(1) || 0}</p>
          </div>
        </div>
      </Popup>
    </Marker>
  )
}

export function StationMap({ stations, selectedStation, onStationClick }) {
  const center = [22.5, 78.5]
  
  return (
    <div className="card h-96">
      <div className="card-header">
        <h3 className="text-lg font-semibold text-gray-900">Station Network</h3>
      </div>
      <div className="card-body p-0 h-[calc(100%-60px)]">
        <MapContainer
          center={center}
          zoom={5}
          scrollWheelZoom={true}
          style={{ width: '100%', height: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {stations.map((station) => (
            <CustomMarker
              key={station.station_id}
              station={station}
              onClick={() => onStationClick?.(station)}
            />
          ))}
        </MapContainer>
      </div>
    </div>
  )
}