'use client';

import React, { useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from 'recharts';
import { InBodyMeasurement } from '@/types';
import { Activity, TrendingDown, ShieldCheck } from 'lucide-react';

interface ProgressChartProps {
  measurements: InBodyMeasurement[];
}

type ChartMode = 'composition' | 'fat' | 'visceral' | 'all';

export default function ProgressChart({ measurements }: ProgressChartProps) {
  const [mode, setMode] = useState<ChartMode>('composition');

  // Format and sort chronological
  const chartData = [...measurements]
    .sort((a, b) => new Date(a.measured_at).getTime() - new Date(b.measured_at).getTime())
    .map((m) => {
      const d = new Date(m.measured_at);
      const label = `${d.getDate()}/${d.getMonth() + 1}`;
      return {
        date: label,
        fullDate: d.toLocaleDateString('vi-VN'),
        weight: m.weight_kg,
        smm: m.skeletal_muscle_mass_kg,
        pbf: m.percent_body_fat,
        bfm: m.body_fat_mass_kg,
        visceral: m.visceral_fat_level,
        bmi: m.bmi,
      };
    });

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass-panel p-3 rounded-xl border border-slate-700 bg-slate-900/95 text-xs shadow-2xl space-y-1.5">
          <div className="font-semibold text-slate-300 pb-1 border-b border-slate-800">
            Ngày: {payload[0]?.payload?.fullDate || label}
          </div>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center justify-between gap-4">
              <span className="flex items-center gap-1.5 text-slate-400">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: entry.color }}
                />
                <span>{entry.name}:</span>
              </span>
              <span className="font-bold text-slate-100 font-mono">
                {entry.value} {entry.unit || ''}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg">
      {/* Chart Header & Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
        <div>
          <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            <span>Biểu đồ Tiến trình Thể trạng (Recharts Timeline)</span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Theo dõi xu hướng tái tạo thể trạng (Body Recomposition) qua các mốc đo
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center p-1 rounded-xl bg-slate-950 border border-slate-800 text-xs">
          <button
            onClick={() => setMode('composition')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
              mode === 'composition'
                ? 'bg-emerald-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Cân nặng & Cơ
          </button>
          <button
            onClick={() => setMode('fat')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
              mode === 'fat'
                ? 'bg-emerald-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Mỡ & % Mỡ (PBF)
          </button>
          <button
            onClick={() => setMode('visceral')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
              mode === 'visceral'
                ? 'bg-emerald-500 text-slate-950 font-bold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Mỡ Nội tạng
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="h-72 w-full">
        {chartData.length === 0 ? (
          <div className="h-full flex items-center justify-center text-xs text-slate-500">
            Chưa có đủ dữ liệu để vẽ biểu đồ
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            {mode === 'composition' ? (
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="weightGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="smmGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis dataKey="date" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} domain={['dataMin - 2', 'dataMax + 2']} />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
                  iconType="circle"
                />
                <Area
                  type="monotone"
                  dataKey="weight"
                  name="Cân nặng (kg)"
                  stroke="#38bdf8"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#weightGrad)"
                  unit="kg"
                />
                <Area
                  type="monotone"
                  dataKey="smm"
                  name="Cơ xương SMM (kg)"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#smmGrad)"
                  unit="kg"
                />
              </AreaChart>
            ) : mode === 'fat' ? (
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis dataKey="date" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} domain={['dataMin - 2', 'dataMax + 2']} />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
                  iconType="circle"
                />
                <Line
                  type="monotone"
                  dataKey="pbf"
                  name="Tỷ lệ mỡ PBF (%)"
                  stroke="#f59e0b"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#f59e0b' }}
                  unit="%"
                />
                <Line
                  type="monotone"
                  dataKey="bfm"
                  name="Khối lượng mỡ (kg)"
                  stroke="#ec4899"
                  strokeWidth={2}
                  dot={{ r: 4, fill: '#ec4899' }}
                  unit="kg"
                />
              </LineChart>
            ) : (
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis dataKey="date" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} domain={[0, 15]} />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
                  iconType="circle"
                />
                <ReferenceLine
                  y={9}
                  stroke="#ef4444"
                  strokeDasharray="4 4"
                  label={{
                    value: 'Ngưỡng an toàn (Level 9)',
                    fill: '#f87171',
                    fontSize: 10,
                    position: 'top',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="visceral"
                  name="Mỡ nội tạng (VFL)"
                  stroke="#a855f7"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#a855f7' }}
                  unit="Level"
                />
              </LineChart>
            )}
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
