import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Area } from 'recharts'
import { CHART_COLORS, CHART_MARGIN, formatChartData, SEVERITY_COLORS } from '../../charts/chartUtils'

export function AnomalyScoreChart({ data, anomalies = [] }) {
  const chartData = formatChartData(data, 'anomaly_score')
  
  const severityZones = [
    { y: 0, y2: 30, color: SEVERITY_COLORS.NORMAL, label: 'Normal' },
    { y: 30, y2: 50, color: SEVERITY_COLORS.LOW, label: 'Low' },
    { y: 50, y2: 70, color: SEVERITY_COLORS.SUSPICIOUS, label: 'Suspicious' },
    { y: 70, y2: 85, color: SEVERITY_COLORS.HIGH, label: 'High' },
    { y: 85, y2: 100, color: SEVERITY_COLORS.CRITICAL, label: 'Critical' },
  ]

  if (chartData.length === 0) {
    return (
      <div className="card h-64 flex items-center justify-center">
        <p className="text-gray-500">No anomaly score data available</p>
      </div>
    )
  }

  return (
    <div className="card h-64">
      <div className="card-header flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: CHART_COLORS.anomaly }} />
          Anomaly Score
        </h3>
        <span className="text-sm text-gray-500">0-100</span>
      </div>
      <div className="card-body p-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={CHART_MARGIN}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
            <XAxis
              dataKey="time"
              type="number"
              tickFormatter={(value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
              domain={[0, 100]}
              tickFormatter={(value) => `${value}`}
            />
            <Tooltip
              contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
              labelFormatter={(value) => new Date(value).toLocaleTimeString()}
              formatter={(value, name) => [value.toFixed(1), name]}
            />
            <Legend />
            {severityZones.map((zone, idx) => (
              <Area
                key={idx}
                type="monotone"
                dataKey="anomaly_score"
                stroke="transparent"
                fill={zone.color}
                fillOpacity={0.1}
                points={chartData.map(d => ({ x: d.time, y: zone.y2 }))}
                baseLine={zone.y}
              />
            ))}
            <Line
              type="monotone"
              dataKey="anomaly_score"
              stroke={CHART_COLORS.anomaly}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6 }}
              name="Anomaly Score"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}