import { Thermometer, Droplets, Wind, Eye, CloudRain } from 'lucide-react';
import { AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import PageContainer from '../components/ui/PageContainer';
import Card from '../components/ui/Card';
import { currentWeather, forecast } from '../data/mock';
import { chartColors } from '../design/tokens';

const weatherMetrics = [
  { icon: Thermometer, label: 'Temperature', value: `${currentWeather.temperature}°C`, color: '#E8A44C' },
  { icon: Droplets, label: 'Humidity', value: `${currentWeather.humidity}%`, color: '#4EA8A6' },
  { icon: Wind, label: 'Wind Speed', value: `${currentWeather.windSpeed} km/h`, color: '#9BA3B0' },
  { icon: Eye, label: 'Visibility', value: `${currentWeather.visibility} km`, color: '#D4C24E' },
  { icon: CloudRain, label: 'Precipitation', value: `${currentWeather.precipitation} mm`, color: '#4EA8A6' },
];

export default function Weather() {
  return (
    <PageContainer className="flex flex-col gap-6">
      <Card>
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-[22px] font-semibold tracking-[-0.02em] text-[#F4F5F7]">Current Conditions</h2>
            <p className="text-[13px] text-[#5E6A7A] mt-1">{currentWeather.condition} · Los Angeles Metro Area</p>
          </div>
        </div>
        <div className="grid grid-cols-5 gap-4">
          {weatherMetrics.map((m) => (
            <div key={m.label} className="bg-[#111820] rounded-xl p-4 border border-[#1E2A3A]">
              <div className="flex items-center gap-2 mb-3">
                <m.icon size={16} style={{ color: m.color }} />
                <span className="text-[11px] font-medium text-[#5E6A7A] tracking-[0.01em] uppercase">{m.label}</span>
              </div>
              <span className="text-[22px] font-bold tracking-[-0.02em] text-[#F4F5F7]">{m.value}</span>
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-[#F4F5F7] mb-4">Weather Impact on Risk Score</h2>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={forecast}>
            <defs>
              <linearGradient id="riskImpactGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={chartColors.critical} stopOpacity={0.3} />
                <stop offset="100%" stopColor={chartColors.critical} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
            <XAxis dataKey="time" tick={{ fill: chartColors.text, fontSize: 11 }} axisLine={false} tickLine={false} interval={3} />
            <YAxis domain={[0, 100]} tick={{ fill: chartColors.text, fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ backgroundColor: '#1A2230', border: '1px solid #1E2A3A', borderRadius: '8px', fontSize: '13px' }} />
            <Area type="monotone" dataKey="riskImpact" stroke={chartColors.critical} fill="url(#riskImpactGrad)" strokeWidth={2} dot={false} name="Risk Impact" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>
      <Card>
        <h2 className="text-[15px] font-semibold tracking-[-0.02em] text-[#F4F5F7] mb-4">48h Forecast Timeline</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={forecast}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
            <XAxis dataKey="time" tick={{ fill: chartColors.text, fontSize: 11 }} axisLine={false} tickLine={false} interval={3} />
            <YAxis yAxisId="temp" tick={{ fill: chartColors.text, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis yAxisId="precip" orientation="right" tick={{ fill: chartColors.text, fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ backgroundColor: '#1A2230', border: '1px solid #1E2A3A', borderRadius: '8px', fontSize: '13px' }} />
            <Line yAxisId="temp" type="monotone" dataKey="temp" stroke={chartColors.high} strokeWidth={2} dot={false} name="Temp (°C)" />
            <Line yAxisId="precip" type="monotone" dataKey="precipitation" stroke={chartColors.secondary} strokeWidth={2} dot={false} name="Precip (mm)" />
            <Line yAxisId="temp" type="monotone" dataKey="windSpeed" stroke={chartColors.muted} strokeWidth={1.5} dot={false} name="Wind (km/h)" strokeDasharray="4 4" />
          </LineChart>
        </ResponsiveContainer>
      </Card>
    </PageContainer>
  );
}