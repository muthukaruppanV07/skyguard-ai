import { useState } from 'react'
import { Play, RotateCcw, Zap, AlertTriangle, CheckCircle, X } from 'lucide-react'
import { simulationApi } from '../services/api'
import { ANOMALY_INJECTION_TYPES } from '../utils/constants'

const QUICK_DEMO_ACTIONS = [
  { type: 'TEMPERATURE_SPIKE', station: 'AWS001', label: 'Temp Spike', icon: <Zap className="w-4 h-4" />, color: 'bg-red-100 text-red-700' },
  { type: 'PRESSURE_SPIKE', station: 'AWS002', label: 'Pressure Spike', icon: <Zap className="w-4 h-4" />, color: 'bg-blue-100 text-blue-700' },
  { type: 'FROZEN_SENSOR', station: 'AWS003', label: 'Freeze Sensor', icon: <AlertTriangle className="w-4 h-4" />, color: 'bg-orange-100 text-orange-700' },
  { type: 'COMMUNICATION_FAILURE', station: 'AWS004', label: 'Comm Failure', icon: <AlertTriangle className="w-4 h-4" />, color: 'bg-yellow-100 text-yellow-700' },
  { type: 'MULTIVARIATE_INCONSISTENCY', station: 'AWS005', label: 'Multivariate', icon: <Zap className="w-4 h-4" />, color: 'bg-purple-100 text-purple-700' },
]

export function DemoControls({ onDemoStep, onReset, running }) {
  const [activeAction, setActiveAction] = useState(null)
  const [customStation, setCustomStation] = useState('AWS001')
  const [customType, setCustomType] = useState('TEMPERATURE_SPIKE')
  const [showCustom, setShowCustom] = useState(false)

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
        <div className="space-y-4">
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

          <div className="border-t border-gray-100 pt-4">
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
          </div>
        </div>
      </div>
    </div>
  )
}