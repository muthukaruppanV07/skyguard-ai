import { useState } from 'react'
import { ChevronUp, ChevronDown, ChevronRight, ExternalLink } from 'lucide-react'
import { formatTemperature, formatPressure, formatHumidity, formatTimestamp, getSeverityClass, formatScore, formatConfidence } from '../utils/formatters'

const columns = [
  { key: 'station_id', label: 'Station', sortable: true },
  { key: 'timestamp', label: 'Time', sortable: true },
  { key: 'temperature', label: 'Temp (°C)', sortable: true },
  { key: 'pressure', label: 'Pressure (hPa)', sortable: true },
  { key: 'humidity', label: 'Humidity (%)', sortable: true },
  { key: 'status', label: 'Status', sortable: true },
  { key: 'anomaly_score', label: 'Anomaly Score', sortable: true },
  { key: 'confidence', label: 'Confidence', sortable: true },
  { key: 'root_cause', label: 'Root Cause', sortable: false },
]

export function StationTable({ stations, onRowClick }) {
  const [sortConfig, setSortConfig] = useState({ key: 'timestamp', direction: 'desc' })
  const [filter, setFilter] = useState('')

  const sortedStations = [...stations].sort((a, b) => {
    if (!sortConfig.key) return 0
    const aVal = a[sortConfig.key]
    const bVal = b[sortConfig.key]
    if (aVal === bVal) return 0
    const direction = sortConfig.direction === 'asc' ? 1 : -1
    return aVal > bVal ? direction : -direction
  })

  const filteredStations = sortedStations.filter(s => 
    (s.station_id?.toLowerCase?.().includes(filter.toLowerCase())) ||
    (s.root_cause?.toLowerCase?.().includes(filter.toLowerCase()))
  )

  const handleSort = (key) => {
    setSortConfig(current => ({
      key,
      direction: current.key === key && current.direction === 'asc' ? 'desc' : 'asc',
    }))
  }

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) return null
    return sortConfig.direction === 'asc' ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />
  }

  return (
    <div className="card overflow-hidden">
      <div className="card-header flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Live Station Data</h3>
        <div className="relative">
          <input
            type="text"
            placeholder="Filter stations..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="input pl-10 w-64"
          />
          <ChevronRight className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              {columns.map(col => (
                <th
                  key={col.key}
                  className={`px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 ${col.sortable ? '' : ''}`}
                  onClick={() => col.sortable && handleSort(col.key)}
                >
                  <div className="flex items-center gap-1">
                    {col.label}
                    {col.sortable && getSortIcon(col.key)}
                  </div>
                </th>
              ))}
              <th className="px-4 py-3 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filteredStations.map((station) => (
              <tr
                key={station.station_id}
                className="hover:bg-gray-50 transition-colors cursor-pointer"
                onClick={() => onRowClick?.(station)}
              >
                <td className="px-4 py-3 font-mono text-sm font-medium text-gray-900">{station.station_id}</td>
                <td className="px-4 py-3 text-sm text-gray-500">{station.timestamp ? formatTimestamp(station.timestamp) : 'N/A'}</td>
                <td className="px-4 py-3 text-sm text-gray-900 font-mono">{station.temperature !== undefined ? formatTemperature(station.temperature) : 'N/A'}</td>
                <td className="px-4 py-3 text-sm text-gray-900 font-mono">{station.pressure !== undefined ? formatPressure(station.pressure) : 'N/A'}</td>
                <td className="px-4 py-3 text-sm text-gray-900 font-mono">{station.humidity !== undefined ? formatHumidity(station.humidity) : 'N/A'}</td>
                <td className="px-4 py-3">
                  <span className={getSeverityClass(station.severity || 'NORMAL')}>
                    {station.severity || 'NORMAL'}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm font-mono text-gray-900">
                  {station.anomaly_score !== undefined ? formatScore(station.anomaly_score) : '—'}
                </td>
                <td className="px-4 py-3 text-sm font-mono text-gray-900">
                  {station.confidence !== undefined ? formatConfidence(station.confidence) : '—'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600 max-w-xs truncate">
                  {station.root_cause || 'NORMAL'}
                </td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={(e) => { e.stopPropagation(); onRowClick?.(station) }}
                    className="text-blue-600 hover:text-blue-800 text-sm font-medium flex items-center justify-center gap-1 mx-auto"
                  >
                    <ExternalLink className="w-4 h-4" />
                    Details
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filteredStations.length === 0 && (
        <div className="p-8 text-center text-gray-500">
          No stations match the filter.
        </div>
      )}
    </div>
  )
}