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

  const getSourceIcon = (sourceType?: string, source?: string) => {
    if (sourceType === 'ocr_confirmed' || source === 'ocr') {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 font-medium">
          <FileText className="w-3 h-3" />
          <span>Quét OCR</span>
        </span>
      );
    }
    if (sourceType === 'device_imported' || source === 'device') {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
          <Smartphone className="w-3 h-3" />
          <span>Máy InBody</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 font-medium">
        <HardDrive className="w-3 h-3" />
        <span>Thủ công</span>
      </span>
    );
  };

  return (
    <div className="rounded-2xl p-6 border border-slate-200 bg-white shadow-xs">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="font-bold text-sm text-slate-900 flex items-center gap-2">
            <Calendar className="w-4 h-4 text-teal-600" />
            <span>Lịch sử Đo đạc InBody ({measurements.length} lần đo)</span>
          </h4>
          <p className="text-xs text-slate-500 mt-0.5">
            Dữ liệu được bảo mật và liên kết trực tiếp với hồ sơ người dùng
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-200 text-slate-600 font-semibold bg-slate-50">
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
          <tbody className="divide-y divide-slate-100">
            {sorted.map((m) => {
              const d = new Date(m.measured_at);
              const dateStr = d.toLocaleDateString('vi-VN', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
              });

              const smmVal = m.smm_kg ?? m.skeletal_muscle_mass_kg;
              const pbfVal = m.pbf_percent ?? m.percent_body_fat;

              const bmiClass = classifyBmiAsian(m.bmi);
              const pbfClass = classifyPbf(pbfVal, 'male');
              const vflClass = classifyVisceralFat(m.visceral_fat_level);

              const isConfirming = deleteConfirmId === m.id;

              return (
                <tr key={m.id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3 px-3 font-semibold text-slate-800 whitespace-nowrap">
                    <div>{dateStr}</div>
                    {m.notes && <div className="text-[10px] text-slate-400 font-normal truncate max-w-[120px]">{m.notes}</div>}
                  </td>
                  <td className="py-3 px-3 font-bold text-slate-900 font-mono">
                    {m.weight_kg} kg
                  </td>
                  <td className="py-3 px-3">
                    {m.bmi ? (
                      <div className="flex flex-col gap-0.5">
                        <span className="font-mono font-bold text-slate-800">{m.bmi}</span>
                        <span className={`text-[10px] px-1.5 py-0.2 rounded border w-fit font-bold ${bmiClass.badgeClass}`}>
                          {bmiClass.label}
                        </span>
                      </div>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </td>
                  <td className="py-3 px-3 font-mono font-bold text-teal-700">
                    {smmVal ? `${smmVal} kg` : '-'}
                  </td>
                  <td className="py-3 px-3">
                    {pbfVal ? (
                      <div className="flex flex-col gap-0.5">
                        <span className="font-mono font-bold text-amber-700">{pbfVal}%</span>
                        <span className={`text-[10px] px-1.5 py-0.2 rounded border w-fit font-bold ${pbfClass.badgeClass}`}>
                          {pbfClass.label}
                        </span>
                      </div>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </td>
                  <td className="py-3 px-3">
                    {m.visceral_fat_level ? (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold border ${vflClass.badgeClass}`}>
                        Cấp {m.visceral_fat_level}
                      </span>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </td>
                  <td className="py-3 px-3 whitespace-nowrap">
                    {getSourceIcon(m.source_type, m.source)}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {isConfirming ? (
                      <div className="flex items-center justify-end gap-1.5 animate-in fade-in">
                        <button
                          onClick={() => handleDelete(m.id)}
                          disabled={isDeleting}
                          className="px-2 py-1 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-[11px] font-bold shadow-xs"
                        >
                          Xác nhận
                        </button>
                        <button
                          onClick={() => setDeleteConfirmId(null)}
                          className="p-1 rounded-lg bg-slate-100 text-slate-500 hover:text-slate-800"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteConfirmId(m.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
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