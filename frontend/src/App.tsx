import { useState } from 'react';
import { Route, Routes, useLocation, useParams } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import PresentBar from './components/PresentBar';
import { usePresentation } from './presentation';
import Dashboard from './pages/Dashboard';
import LiveMonitor from './pages/LiveMonitor';
import Stations from './pages/Stations';
import StationDetail from './pages/StationDetail';
import StationIntelligence from './pages/StationIntelligence';
import AnomalyCenter from './pages/AnomalyCenter';
import Alerts from './pages/Alerts';
import AnomalyDetail from './pages/AnomalyDetail';
import AIInsights from './pages/AIInsights';
import SensorHealth from './pages/SensorHealth';
import SensorHealthDetail from './pages/SensorHealthDetail';
import Maintenance from './pages/Maintenance';
import DataQuality from './pages/DataQuality';
import Analytics from './pages/Analytics';
import Simulation from './pages/Simulation';
import Demo from './pages/Demo';
import Evaluation from './pages/Evaluation';
import WhySkyguard from './pages/WhySkyguard';
import Judge from './pages/Judge';
import Spatial from './pages/Spatial';
import Reports from './pages/Reports';
import Settings from './pages/Settings';

function HealthDetailRoute() {
  return <SensorHealthDetail />;
}

function StationDetailRoute() {
  return <StationDetail />;
}

export default function App() {
  const [navOpen, setNavOpen] = useState(false);
  const [simRunning, setSimRunning] = useState(false);
  const location = useLocation();
  const { enabled: presenting } = usePresentation();

  if (presenting) {
    return (
      <div className="min-h-screen">
        <PresentBar simRunning={simRunning} />
        <main key={location.pathname} className="present-stage mx-auto">
          <Routes>
            <Route path="/demo" element={<Demo />} />
            <Route path="*" element={<Demo />} />
          </Routes>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="lg:pl-60">
        <Topbar onMenu={() => setNavOpen(true)} simRunning={simRunning} />
        <main key={location.pathname} className="mx-auto max-w-[1400px]">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/live" element={<LiveMonitor onSimChange={setSimRunning} />} />
            <Route path="/stations" element={<Stations />} />
            <Route path="/stations/:stationId" element={<StationDetailRoute />} />
            <Route path="/stations/:stationId/intel" element={<StationIntelligence />} />
            <Route path="/anomalies" element={<AnomalyCenter />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/anomalies/:anomalyId" element={<AnomalyDetail />} />
            <Route path="/insights" element={<AIInsights />} />
            <Route path="/health" element={<SensorHealth />} />
            <Route path="/health/:stationId" element={<HealthDetailRoute />} />
            <Route path="/maintenance" element={<Maintenance />} />
            <Route path="/data" element={<DataQuality />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/simulation" element={<Simulation />} />
            <Route path="/demo" element={<Demo />} />
            <Route path="/evaluation" element={<Evaluation />} />
            <Route path="/why" element={<WhySkyguard />} />
            <Route path="/judge" element={<Judge />} />
            <Route path="/spatial" element={<Spatial />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<div className="p-8 text-center text-slate-500">Unknown route — use the sidebar.</div>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
