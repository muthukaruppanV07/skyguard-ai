import { useState } from 'react'
import { X, ChevronDown, ChevronUp, AlertCircle, CheckCircle, Info, Clock, Gauge, Brain, MapPin } from 'lucide-react'
import { formatTemperature, formatPressure, formatHumidity, formatScore, formatConfidence, formatDateTime, getSeverityColor, getSeverityClass } from '../utils/formatters'
import { ROOT_CAUSE_LABELS } from '../utils/constants'

export function AnomalyPanel({ anomaly, onClose }) {
  const [expanded, setExpanded] = useState(true)

  if (!anomaly) {
    return (
      <div className="card h-full flex flex-col">
        <div className="card-header flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">Anomaly Details</h3>
        </div>
        <div className="card-body flex-1 flex items-center justify-center text-gray-500">
          Click on a station row to view anomaly details
        </div>
      </div>
    )
  }

  const severityColor = getSeverityColor(anomaly.severity)

  return (
    <div className="card h-full flex flex-col">
      <div className="card-header flex items-center justify-between border-b-2" style={{ borderColor: severityColor }}>
        <h3 className="text-lg font-semibold text-gray-900">Anomaly Details</h3>
        <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg transition-colors">
          <X className="w-5 h-5 text-gray-500" />
        </button>
      </div>
      <div className="card-body flex-1 overflow-y-auto">
        <div className="space-y-6">
          <div className="flex items-center gap-4 p-4 rounded-xl" style={{ backgroundColor: `${severityColor}10` }}>
            <div className="w-16 h-16 rounded-xl flex items-center justify-center flex-shrink-0" style={{ backgroundColor: severityColor }}>
              <AlertCircle className="w-8 h-8 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl font-bold text-gray-900">{anomaly.station_id}</span>
                <span className={getSeverityClass(anomaly.severity)}>
                  {anomaly.severity}
                </span>
                <span className="text-sm text-gray-500">Score: {formatScore(anomaly.anomaly_score)}</span>
              </div>
              <p className="text-gray-600">
                <strong>Root Cause:</strong> {ROOT_CAUSE_LABELS[anomaly.root_cause] || anomaly.root_cause}
                <span className="ml-3 text-sm text-gray-500">Confidence: {formatConfidence(anomaly.confidence)}</span>
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Detected: {anomaly.timestamp ? formatDateTime(anomaly.timestamp) : 'Unknown'}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-red-50 border border-red-100">
              <div className="flex items-center gap-2 text-red-700 mb-1">
                <AlertCircle className="w-4 h-4" />
                <span className="font-medium">Observed</span>
              </div>
              <div className="space-y-1 text-sm">
                <p>Temp: <span className="font-mono font-semibold">{formatTemperature(anomaly.observed_temp)}</span></p>
                <p>Pressure: <span className="font-mono font-semibold">{formatPressure(anomaly.observed_pressure)}</span></p>
                <p>Humidity: <span className="font-mono font-semibold">{formatHumidity(anomaly.observed_humidity)}</span></p>
              </div>
            </div>
            <div className="p-4 rounded-xl bg-blue-50 border border-blue-100">
              <div className="flex items-center gap-2 text-blue-700 mb-1">
                <Gauge className="w-4 h-4" />
                <span className="font-medium">Expected (AI)</span>
              </div>
              <div className="space-y-1 text-sm">
                <p>Temp: <span className="font-mono font-semibold">{anomaly.expected_temp ? formatTemperature(anomaly.expected_temp) : 'N/A'}</span></p>
                <p>Pressure: <span className="font-mono font-semibold">{anomaly.expected_pressure ? formatPressure(anomaly.expected_pressure) : 'N/A'}</span></p>
                <p>Humidity: <span className="font-mono font-semibold">{anomaly.expected_humidity ? formatHumidity(anomaly.expected_humidity) : 'N/A'}</span></p>
              </div>
            </div>
            <div className="p-4 rounded-xl bg-green-50 border border-green-100">
              <div className="flex items-center gap-2 text-green-700 mb-1">
                <CheckCircle className="w-4 h-4" />
                <span className="font-medium">Correction</span>
              </div>
              <div className="space-y-1 text-sm">
                <p>Confidence: <span className="font-mono font-semibold">{formatConfidence(anomaly.correction_confidence)}</span></p>
                <p>Applied: <span className="font-medium">{anomaly.expected_temp ? 'Yes' : 'No'}</span></p>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-100 pt-4">
            <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Info className="w-5 h-5 text-blue-600" />
              AI Explanation
            </h4>
            <div className="p-4 rounded-lg bg-gray-50 border border-gray-100">
              <p className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
                {anomaly.explanation || 'No explanation available.'}
              </p>
            </div>
          </div>

          {anomaly.contributing_factors && (
            <div className="border-t border-gray-100 pt-4">
              <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Brain className="w-5 h-5 text-purple-600" />
                Contributing Factors
              </h4>
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
          )}

          <div className="border-t border-gray-100 pt-4">
            <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <MapPin className="w-5 h-5 text-orange-600" />
              Component Scores
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {[
                { key: 'rule', label: 'Rule-Based QC', icon: <CheckCircle className="w-4 h-4" /> },
                { key: 'isolation_forest', label: 'Isolation Forest', icon: <Brain className="w-4 h-4" /> },
                { key: 'autoencoder', label: 'Autoencoder', icon: <Brain className="w-4 h-4" /> },
                { key: 'temporal', label: 'Temporal Analysis', icon: <Clock className="w-4 h-4" /> },
                { key: 'multivariate', label: 'Multivariate', icon: <Gauge className="w-4 h-4" /> },
                { key: 'spatial', label: 'Spatial Consistency', icon: <MapPin className="w-4 h-4" /> },
              ].map((component) => (
                <div key={component.key} className="p-3 rounded-lg bg-white border border-gray-100">
                  <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                    {component.icon}
                    <span>{component.label}</span>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">
                    {anomaly[`${component.key}_score`] !== undefined ? formatScore(anomaly[`${component.key}_score`]) : '—'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}