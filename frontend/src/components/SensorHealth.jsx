import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts'
import { SENSOR_TYPES } from '../utils/constants'
import { formatScore, getHealthStatusLabel, getHealthStatusClass } from '../utils/formatters'

const SENSOR_COLORS = {
  TEMPERATURE: '#ef4444',
  PRESSURE: '#3b82f6',
  HUMIDITY: '#22c55e',
}

export function SensorHealth({ healthData }) {
  if (!healthData || !healthData.sensors) {
    return (
      <div className="card h-full flex items-center justify-center">
        <p className="text-gray-500">No health data available</p>
      </div>
    )
  }

  const sensors = Object.entries(healthData.sensors).map(([key, value]) => ({
    sensor: key,
    score: value.score,
    status: value.status,
    ...value,
  }))

  return (
    <div className="card h-full">
      <div className="card-header flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Sensor Health</h3>
        <span className="text-sm text-gray-500">Overall: {healthData.overall_score?.toFixed(1) || 0}%</span>
      </div>
      <div className="card-body">
        <div className="space-y-4">
          {SENSOR_TYPES.map(({ value, label, unit, color }) => {
            const sensor = sensors.find(s => s.sensor === value)
            if (!sensor) return null

            const statusClass = getHealthStatusClass(sensor.score)
            const statusLabel = getHealthStatusLabel(sensor.score)

            return (
              <div key={value} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                    <span className="font-medium text-gray-900">{label}</span>
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${statusClass} bg-opacity-10`}>
                      {statusLabel}
                    </span>
                  </div>
                  <span className="text-lg font-bold" style={{ color }}>{formatScore(sensor.score)}</span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${sensor.score}%`,
                      backgroundColor: color,
                    }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-500">
                  <span>Anomalies (24h): {sensor.anomaly_count_24h || 0}</span>
                  <span>Anomalies (7d): {sensor.anomaly_count_7d || 0}</span>
                  {sensor.drift_detected && <span className="text-orange-600">Drift detected</span>}
                  {sensor.frozen_count > 0 && <span className="text-red-600">Frozen: {sensor.frozen_count}</span>}
                </div>
              </div>
            )
          })}
        </div>

        <div className="mt-6">
          <h4 className="font-semibold text-gray-900 mb-3">Health Comparison</h4>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sensors} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 11 }} />
                <YAxis type="category" dataKey="sensor" width={100} tick={{ fill: '#6b7280', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                  formatter={(value) => [value.toFixed(1), 'Health Score']}
                />
                <Legend />
                <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                  {sensors.map((_, idx) => (
                    <Cell key={`cell-${idx}`} fill={SENSOR_COLORS[sensors[idx]?.sensor] || '#6b7280'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}