'use client';

import React, { useState, useEffect } from 'react';
import {
  Weight,
  Activity,
  Flame,
  Dumbbell,
  ShieldCheck,
  TrendingDown,
  PlusCircle,
  FileText,
  Calendar,
  Layers,
} from 'lucide-react';
import { InBodyMeasurement } from '@/types';
import KpiCard from './KpiCard';
import ProgressChart from './ProgressChart';
import MeasurementForm from './MeasurementForm';
import MeasurementHistoryTable from './MeasurementHistoryTable';
import OcrScanner from './OcrScanner';
import {
  fetchInBodyMeasurements,
  saveInBodyMeasurement,
  deleteInBodyMeasurement,
} from '@/lib/api';
import { classifyBmiAsian, classifyPbf, classifyVisceralFat } from '@/lib/classifiers';

export default function InBodyDashboard() {
  const [measurements, setMeasurements] = useState<InBodyMeasurement[]>([]);
  const [subTab, setSubTab] = useState<'overview' | 'manual' | 'ocr' | 'history'>('overview');
  const [isLoading, setIsLoading] = useState(true);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const data = await fetchInBodyMeasurements();
      setMeasurements(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSave = async (meas: Partial<InBodyMeasurement>) => {
    await saveInBodyMeasurement(meas);
    await loadData();
    setSubTab('overview');
  };

  const handleDelete = async (id: string) => {
    await deleteInBodyMeasurement(id);
    await loadData();
  };

  // Compute latest & baseline metrics
  const sorted = [...measurements].sort(
    (a, b) => new Date(b.measured_at).getTime() - new Date(a.measured_at).getTime()
  );
  const latest = sorted[0];
  const baseline = sorted[sorted.length - 1];

  const weightDelta =
    latest && baseline && latest.id !== baseline.id
      ? Number((latest.weight_kg - baseline.weight_kg).toFixed(1))
      : undefined;

  const smmDelta =
    latest?.skeletal_muscle_mass_kg && baseline?.skeletal_muscle_mass_kg && latest.id !== baseline.id
      ? Number((latest.skeletal_muscle_mass_kg - baseline.skeletal_muscle_mass_kg).toFixed(1))
      : undefined;

  const pbfDelta =
    latest?.percent_body_fat && baseline?.percent_body_fat && latest.id !== baseline.id
      ? Number((latest.percent_body_fat - baseline.percent_body_fat).toFixed(1))
      : undefined;

  const vflDelta =
    latest?.visceral_fat_level !== undefined &&
    baseline?.visceral_fat_level !== undefined &&
    latest.id !== baseline.id
      ? latest.visceral_fat_level - baseline.visceral_fat_level
      : undefined;

  const bmiClass = latest ? classifyBmiAsian(latest.bmi) : undefined;
  const pbfClass = latest ? classifyPbf(latest.percent_body_fat, 'male') : undefined;
  const vflClass = latest ? classifyVisceralFat(latest.visceral_fat_level) : undefined;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* KPI Top Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard
          title="Cân nặng"
          value={latest?.weight_kg || 72.4}
          unit="kg"
          icon={Weight}
          delta={weightDelta}
          deltaUnit="kg"
          subtitle="Mục tiêu: 70.0 kg"
        />

        <KpiCard
          title="Chỉ số BMI"
          value={latest?.bmi || 24.47}
          unit="kg/m²"
          icon={Activity}
          classification={bmiClass}
          subtitle="Chuẩn WHO Châu Á"
        />

        <KpiCard
          title="Tỷ lệ Mỡ (PBF)"
          value={latest?.percent_body_fat || 19.5}
          unit="%"
          icon={Flame}
          classification={pbfClass}
          delta={pbfDelta}
          deltaUnit="%"
        />

        <KpiCard
          title="Cơ xương (SMM)"
          value={latest?.skeletal_muscle_mass_kg || 33.8}
          unit="kg"
          icon={Dumbbell}
          delta={smmDelta}
          deltaUnit="kg"
          subtitle="Mục tiêu: 34.5 kg"
        />

        <KpiCard
          title="Mỡ Nội Tạng"
          value={`Lvl ${latest?.visceral_fat_level || 6}`}
          unit=""
          icon={ShieldCheck}
          classification={vflClass}
          delta={vflDelta}
          deltaUnit="lvl"
        />

        <KpiCard
          title="Khối lượng Mỡ"
          value={latest?.body_fat_mass_kg || 14.1}
          unit="kg"
          icon={TrendingDown}
          subtitle="Giảm tốt qua các đợt"
        />
      </div>

      {/* Sub-Tab Navigation */}
      <div className="flex items-center gap-1.5 p-1 rounded-2xl bg-slate-950 border border-slate-800 text-xs w-fit">
        <button
          onClick={() => setSubTab('overview')}
          className={`px-4 py-2 rounded-xl font-semibold flex items-center gap-2 transition-all ${
            subTab === 'overview'
              ? 'bg-gradient-to-r from-emerald-500 to-teal-400 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Biểu đồ & Xu hướng</span>
        </button>

        <button
          onClick={() => setSubTab('manual')}
          className={`px-4 py-2 rounded-xl font-semibold flex items-center gap-2 transition-all ${
            subTab === 'manual'
              ? 'bg-gradient-to-r from-emerald-500 to-teal-400 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <PlusCircle className="w-3.5 h-3.5" />
          <span>Ghi nhận chỉ số</span>
        </button>

        <button
          onClick={() => setSubTab('ocr')}
          className={`px-4 py-2 rounded-xl font-semibold flex items-center gap-2 transition-all ${
            subTab === 'ocr'
              ? 'bg-gradient-to-r from-emerald-500 to-teal-400 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Quét OCR Phiếu</span>
        </button>

        <button
          onClick={() => setSubTab('history')}
          className={`px-4 py-2 rounded-xl font-semibold flex items-center gap-2 transition-all ${
            subTab === 'history'
              ? 'bg-gradient-to-r from-emerald-500 to-teal-400 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Calendar className="w-3.5 h-3.5" />
          <span>Lịch sử ({measurements.length})</span>
        </button>
      </div>

      {/* Main Tab Content */}
      {subTab === 'overview' && (
        <div className="space-y-6 animate-in fade-in">
          <ProgressChart measurements={measurements} />
          <MeasurementHistoryTable measurements={measurements} onDelete={handleDelete} />
        </div>
      )}

      {subTab === 'manual' && (
        <div className="animate-in fade-in">
          <MeasurementForm onSave={handleSave} defaultHeight={latest?.height_cm || 172} />
        </div>
      )}

      {subTab === 'ocr' && (
        <div className="animate-in fade-in">
          <OcrScanner onSaveOcrResult={handleSave} />
        </div>
      )}

      {subTab === 'history' && (
        <div className="animate-in fade-in">
          <MeasurementHistoryTable measurements={measurements} onDelete={handleDelete} />
        </div>
      )}
    </div>
  );
}
