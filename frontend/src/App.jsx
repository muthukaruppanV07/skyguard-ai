import { Routes, Route } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { StationDetail } from './pages/StationDetail'
import { AnomalyDetail } from './pages/AnomalyDetail'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/station/:stationId" element={<StationDetail />} />
      <Route path="/anomaly/:anomalyId" element={<AnomalyDetail />} />
    </Routes>
  )
}