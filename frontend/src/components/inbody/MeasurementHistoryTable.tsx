'use client';

import React, { useState } from 'react';
import { InBodyMeasurement } from '@/types';
import { Trash2, Calendar, FileText, Smartphone, HardDrive, X } from 'lucide-react';
import { classifyBmiAsian, classifyPbf, classifyVisceralFat } from '@/lib/classifiers';

interface MeasurementHistoryTableProps {
  measurements: InBodyMeasurement[];
  onDelete: (id: string) => Promise<void>;
}

export default function MeasurementHistoryTable({
  measurements,
  onDelete,
}: MeasurementHistoryTableProps) {
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const sorted = [...measurements].sort(
    (a, b) => new Date(b.measured_at).getTime() - new Date(a.measured_at).getTime()
  );

  const handleDelete = async (id: string) => {
    setIsDeleting(true);
    try {
      await onDelete(id);
      setDeleteConfirmId(null);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDeleting(false);
    }
  };

  const getSourceIcon = (source?: string) => {
    switch (source) {
      case 'ocr':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
            <FileText className="w-3 h-3" />
            <span>Quét OCR</span>
          </span>
        );
      case 'device':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
            <Smartphone className="w-3 h-3" />
            <span>Máy InBody</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
            <HardDrive className="w-3 h-3" />
            <span>Thủ công</span>
          </span>
        );
    }
  };

  return (
    <div className="glass-card rounded-2xl p-5 border border-slate-800/80 bg-slate-900/60 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="font-bold text-sm text-slate-100 flex items-center gap-2">
            <Calendar className="w-4 h-4 text-emerald-400" />
            <span>Lịch sử Đo đạc InBody ({measurements.length} lần đo)</span>
          </h4>
          <p className="text-xs text-slate-400 mt-0.5">
            Dữ liệu được bảo mật và liên kết trực tiếp với hồ sơ người dùng
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 font-semibold bg-slate-950/40">
              <th className="py-2.5 px-3">Ngày đo</th>
              <th className="py-2.5 px-3">Cân nặng</th>
              <th className="py-2.5 px-3">BMI (WHO Á)</th>
              <th className="py-2.5 px-3">Cơ xương (SMM)</th>
              <th className="py-2.5 px-3">Tỷ lệ Mỡ (PBF)</th>
              <th className="py-2.5 px-3">Mỡ nội tạng</th>
              <th className="py-2.5 px-3">Nguồn</th>
              <th className="py-2.5 px-3 text-right">Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {sorted.map((m) => {
              const d = new Date(m.measured_at);
              const dateStr = d.toLocaleDateString('vi-VN', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
              });

              const bmiClass = classifyBmiAsian(m.bmi);
              const pbfClass = classifyPbf(m.percent_body_fat, 'male');
              const vflClass = classifyVisceralFat(m.visceral_fat_level);

              const isConfirming = deleteConfirmId === m.id;

              return (
                <tr key={m.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3 px-3 font-medium text-slate-200 whitespace-nowrap">
                    <div>{dateStr}</div>
                    {m.notes && <div className="text-[10px] text-slate-500 truncate max-w-[120px]">{m.notes}</div>}
                  </td>
                  <td className="py-3 px-3 font-bold text-slate-100 font-mono">
                    {m.weight_kg} kg
                  </td>
                  <td className="py-3 px-3">
                    {m.bmi ? (
                      <div className="flex flex-col gap-0.5">
                        <span className="font-mono font-semibold text-slate-200">{m.bmi}</span>
                        <span className={`text-[10px] px-1.5 py-0.2 rounded border w-fit ${bmiClass.badgeClass}`}>
                          {bmiClass.label}
                        </span>
                      </div>
                    ) : (
                      <span className="text-slate-500">-</span>
                    )}
                  </td>
                  <td className="py-3 px-3 font-mono font-semibold text-emerald-400">
                    {m.skeletal_muscle_mass_kg ? `${m.skeletal_muscle_mass_kg} kg` : '-'}
                  </td>
                  <td className="py-3 px-3">
                    {m.percent_body_fat ? (
                      <div className="flex flex-col gap-0.5">
                        <span className="font-mono font-semibold text-amber-400">{m.percent_body_fat}%</span>
                        <span className={`text-[10px] px-1.5 py-0.2 rounded border w-fit ${pbfClass.badgeClass}`}>
                          {pbfClass.label}
                        </span>
                      </div>
                    ) : (
                      <span className="text-slate-500">-</span>
                    )}
                  </td>
                  <td className="py-3 px-3">
                    {m.visceral_fat_level ? (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold border ${vflClass.badgeClass}`}>
                        Level {m.visceral_fat_level}
                      </span>
                    ) : (
                      <span className="text-slate-500">-</span>
                    )}
                  </td>
                  <td className="py-3 px-3 whitespace-nowrap">
                    {getSourceIcon(m.source)}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {isConfirming ? (
                      <div className="flex items-center justify-end gap-1.5 animate-in fade-in">
                        <button
                          onClick={() => handleDelete(m.id)}
                          disabled={isDeleting}
                          className="px-2 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-[11px] font-semibold"
                        >
                          Xác nhận
                        </button>
                        <button
                          onClick={() => setDeleteConfirmId(null)}
                          className="p-1 rounded-lg bg-slate-800 text-slate-400 hover:text-slate-200"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteConfirmId(m.id)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition-colors"
                        title="Xóa lần đo này"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
