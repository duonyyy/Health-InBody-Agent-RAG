'use client';

import React, { useState } from 'react';
import { PlusCircle, Calculator, Check, AlertCircle } from 'lucide-react';
import { InBodyMeasurement } from '@/types';
import { calculateBmi, calculateBmr, classifyBmiAsian } from '@/lib/classifiers';

interface MeasurementFormProps {
  onSave: (meas: Partial<InBodyMeasurement>) => Promise<void>;
  defaultHeight?: number;
}

export default function MeasurementForm({ onSave, defaultHeight = 172 }: MeasurementFormProps) {
  const [date, setDate] = useState('2026-10-26');

  React.useEffect(() => {
    try {
      setDate(new Date().toISOString().split('T')[0]);
    } catch (e) {}
  }, []);
  const [height, setHeight] = useState(defaultHeight);
  const [weight, setWeight] = useState<number | ''>(72.4);
  const [smm, setSmm] = useState<number | ''>(33.8);
  const [bfm, setBfm] = useState<number | ''>(14.1);
  const [pbf, setPbf] = useState<number | ''>(19.5);
  const [vfl, setVfl] = useState<number | ''>(6);
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Live calculations
  const weightNum = typeof weight === 'number' ? weight : 0;
  const heightNum = typeof height === 'number' ? height : 0;
  const currentBmi = calculateBmi(weightNum, heightNum);
  const currentBmr = weightNum > 0 && heightNum > 0 ? calculateBmr(weightNum, heightNum, 27, 'male') : 0;
  const bmiClassification = classifyBmiAsian(currentBmi);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (!weightNum || weightNum <= 0) {
      setErrorMsg('Vui lòng nhập cân nặng hợp lệ (> 0 kg)');
      return;
    }

    setIsSubmitting(true);
    try {
      await onSave({
        measured_at: new Date(date).toISOString(),
        height_cm: heightNum,
        weight_kg: weightNum,
        skeletal_muscle_mass_kg: typeof smm === 'number' ? smm : undefined,
        body_fat_mass_kg: typeof bfm === 'number' ? bfm : undefined,
        percent_body_fat: typeof pbf === 'number' ? pbf : undefined,
        visceral_fat_level: typeof vfl === 'number' ? vfl : undefined,
        bmi: currentBmi,
        bmr_kcal: currentBmr,
        notes: notes.trim(),
        source: 'manual',
      });

      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Có lỗi khi lưu lần đo');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
            <PlusCircle className="w-4 h-4" />
          </div>
          <div>
            <h4 className="font-bold text-sm text-slate-100">Ghi nhận Chỉ số InBody Thủ công</h4>
            <p className="text-xs text-slate-400">Nhập số liệu từ phiếu in hoặc máy đo phòng gym</p>
          </div>
        </div>

        {/* Live calculated BMI Pill */}
        {currentBmi && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-xl bg-slate-950 border border-slate-800 text-xs">
            <Calculator className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-400">Tính nhanh BMI:</span>
            <span className="font-bold text-slate-100 font-mono">{currentBmi}</span>
            <span className={`px-1.5 py-0.2 rounded text-[10px] font-semibold border ${bmiClassification.badgeClass}`}>
              {bmiClassification.label}
            </span>
          </div>
        )}
      </div>

      {errorMsg && (
        <div className="mb-4 p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-200 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {savedSuccess && (
        <div className="mb-4 p-3 rounded-xl bg-emerald-950/60 border border-emerald-800 text-emerald-200 text-xs flex items-center gap-2 animate-in fade-in">
          <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>Đã lưu thành công lần đo mới vào hồ sơ InBody!</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          {/* Ngày đo */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Ngày đo</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-emerald-500 font-mono"
              required
            />
          </div>

          {/* Chiều cao */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Chiều cao (cm)</label>
            <input
              type="number"
              step="0.5"
              value={height}
              onChange={(e) => setHeight(Number(e.target.value))}
              placeholder="172"
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-emerald-500 font-mono"
              required
            />
          </div>

          {/* Cân nặng */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Cân nặng (kg) *</label>
            <input
              type="number"
              step="0.1"
              value={weight}
              onChange={(e) => setWeight(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="72.4"
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-emerald-500 font-mono font-semibold"
              required
            />
          </div>

          {/* Cơ xương SMM */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Khối lượng Cơ (SMM kg)</label>
            <input
              type="number"
              step="0.1"
              value={smm}
              onChange={(e) => setSmm(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="33.8"
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-emerald-500 font-mono"
            />
          </div>

          {/* Khối lượng Mỡ BFM */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Khối lượng Mỡ (BFM kg)</label>
            <input
              type="number"
              step="0.1"
              value={bfm}
              onChange={(e) => setBfm(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="14.1"
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-emerald-500 font-mono"
            />
          </div>

          {/* Tỷ lệ Mỡ PBF */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Tỷ lệ Mỡ PBF (%)</label>
            <input
              type="number"
              step="0.1"
              value={pbf}
              onChange={(e) => setPbf(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="19.5"
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-emerald-500 font-mono"
            />
          </div>

          {/* Mỡ Nội Tạng VFL */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Mỡ Nội tạng (Level 1-20)</label>
            <input
              type="number"
              step="1"
              value={vfl}
              onChange={(e) => setVfl(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="6"
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-emerald-500 font-mono"
            />
          </div>

          {/* Ghi chú */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Ghi chú phòng tập</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Đo lúc đói buổi sáng..."
              className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        <div className="flex items-center justify-end pt-2">
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-400 hover:brightness-110 text-slate-950 font-bold text-xs shadow-md shadow-emerald-500/25 flex items-center gap-1.5 transition-all"
          >
            <PlusCircle className="w-4 h-4" />
            <span>{isSubmitting ? 'Đang lưu...' : 'Lưu lần đo vào Hồ sơ'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
