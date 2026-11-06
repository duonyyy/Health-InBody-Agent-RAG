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
  const [date, setDate] = useState(() => {
    try {
      return new Date().toISOString().split('T')[0];
    } catch {
      return '2026-10-26';
    }
  });
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
      const smmVal = typeof smm === 'number' ? smm : undefined;
      const bfmVal = typeof bfm === 'number' ? bfm : undefined;
      const pbfVal = typeof pbf === 'number' ? pbf : undefined;
      const vflVal = typeof vfl === 'number' ? vfl : undefined;

      await onSave({
        measured_at: new Date(date).toISOString(),
        height_cm: heightNum,
        weight_kg: weightNum,
        smm_kg: smmVal,
        bfm_kg: bfmVal,
        pbf_percent: pbfVal,
        skeletal_muscle_mass_kg: smmVal,
        body_fat_mass_kg: bfmVal,
        percent_body_fat: pbfVal,
        visceral_fat_level: vflVal,
        bmi: currentBmi,
        bmr_kcal: currentBmr,
        notes: notes.trim(),
        source_type: 'manual_confirmed',
        confirmed_by_user: true,
        source: 'manual',
      });

      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Có lỗi khi lưu lần đo';
      setErrorMsg(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rounded-2xl p-6 border border-slate-200 bg-white shadow-xs">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-teal-50 text-teal-700 flex items-center justify-center border border-teal-200 font-bold">
            <PlusCircle className="w-4 h-4" />
          </div>
          <div>
            <h4 className="font-bold text-sm text-slate-900">Ghi nhận Chỉ số InBody Thủ công</h4>
            <p className="text-xs text-slate-500">Nhập số liệu từ phiếu in hoặc máy đo phòng gym</p>
          </div>
        </div>

        {/* Live calculated BMI Pill */}
        {currentBmi && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-xl bg-slate-50 border border-slate-200 text-xs">
            <Calculator className="w-3.5 h-3.5 text-teal-600" />
            <span className="text-slate-500 font-medium">Tính nhanh BMI:</span>
            <span className="font-bold text-slate-900 font-mono">{currentBmi}</span>
            <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold border ${bmiClassification.badgeClass}`}>
              {bmiClassification.label}
            </span>
          </div>
        )}
      </div>

      {errorMsg && (
        <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center gap-2 font-medium">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {savedSuccess && (
        <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center gap-2 font-medium animate-in fade-in">
          <Check className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>Đã lưu thành công lần đo mới vào hồ sơ InBody!</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3.5">
          {/* Ngày đo */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Ngày đo</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 text-xs focus:bg-white focus:outline-none focus:border-teal-600 font-mono"
              required
            />
          </div>

          {/* Chiều cao */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Chiều cao (cm)</label>
            <input
              type="number"
              step="0.5"
              value={height}
              onChange={(e) => setHeight(Number(e.target.value))}
              placeholder="172"
              className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 text-xs focus:bg-white focus:outline-none focus:border-teal-600 font-mono"
              required
            />
          </div>

          {/* Cân nặng */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Cân nặng (kg) *</label>
            <input
              type="number"
              step="0.1"
              value={weight}
              onChange={(e) => setWeight(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="72.4"
              className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 text-xs focus:bg-white focus:outline-none focus:border-teal-600 font-mono font-bold"
              required
            />
          </div>

          {/* Cơ xương SMM */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Khối lượng Cơ (SMM kg)</label>
            <input
              type="number"
              step="0.1"
              value={smm}
              onChange={(e) => setSmm(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="33.8"
              className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 text-xs focus:bg-white focus:outline-none focus:border-teal-600 font-mono"
            />
          </div>

          {/* Khối lượng Mỡ BFM */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Khối lượng Mỡ (BFM kg)</label>
            <input
              type="number"
              step="0.1"
              value={bfm}
              onChange={(e) => setBfm(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="14.1"
              className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 text-xs focus:bg-white focus:outline-none focus:border-teal-600 font-mono"
            />
          </div>

          {/* Tỷ lệ Mỡ PBF */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Tỷ lệ Mỡ PBF (%)</label>
            <input
              type="number"
              step="0.1"
              value={pbf}
              onChange={(e) => setPbf(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="19.5"
              className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 text-xs focus:bg-white focus:outline-none focus:border-teal-600 font-mono"
            />
          </div>

          {/* Mỡ Nội Tạng VFL */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Mỡ Nội tạng (Level 1-20)</label>
            <input
              type="number"
              step="1"
              value={vfl}
              onChange={(e) => setVfl(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="6"
              className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 text-xs focus:bg-white focus:outline-none focus:border-teal-600 font-mono"
            />
          </div>

          {/* Ghi chú */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Ghi chú phòng tập</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Đo lúc đói buổi sáng..."
              className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 text-xs focus:bg-white focus:outline-none focus:border-teal-600"
            />
          </div>
        </div>

        <div className="flex items-center justify-end pt-2">
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-teal-600 to-emerald-600 hover:brightness-105 text-white font-bold text-xs shadow-sm flex items-center gap-1.5 transition-all"
          >
            <PlusCircle className="w-4 h-4" />
            <span>{isSubmitting ? 'Đang lưu...' : 'Lưu lần đo vào Hồ sơ'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}