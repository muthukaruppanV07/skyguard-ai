import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, AlertTriangle, CheckCircle, HeartPulse } from 'lucide-react'
import { stationsApi, anomaliesApi, healthApi } from '../services/api'
import { STATION_COORDS, SENSOR_TYPES } from '../utils/constants'
import { formatTemperature, formatPressure, formatHumidity, formatScore, formatConfidence, formatDateTime, getSeverityClass, getSeverityColor, getHealthStatusLabel, getHealthStatusClass } from '../utils/formatters'
import { TemperatureChart } from '../components/Charts/TemperatureChart'
import { PressureChart } from '../components/Charts/PressureChart'
import { HumidityChart } from '../components/Charts/HumidityChart'
import { AnomalyScoreChart } from '../components/Charts/AnomalyScoreChart'
import { AnomalyPanel } from '../components/AnomalyPanel'
import { SensorHealth } from '../components/SensorHealth'

export function StationDetail() {
  const { stationId } = useParams()
  const [station, setStation] = useState(null)
  const [anomalies, setAnomalies] = useState([])
  const [health, setHealth] = useState(null)
  const [chartData, setChartData] = useState([])
  const [selectedAnomaly, setSelectedAnomaly] = useState(null)
  const [loading, setLoading] = useState(true)

  const coords = STATION_COORDS.find(c => c.station_id === stationId)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [stationRes, anomaliesRes, healthRes] = await Promise.all([
          stationsApi.get(stationId),
          anomaliesApi.list({ station_id: stationId, hours: 168, limit: 100 }),
          healthApi.station(stationId),
        ])
        setStation(stationRes.data)
        setAnomalies(anomaliesRes.data)
        setHealth(healthRes.data)
        
        const history = await fetchStationHistory(stationId)
        setChartData(history)
      } catch (e) {
        console.error('Failed to fetch station detail:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [stationId])

  const fetchStationHistory = async (stationId) => {
    try {
      const res = await stationsApi.get(stationId)
      return res.data.history || []
    } catch {
      return []
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Loading station details...</div>
      </div>
    )
  }

  if (!station) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900">Station not found</h2>
          <Link to="/" className="text-blue-600 hover:underline mt-2 inline-block">Back to Dashboard</Link>
        </div>
      </div>
    )
  }

  const recentAnomalies = anomalies.slice(0, 10)
  const severityColor = getSeverityColor(station.severity)

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            <Link to="/" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-gray-900">{station.station_id}</h1>
              <p className="text-sm text-gray-500">{coords?.name || 'Unknown Location'}</p>
            </div>
            <div className="ml-auto flex items-center gap-4">
              <span className={getSeverityClass(station.severity || 'NORMAL')}>
                {station.severity || 'NORMAL'}
              </span>
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: severityColor }} />
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="md:col-span-2 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="card p-6">
                <p className="text-sm text-gray-500">Temperature</p>
                <p className="text-3xl font-bold text-red-600 font-mono">{station.temperature ? formatTemperature(station.temperature) : 'N/A'}</p>
              </div>
              <div className="card p-6">
                <p className="text-sm text-gray-500">Pressure</p>
                <p className="text-3xl font-bold text-blue-600 font-mono">{station.pressure ? formatPressure(station.pressure) : 'N/A'}</p>
              </div>
              <div className="card p-6">
                <p className="text-sm text-gray-500">Humidity</p>
                <p className="text-3xl font-bold text-green-600 font-mono">{station.humidity ? formatHumidity(station.humidity) : 'N/A'}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <TemperatureChart data={chartData} anomalies={anomalies} />
              <PressureChart data={chartData} anomalies={anomalies} />
              <HumidityChart data={chartData} anomalies={anomalies} />
              <AnomalyScoreChart data={chartData} anomalies={anomalies} />
            </div>
          </div>

          <div className="space-y-6">
            <div className="card">
              <div className="card-header">
                <h3 className="text-lg font-semibold text-gray-900">Station Info</h3>
              </div>
              <div className="card-body space-y-4">
                <div>
                  <p className="text-sm text-gray-500">Coordinates</p>
                  <p className="font-mono text-gray-900">{coords?.lat?.toFixed(4)}, {coords?.lng?.toFixed(4)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Elevation</p>
                  <p className="font-mono text-gray-900">{coords?.elevation} m</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Last Update</p>
                  <p className="font-mono text-gray-900">{station.timestamp ? formatDateTime(station.timestamp) : 'N/A'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Anomaly Score</p>
                  <p className="text-2xl font-bold text-gray-900">{station.anomaly_score ? formatScore(station.anomaly_score) : '—'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Confidence</p>
                  <p className="text-2xl font-bold text-gray-900">{station.confidence ? formatConfidence(station.confidence) : '—'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Root Cause</p>
                  <p className="font-medium text-gray-900">{station.root_cause || 'NORMAL'}</p>
                </div>
              </div>
            </div>

            <SensorHealth healthData={health} />
          </div>
        </div>

        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Recent Anomalies</h3>
            <span className="text-sm text-gray-500">{anomalies.length} total</span>
          </div>
          <div className="card-body">
            {anomalies.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No anomalies recorded for this station</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {anomalies.slice(0, 20).map((anomaly) => (
                  <button
                    key={anomaly.id}
                    onClick={() => setSelectedAnomaly(anomaly)}
                    className="w-full text-left p-4 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors flex items-center justify-between"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${getSeverityColor(anomaly.severity)}15` }}>
                        <AlertTriangle className="w-5 h-5" style={{ color: getSeverityColor(anomaly.severity) }} />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{anomaly.root_cause}</p>
                        <p className="text-sm text-gray-500">{formatDateTime(anomaly.timestamp)} • Score: {formatScore(anomaly.anomaly_score)}</p>
                      </div>
                    </div>
                    <span className={getSeverityClass(anomaly.severity)}>{anomaly.severity}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {selectedAnomaly && (
          <AnomalyPanel
            anomaly={selectedAnomaly}
            onClose={() => setSelectedAnomaly(null)}
          />
        )}
      </main>
    </div>
  )
}