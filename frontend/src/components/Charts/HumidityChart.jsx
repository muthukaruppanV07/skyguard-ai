import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { CHART_COLORS, CHART_MARGIN, formatChartData } from '../../charts/chartUtils'

export function HumidityChart({ data, anomalies = [] }) {
  const chartData = formatChartData(data, 'humidity')

  if (chartData.length === 0) {
    return (
      <div className="card h-64 flex items-center justify-center">
        <p className="text-gray-500">No humidity data available</p>
      </div>
    )
  }

  return (
    <div className="card h-64">
      <div className="card-header flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: CHART_COLORS.humidity }} />
          Humidity
        </h3>
        <span className="text-sm text-gray-500">%</span>
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
              tickFormatter={(value) => `${value}%`}
            />
            <Tooltip
              contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
              labelFormatter={(value) => new Date(value).toLocaleTimeString()}
              formatter={(value) => [value.toFixed(1), 'Humidity']}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="humidity"
              stroke={CHART_COLORS.humidity}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6 }}
              name="Humidity"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}