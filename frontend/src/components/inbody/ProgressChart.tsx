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
import { Activity } from 'lucide-react';

interface ProgressChartProps {
  measurements: InBodyMeasurement[];
}

type ChartMode = 'composition' | 'fat' | 'visceral';

interface TooltipEntry {
  color?: string;
  name?: string;
  value?: number | string;
  unit?: string;
  payload?: {
    fullDate?: string;
  };
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    return (
      <div className="p-3.5 rounded-xl border border-slate-200 bg-white text-xs shadow-xl space-y-1.5">
        <div className="font-bold text-slate-800 pb-1 border-b border-slate-100">
          Ngày: {payload[0]?.payload?.fullDate || label}
        </div>
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-slate-600">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span>{entry.name}:</span>
            </span>
            <span className="font-bold text-slate-900 font-mono">
              {entry.value} {entry.unit || ''}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return null;
}

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
        smm: m.smm_kg ?? m.skeletal_muscle_mass_kg,
        pbf: m.pbf_percent ?? m.percent_body_fat,
        bfm: m.bfm_kg ?? m.body_fat_mass_kg,
        visceral: m.visceral_fat_level,
        bmi: m.bmi,
      };
    });

  return (
    <div className="rounded-2xl p-6 border border-slate-200 bg-white shadow-xs">
      {/* Chart Header & Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
        <div>
          <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <Activity className="w-4 h-4 text-teal-600" />
            <span>Biểu đồ Tiến trình Thể trạng</span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Theo dõi xu hướng tái tạo thể trạng (Body Recomposition) qua các mốc đo
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center p-1 rounded-xl bg-slate-100 border border-slate-200 text-xs">
          <button
            onClick={() => setMode('composition')}
            className={`px-3 py-1.5 rounded-lg font-bold transition-all ${
              mode === 'composition'
                ? 'bg-white text-teal-900 shadow-xs border border-slate-200/80'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Cân nặng & Cơ
          </button>
          <button
            onClick={() => setMode('fat')}
            className={`px-3 py-1.5 rounded-lg font-bold transition-all ${
              mode === 'fat'
                ? 'bg-white text-teal-900 shadow-xs border border-slate-200/80'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Mỡ & % Mỡ (PBF)
          </button>
          <button
            onClick={() => setMode('visceral')}
            className={`px-3 py-1.5 rounded-lg font-bold transition-all ${
              mode === 'visceral'
                ? 'bg-white text-teal-900 shadow-xs border border-slate-200/80'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Mỡ Nội tạng
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="h-72 w-full">
        {chartData.length === 0 ? (
          <div className="h-full flex items-center justify-center text-xs text-slate-400">
            Chưa có đủ dữ liệu để vẽ biểu đồ
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            {mode === 'composition' ? (
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="weightGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0284c7" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#0284c7" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="smmGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0d9488" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#0d9488" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
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
                  stroke="#0284c7"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#weightGrad)"
                  unit="kg"
                />
                <Area
                  type="monotone"
                  dataKey="smm"
                  name="Cơ xương SMM (kg)"
                  stroke="#0d9488"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#smmGrad)"
                  unit="kg"
                />
              </AreaChart>
            ) : mode === 'fat' ? (
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
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
                  stroke="#d97706"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#d97706' }}
                  unit="%"
                />
                <Line
                  type="monotone"
                  dataKey="bfm"
                  name="Khối lượng mỡ (kg)"
                  stroke="#db2777"
                  strokeWidth={2}
                  dot={{ r: 4, fill: '#db2777' }}
                  unit="kg"
                />
              </LineChart>
            ) : (
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} domain={[0, 15]} />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
                  iconType="circle"
                />
                <ReferenceLine
                  y={9}
                  stroke="#e11d48"
                  strokeDasharray="4 4"
                  label={{
                    value: 'Ngưỡng an toàn (Cấp 9)',
                    fill: '#e11d48',
                    fontSize: 10,
                    position: 'top',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="visceral"
                  name="Mỡ nội tạng (VFL)"
                  stroke="#7c3aed"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#7c3aed' }}
                  unit="Cấp"
                />
              </LineChart>
            )}
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}