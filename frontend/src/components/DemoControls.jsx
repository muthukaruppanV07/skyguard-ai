import { useState } from 'react'
import { Play, RotateCcw, Zap, AlertTriangle, CheckCircle, X, Download, Cpu, Server, Database, Wifi, Brain, Cloud, Shield } from 'lucide-react'
import { simulationApi } from '../services/api'
import { ANOMALY_INJECTION_TYPES } from '../utils/constants'

const QUICK_DEMO_ACTIONS = [
  { type: 'TEMPERATURE_SPIKE', station: 'AWS001', label: 'Temp Spike', icon: <Zap className="w-4 h-4" />, color: 'bg-red-100 text-red-700' },
  { type: 'PRESSURE_SPIKE', station: 'AWS002', label: 'Pressure Spike', icon: <Zap className="w-4 h-4" />, color: 'bg-blue-100 text-blue-700' },
  { type: 'FROZEN_SENSOR', station: 'AWS003', label: 'Freeze Sensor', icon: <AlertTriangle className="w-4 h-4" />, color: 'bg-orange-100 text-orange-700' },
  { type: 'COMMUNICATION_FAILURE', station: 'AWS004', label: 'Comm Failure', icon: <AlertTriangle className="w-4 h-4" />, color: 'bg-yellow-100 text-yellow-700' },
  { type: 'MULTIVARIATE_INCONSISTENCY', station: 'AWS005', label: 'Multivariate', icon: <Zap className="w-4 h-4" />, color: 'bg-purple-100 text-purple-700' },
]

const ADVANCED_ACTIONS = [
  { action: 'export_onnx', label: 'Export ONNX', icon: <Download className="w-4 h-4" />, color: 'bg-indigo-100 text-indigo-700', desc: 'Export models to ONNX for edge deployment' },
  { action: 'train_lstm', label: 'Train LSTM', icon: <Brain className="w-4 h-4" />, color: 'bg-pink-100 text-pink-700', desc: 'Train LSTM Autoencoder for temporal patterns' },
  { action: 'start_esp32_fleet', label: 'ESP32 Fleet', icon: <Wifi className="w-4 h-4" />, color: 'bg-cyan-100 text-cyan-700', desc: 'Launch 8 ESP32 devices via MQTT' },
  { action: 'load_imd_data', label: 'IMD Sample Data', icon: <Database className="w-4 h-4" />, color: 'bg-green-100 text-green-700', desc: 'Load realistic IMD sample data' },
  { action: 'export_onnx', label: 'Validate ONNX', icon: <Shield className="w-4 h-4" />, color: 'bg-violet-100 text-violet-700', desc: 'Validate ONNX model inference' },
  { action: 'train_lstm', label: 'LSTM Inference', icon: <Cpu className="w-4 h-4" />, color: 'bg-rose-100 text-rose-700', desc: 'Run LSTM Autoencoder inference' },
]

