import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, AlertTriangle, CheckCircle, Brain, Clock, Gauge, MapPin, Shield } from 'lucide-react'
import { anomaliesApi, explainApi } from '../services/api'
import { formatTemperature, formatPressure, formatHumidity, formatScore, formatConfidence, formatDateTime, getSeverityClass, getSeverityColor } from '../utils/formatters'
import { ROOT_CAUSE_LABELS } from '../utils/constants'

export function AnomalyDetail() {
  const { anomalyId } = useParams()
  const [anomaly, setAnomaly] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [anomalyRes, explainRes] = await Promise.all([
          anomaliesApi.get(anomalyId),
          explainApi.get(anomalyId).catch(() => ({ data: null })),
        ])
        setAnomaly(anomalyRes.data)
        setExplanation(explainRes.data)
      } catch (e) {
        console.error('Failed to fetch anomaly detail:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [anomalyId])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Loading anomaly details...</div>
      </div>
    )
  }

  if (!anomaly) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900">Anomaly not found</h2>
          <Link to="/" className="text-blue-600 hover:underline mt-2 inline-block">Back to Dashboard</Link>
        </div>
      </div>
    )
  }

  const severityColor = getSeverityColor(anomaly.severity)

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            <Link to="/" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Anomaly #{anomaly.id}</h1>
              <p className="text-sm text-gray-500">{anomaly.station_id} • {anomaly.root_cause}</p>
            </div>
            <div className="ml-auto flex items-center gap-4">
              <span className={getSeverityClass(anomaly.severity)}>{anomaly.severity}</span>
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: severityColor }} />
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="card">
              <div className="card-header flex items-center justify-between border-b-2" style={{ borderColor: severityColor }}>
                <h3 className="text-lg font-semibold text-gray-900">Anomaly Overview</h3>
                <span className={`px-3 py-1 rounded-full text-sm font-medium`} style={{ backgroundColor: `${severityColor}15`, color: severityColor }}>
                  {anomaly.severity}
                </span>
              </div>
              <div className="card-body">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                  <div className="p-4 rounded-xl" style={{ backgroundColor: `${severityColor}10` }}>
                    <p className="text-sm text-gray-500">Anomaly Score</p>
                    <p className="text-4xl font-bold text-gray-900" style={{ color: severityColor }}>{formatScore(anomaly.anomaly_score)}</p>
                    <p className="text-sm text-gray-500">Confidence: {formatConfidence(anomaly.confidence)}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-blue-50">
                    <p className="text-sm text-gray-500">Root Cause</p>
                    <p className="text-lg font-semibold text-gray-900">{ROOT_CAUSE_LABELS[anomaly.root_cause] || anomaly.root_cause}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-green-50">
                    <p className="text-sm text-gray-500">Correction Confidence</p>
                    <p className="text-lg font-semibold text-gray-900">{formatConfidence(anomaly.correction_confidence)}</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="p-4 rounded-xl bg-red-50">
                    <p className="text-sm text-gray-500">Observed</p>
                    <div className="space-y-1 mt-2">
                      <p>Temp: <span className="font-mono font-semibold">{formatTemperature(anomaly.observed_temp)}</span></p>
                      <p>Pressure: <span className="font-mono font-semibold">{formatPressure(anomaly.observed_pressure)}</span></p>
                      <p>Humidity: <span className="font-mono font-semibold">{formatHumidity(anomaly.observed_humidity)}</span></p>
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-blue-50">
                    <p className="text-sm text-gray-500">Expected (AI)</p>
                    <div className="space-y-1 mt-2">
                      <p>Temp: <span className="font-mono font-semibold">{anomaly.expected_temp ? formatTemperature(anomaly.expected_temp) : 'N/A'}</span></p>
                      <p>Pressure: <span className="font-mono font-semibold">{anomaly.expected_pressure ? formatPressure(anomaly.expected_pressure) : 'N/A'}</span></p>
                      <p>Humidity: <span className="font-mono font-semibold">{anomaly.expected_humidity ? formatHumidity(anomaly.expected_humidity) : 'N/A'}</span></p>
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-green-50">
                    <p className="text-sm text-gray-500">Deviation</p>
                    <div className="space-y-1 mt-2">
                      <p>Temp: <span className="font-mono font-semibold text-red-600">{anomaly.expected_temp ? formatTemperature(Math.abs(anomaly.observed_temp - anomaly.expected_temp)) : 'N/A'}</span></p>
                      <p>Pressure: <span className="font-mono font-semibold text-red-600">{anomaly.expected_pressure ? formatPressure(Math.abs(anomaly.observed_pressure - anomaly.expected_pressure)) : 'N/A'}</span></p>
                      <p>Humidity: <span className="font-mono font-semibold text-red-600">{anomaly.expected_humidity ? formatHumidity(Math.abs(anomaly.observed_humidity - anomaly.expected_humidity)) : 'N/A'}</span></p>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-100 pt-6">
                  <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <Shield className="w-5 h-5 text-blue-600" />
                    AI Explanation
                  </h4>
                  <div className="p-4 rounded-lg bg-gray-50 border border-gray-100">
                    <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
                      {anomaly.explanation || 'No explanation available.'}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <h3 className="text-lg font-semibold text-gray-900">Component Scores</h3>
              </div>
              <div className="card-body">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {[
                    { key: 'rule', label: 'Rule-Based QC', icon: <CheckCircle className="w-4 h-4" />, color: '#22c55e' },
                    { key: 'isolation_forest', label: 'Isolation Forest', icon: <Brain className="w-4 h-4" />, color: '#3b82f6' },
                    { key: 'autoencoder', label: 'Autoencoder', icon: <Brain className="w-4 h-4" />, color: '#8b5cf6' },
                    { key: 'temporal', label: 'Temporal Analysis', icon: <Clock className="w-4 h-4" />, color: '#f97316' },
                    { key: 'multivariate', label: 'Multivariate', icon: <Gauge className="w-4 h-4" />, color: '#ec4899' },
                    { key: 'spatial', label: 'Spatial Consistency', icon: <MapPin className="w-4 h-4" />, color: '#06b6d4' },
                  ].map((component) => (
                    <div key={component.key} className="p-4 rounded-lg border border-gray-100">
                      <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                        <span style={{ color: component.color }}>{component.icon}</span>
                        <span>{component.label}</span>
                      </div>
                      <div className="text-3xl font-bold text-gray-900" style={{ color: component.color }}>
                        {anomaly[`${component.key}_score`] !== undefined ? formatScore(anomaly[`${component.key}_score`]) : '—'}
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full mt-2 overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${anomaly[`${component.key}_score`] || 0}%`,
                            backgroundColor: component.color,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="card">
              <div className="card-header">
                <h3 className="text-lg font-semibold text-gray-900">Metadata</h3>
              </div>
              <div className="card-body space-y-4">
                <div className="flex justify-between">
                  <span className="text-gray-500">Anomaly ID</span>
                  <span className="font-mono font-medium">#{anomaly.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Station</span>
                  <span className="font-medium">{anomaly.station_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Timestamp</span>
                  <span className="font-mono text-sm">{formatDateTime(anomaly.timestamp)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Model Version</span>
                  <span className="font-mono text-sm">{anomaly.model_version}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Reading ID</span>
                  <span className="font-mono text-sm">#{anomaly.reading_id}</span>
                </div>
              </div>
            </div>

            {explanation && explanation.shap_values && (
              <div className="card">
                <div className="card-header">
                  <h3 className="text-lg font-semibold text-gray-900">SHAP Feature Importance</h3>
                </div>
                <div className="card-body">
                  <div className="space-y-3">
                    {explanation.top_features?.slice(0, 10).map((feat, idx) => (
                      <div key={idx} className="flex items-center gap-3">
                        <span className="text-sm font-medium text-gray-700 w-48 truncate">{feat.feature}</span>
                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-purple-600"
                            style={{ width: `${Math.min(feat.importance * 1000, 100)}%` }}
                          />
                        </div>
                        <span className="text-sm font-mono text-gray-500 w-16 text-right">{feat.importance.toFixed(4)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {anomaly.contributing_factors && (
              <div className="card">
                <div className="card-header">
                  <h3 className="text-lg font-semibold text-gray-900">Contributing Factors</h3>
                </div>
                <div className="card-body">
                  <div className="space-y-2">
                    {typeof anomaly.contributing_factors === 'string' ? (
                      <p className="text-sm text-gray-600">{anomaly.contributing_factors}</p>
                    ) : (
                      anomaly.contributing_factors.map((factor, idx) => (
                        <div key={idx} className="p-3 rounded-lg bg-white border border-gray-100 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="text-sm font-medium text-gray-700">{factor.factor || factor}</span>
                            <span className={`text-xs px-2 py-0.5 rounded ${factor.impact === 'high' ? 'bg-red-100 text-red-700' : factor.impact === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'}`}>
                              {factor.impact || 'low'}
                            </span>
                          </div>
                          <div className="text-sm font-mono font-semibold text-gray-900">{factor.score}</div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}