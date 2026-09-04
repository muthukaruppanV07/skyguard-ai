import { useEffect, useState, useCallback, useRef } from 'react'
import { useWebSocket } from '../services/websocket'
import { stationsApi, statisticsApi, healthApi, anomaliesApi, simulationApi } from '../services/api'
import { Header } from '../components/Header'
import { SummaryCards } from '../components/SummaryCards'
import { StationTable } from '../components/StationTable'
import { TemperatureChart } from '../components/Charts/TemperatureChart'
import { PressureChart } from '../components/Charts/PressureChart'
import { HumidityChart } from '../components/Charts/HumidityChart'
import { AnomalyScoreChart } from '../components/Charts/AnomalyScoreChart'
import { StationMap } from '../components/Map/StationMap'
import { AnomalyPanel } from '../components/AnomalyPanel'
import { SensorHealth } from '../components/SensorHealth'
import { DemoControls } from '../components/DemoControls'
import { AlertBanner } from '../components/AlertBanner'
import { STATION_COORDS } from '../utils/constants'

export function Dashboard() {
  const [stations, setStations] = useState([])
  const [statistics, setStatistics] = useState(null)
  const [healthData, setHealthData] = useState(null)
  const [selectedStation, setSelectedStation] = useState(null)
  const [anomalies, setAnomalies] = useState([])
  const [alerts, setAlerts] = useState([])
  const [chartData, setChartData] = useState({})
  const [demoRunning, setDemoRunning] = useState(false)
  const [demoStep, setDemoStep] = useState(0)
  const [demoMode, setDemoMode] = useState('manual')
  const stationHistoryRef = useRef({})

  const fetchInitialData = useCallback(async () => {
    try {
      const [stationsRes, statsRes, healthRes, anomaliesRes] = await Promise.all([
        stationsApi.list(),
        statisticsApi.get(24),
        healthApi.network(),
        anomaliesApi.list({ hours: 24, limit: 50 }),
      ])
      setStations(stationsRes.data)
      setStatistics(statsRes.data)
      setHealthData(healthRes.data)
      setAnomalies(anomaliesRes.data)
    } catch (e) {
      console.error('Failed to fetch initial data:', e)
    }
  }, [])

  const fetchChartData = useCallback(async (stationId) => {
    try {
      const res = await stationsApi.get(stationId)
      // Would need a proper endpoint for historical data
    } catch (e) {
      console.error('Failed to fetch chart data:', e)
    }
  }, [])

  useEffect(() => {
    fetchInitialData()
    const interval = setInterval(fetchInitialData, 5000)
    return () => clearInterval(interval)
  }, [fetchInitialData])

  const handleLiveUpdate = useCallback((data) => {
    if (data.type === 'live_update' || data.type === 'initial_snapshot') {
      const stationUpdates = data.stations || {}
      
      setStations(prev => prev.map(s => {
        const update = stationUpdates[s.station_id]
        if (update) {
          if (!stationHistoryRef.current[s.station_id]) {
            stationHistoryRef.current[s.station_id] = []
          }
          stationHistoryRef.current[s.station_id].push({
            timestamp: update.timestamp,
            temperature: update.temperature,
            pressure: update.pressure,
            humidity: update.humidity,
            anomaly_score: update.anomaly_score,
            severity: update.severity,
          })
          if (stationHistoryRef.current[s.station_id].length > 200) {
            stationHistoryRef.current[s.station_id].shift()
          }
          
          return {
            ...s,
            ...update,
            timestamp: update.timestamp,
          }
        }
        return s
      }))

      setChartData(prev => ({
        ...prev,
        ...Object.fromEntries(
          Object.entries(stationUpdates).map(([id, update]) => [
            id,
            (prev[id] || []).concat({
              timestamp: update.timestamp,
              temperature: update.temperature,
              pressure: update.pressure,
              humidity: update.humidity,
              anomaly_score: update.anomaly_score,
            }).slice(-200)
          ])
        )
      }))
    } else if (data.type === 'anomaly') {
      setAlerts(prev => [{
        id: data.anomaly_id,
        station_id: data.station_id,
        severity: data.severity,
        message: data.message,
        timestamp: new Date().toISOString(),
        acknowledged: false,
      }, ...prev].slice(0, 10))
      
      fetchInitialData()
    }
  }, [fetchInitialData])

  useWebSocket(handleLiveUpdate)

  const handleStationClick = useCallback((station) => {
    setSelectedStation(station)
    if (stationHistoryRef.current[station.station_id]) {
      setChartData(prev => ({
        ...prev,
        [station.station_id]: stationHistoryRef.current[station.station_id]
      }))
    }
  }, [])

  const handleAlertDismiss = useCallback((id) => {
    setAlerts(prev => prev.filter(a => a.id !== id))
  }, [])

  const handleAlertAcknowledge = useCallback(async (id) => {
    try {
      await anomaliesApi.acknowledge?.(id)
      setAlerts(prev => prev.map(a => a.id === id ? { ...a, acknowledged: true } : a))
    } catch (e) {
      console.error('Failed to acknowledge:', e)
    }
  }, [])

  const handleDemoStep = useCallback(async (step) => {
    setDemoStep(prev => prev + 1)
  }, [])

  const handleReset = useCallback(async () => {
    await simulationApi.reset()
    setDemoStep(0)
    fetchInitialData()
  }, [fetchInitialData])

  const stationMapData = stations.map(s => ({
    ...s,
    ...STATION_COORDS.find(c => c.station_id === s.station_id),
  }))

  const selectedStationHistory = selectedStation 
    ? (chartData[selectedStation.station_id] || [])
    : []

  const selectedStationAnomalies = anomalies.filter(a => a.station_id === selectedStation?.station_id)

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <AlertBanner
        alerts={alerts}
        onDismiss={handleAlertDismiss}
        onAcknowledge={handleAlertAcknowledge}
      />
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <SummaryCards data={statistics} />
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <StationTable
              stations={stations}
              onRowClick={handleStationClick}
            />
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <TemperatureChart data={selectedStationHistory} anomalies={selectedStationAnomalies} />
              <PressureChart data={selectedStationHistory} anomalies={selectedStationAnomalies} />
              <HumidityChart data={selectedStationHistory} anomalies={selectedStationAnomalies} />
              <AnomalyScoreChart data={selectedStationHistory} anomalies={selectedStationAnomalies} />
            </div>
          </div>
          
          <div className="space-y-6">
            <StationMap
              stations={stationMapData}
              selectedStation={selectedStation}
              onStationClick={handleStationClick}
            />
            
            <SensorHealth healthData={healthData} />
            
            <DemoControls
              onDemoStep={handleDemoStep}
              onReset={handleReset}
              running={demoRunning}
            />
          </div>
        </div>

        {selectedStation && (
          <AnomalyPanel
            anomaly={selectedStationAnomalies[0] || null}
            onClose={() => setSelectedStation(null)}
          />
        )}
      </main>
    </div>
  )
}