export function DemoControls({ onDemoStep, onReset, running }) {
  const [activeAction, setActiveAction] = useState(null)
  const [customStation, setCustomStation] = useState('AWS001')
  const [customType, setCustomType] = useState('TEMPERATURE_SPIKE')
  const [showCustom, setShowCustom] = useState(false)
  const [activeTab, setActiveTab] = useState('quick')

  const handleQuickInject = async (action) => {
    setActiveAction(action.type)
    try {
      await simulationApi.inject({
        station_id: action.station,
        fault_type: action.type,
        params: { magnitude: 25 },
      })
      onDemoStep?.(action.type)
    } catch (e) {
      console.error('Failed to inject anomaly:', e)
    } finally {
      setTimeout(() => setActiveAction(null), 2000)
    }
  }

  const handleAdvancedAction = async (action) => {
    setActiveAction(action.action)
    try {
      await simulationApi.advancedAction(action.action)
      onDemoStep?.(action.action)
    } catch (e) {
      console.error('Advanced action failed:', e)
    } finally {
      setTimeout(() => setActiveAction(null), 2000)
    }
  }

  const handleCustomInject = async () => {
    setActiveAction(customType)
    try {
      await simulationApi.inject({
        station_id: customStation,
        fault_type: customType,
        params: { magnitude: 25 },
      })
      onDemoStep?.(customType)
    } catch (e) {
      console.error('Failed to inject anomaly:', e)
    } finally {
      setTimeout(() => setActiveAction(null), 2000)
    }
  }

  const handleReset = async () => {
    try {
      await simulationApi.reset()
      onReset?.()
    } catch (e) {
      console.error('Failed to reset:', e)
    }
  }

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Zap className="w-5 h-5 text-orange-500" />
          SIH Demo Controls
        </h3>
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${running ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
          {running ? 'LIVE' : 'PAUSED'}
        </span>
      </div>
      <div className="card-body">
        <div className="mb-4 border-b border-gray-100">
          <nav className="flex gap-4" role="tablist">
            <button
              role="tab"
              aria-selected={activeTab === 'quick'}
              onClick={() => setActiveTab('quick')}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${activeTab === 'quick' ? 'bg-orange-100 text-orange-700 border-b-2 border-orange-500' : 'text-gray-500 hover:text-gray-700'}`}
            >
              Quick Actions
            </button>
            <button
              role="tab"
              aria-selected={activeTab === 'advanced'}
              onClick={() => setActiveTab('advanced')}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${activeTab === 'advanced' ? 'bg-indigo-100 text-indigo-700 border-b-2 border-indigo-500' : 'text-gray-500 hover:text-gray-700'}`}
            >
              Advanced Features
            </button>
            <button
              role="tab"
              aria-selected={activeTab === 'custom'}
              onClick={() => setActiveTab('custom')}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${activeTab === 'custom' ? 'bg-orange-100 text-orange-700 border-b-2 border-orange-500' : 'text-gray-500 hover:text-gray-700'}`}
            >
              Custom Injection
            </button>
          </nav>
        </div>

        <div className="space-y-4">
          {activeTab === 'quick' && (
            <div>
              <h4 className="font-medium text-gray-900 mb-3">Quick Actions</h4>
              <div className="flex flex-wrap gap-2">
                {QUICK_DEMO_ACTIONS.map((action) => (
                  <button
                    key={action.type}
                    onClick={() => handleQuickInject(action)}
                    disabled={running || activeAction !== null}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-50 ${action.color} hover:opacity-90 ${activeAction === action.type ? 'ring-2 ring-offset-2' : ''}`}
                    style={{ ringColor: action.color.replace('bg-', '').replace('100', '500') }}
                  >
                    {action.icon}
                    <span>{action.label}</span>
                    {activeAction === action.type && <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />}
                  </button>
                ))}
                <button
                  onClick={handleReset}
                  disabled={running}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>Reset Demo</span>
                </button>
              </div>
            </div>
          )}

          {activeTab === 'advanced' && (
            <div>
              <h4 className="font-medium text-gray-900 mb-3">Advanced Features</h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {ADVANCED_ACTIONS.map((action) => (
                  <button
                    key={action.action}
                    onClick={() => handleAdvancedAction(action)}
                    disabled={running || activeAction !== null}
                    className={`flex flex-col items-center gap-2 p-4 rounded-lg text-sm font-medium transition-all disabled:opacity-50 ${action.color} hover:opacity-90 hover:shadow-md ${activeAction === action.action ? 'ring-2 ring-offset-2' : ''}`}
                    style={{ ringColor: action.color.replace('bg-', '').replace('100', '500') }}
                  >
                    <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-white/50">
                      {action.icon}
                    </div>
                    <span className="text-center">{action.label}</span>
                    <span className="text-xs text-gray-500 text-center">{action.desc}</span>
                    {activeAction === action.action && <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />}
                  </button>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'custom' && (
            <div>
              <h4 className="font-medium text-gray-900 mb-3">Custom Injection</h4>
              <div className="flex flex-wrap items-end gap-4">
                <div>
                  <label className="label">Station</label>
                  <select
                    value={customStation}
                    onChange={(e) => setCustomStation(e.target.value)}
                    className="input w-36"
                  >
                    {['AWS001', 'AWS002', 'AWS003', 'AWS004', 'AWS005', 'AWS006', 'AWS007', 'AWS008'].map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Fault Type</label>
                  <select
                    value={customType}
                    onChange={(e) => setCustomType(e.target.value)}
                    className="input w-52"
                  >
                    {ANOMALY_INJECTION_TYPES.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleCustomInject}
                  disabled={running || activeAction !== null}
                  className="px-4 py-2 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 disabled:opacity-50 transition-colors"
                >
                  {activeAction ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                      Injecting...
                    </>
                  ) : (
                    'Inject'
                  )}
                </button>
              </div>
            </div>
          )}

          <div className="border-t border-gray-100 pt-4 text-sm text-gray-500">
            <p className="font-medium mb-1">Demo Sequence:</p>
            <ol className="list-decimal list-inside space-y-1">
              <li>Show healthy network baseline (3s)</li>
              <li>Temperature Spike - AWS001 (5s)</li>
              <li>Sensor Drift - AWS002 (5s)</li>
              <li>Frozen Sensor - AWS003 (5s)</li>
              <li>Communication Failure - AWS004 (5s)</li>
              <li>Multivariate Anomaly - AWS005 (5s)</li>
              <li>Pressure Spike - AWS006 (5s)</li>
              <li>Humidity Drop - AWS007 (5s)</li>
              <li>Sensor Degradation - AWS008 (5s)</li>
              <li>Reset to healthy state (2s)</li>
            </ol>
            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
              <p className="font-medium text-blue-800 mb-1">Advanced Features Available:</p>
              <ul className="list-disc list-inside space-y-1 text-blue-700 text-xs">
                <li>ONNX Model Export & Validation</li>
                <li>LSTM Autoencoder Training & Inference</li>
                <li>ESP32 Fleet (8 devices via MQTT)</li>
                <li>Real IMD Data (Monsoon/Heatwave/Cyclone)</li>
                <li>SHAP Explainability & Waterfall Plots</li>
                <li>Model Drift Detection & Monitoring</li>
                <li>Streaming Architecture (Redis/In-Memory)</li>
                <li>Multi-channel Alerting (Email/Slack/Telegram)</li>
                <li>MLflow Model Registry & Deployment</li>
                <li>Performance Dashboard with Live Metrics</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}