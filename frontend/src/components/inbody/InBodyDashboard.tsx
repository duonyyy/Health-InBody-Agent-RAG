'use client';

import React, { useState, useEffect, useCallback } from 'react';
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
  Loader2,
  AlertCircle,
  RotateCw,
} from 'lucide-react';
import { InBodyMeasurement, UserProfile, SexAtBirthType, SexType } from '@/types';
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

interface InBodyDashboardProps {
  onMeasurementChange?: () => void;
  profile?: UserProfile | null;
  sexAtBirth?: SexAtBirthType | SexType | string | null;
}

export default function InBodyDashboard({
  onMeasurementChange,
  profile,
  sexAtBirth,
}: InBodyDashboardProps) {
  const [measurements, setMeasurements] = useState<InBodyMeasurement[]>([]);
  const [subTab, setSubTab] = useState<'overview' | 'manual' | 'ocr' | 'history'>('overview');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await fetchInBodyMeasurements();
      setMeasurements(data);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'Không thể tải danh sách số đo InBody từ máy chủ.';
      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    const fetchInit = async () => {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const data = await fetchInBodyMeasurements();
        if (!ignore) {
          setMeasurements(data);
        }
      } catch (err: unknown) {
        if (!ignore) {
          const message =
            err instanceof Error
              ? err.message
              : 'Không thể tải danh sách số đo InBody từ máy chủ.';
          setErrorMessage(message);
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    };
    fetchInit();
    return () => {
      ignore = true;
    };
  }, []);

  const handleSave = async (meas: Partial<InBodyMeasurement>) => {
    await saveInBodyMeasurement(meas);
    await loadData();
    if (onMeasurementChange) onMeasurementChange();
    setSubTab('overview');
  };

  const handleDelete = async (id: string) => {
    await deleteInBodyMeasurement(id);
    await loadData();
    if (onMeasurementChange) onMeasurementChange();
  };

  // Sắp xếp theo ngày giảm dần
  const sorted = [...measurements].sort(
    (a, b) => new Date(b.measured_at).getTime() - new Date(a.measured_at).getTime()
  );
  const latest = sorted[0];
  const baseline = sorted[sorted.length - 1];

  const hasData = sorted.length > 0;

  const latestSmm = latest?.smm_kg ?? latest?.skeletal_muscle_mass_kg;
  const baselineSmm = baseline?.smm_kg ?? baseline?.skeletal_muscle_mass_kg;

  const latestBfm = latest?.bfm_kg ?? latest?.body_fat_mass_kg;

  const latestPbf = latest?.pbf_percent ?? latest?.percent_body_fat;
  const baselinePbf = baseline?.pbf_percent ?? baseline?.percent_body_fat;

  const effectiveSex = sexAtBirth || profile?.sex_at_birth || profile?.sex || null;

  const hasValidWeightDelta =
    latest?.weight_kg != null &&
    baseline?.weight_kg != null &&
    latest.id !== baseline.id;
  const weightDelta = hasValidWeightDelta
    ? Number((latest.weight_kg! - baseline.weight_kg!).toFixed(1))
    : undefined;

  const hasValidSmmDelta =
    latestSmm != null &&
    baselineSmm != null &&
    latest?.id !== baseline?.id;
  const smmDelta = hasValidSmmDelta
    ? Number((latestSmm! - baselineSmm!).toFixed(1))
    : undefined;

  const hasValidPbfDelta =
    latestPbf != null &&
    baselinePbf != null &&
    latest?.id !== baseline?.id;
  const pbfDelta = hasValidPbfDelta
    ? Number((latestPbf! - baselinePbf!).toFixed(1))
    : undefined;

  const hasValidVflDelta =
    latest?.visceral_fat_level != null &&
    baseline?.visceral_fat_level != null &&
    latest.id !== baseline.id;
  const vflDelta = hasValidVflDelta
    ? latest.visceral_fat_level! - baseline.visceral_fat_level!
    : undefined;

  const bmiClass = latest?.bmi != null ? classifyBmiAsian(latest.bmi) : undefined;
  const pbfClass = latestPbf != null ? classifyPbf(latestPbf, effectiveSex) : undefined;
  const vflClass = latest?.visceral_fat_level != null ? classifyVisceralFat(latest.visceral_fat_level) : undefined;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Error notification banner */}
      {errorMessage && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span className="font-medium">{errorMessage}</span>
          </div>
          <button
            onClick={loadData}
            className="px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold flex items-center gap-1.5 transition-colors shadow-xs"
          >
            <RotateCw className="w-3.5 h-3.5" />
            <span>Thử lại</span>
          </button>
        </div>
      )}

      {/* Loading indicator */}
      {isLoading && (
        <div className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-slate-200 text-xs text-slate-700 w-fit shadow-xs font-medium">
          <Loader2 className="w-4 h-4 animate-spin text-teal-600" />
          <span>Đang đồng bộ số đo InBody từ máy chủ...</span>
        </div>
      )}

      {/* KPI Top Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard
          title="Cân nặng"
          value={latest?.weight_kg != null ? latest.weight_kg : '--'}
          unit={latest?.weight_kg != null ? 'kg' : ''}
          icon={Weight}
          delta={weightDelta}
          deltaUnit="kg"
          subtitle={latest?.weight_kg != null ? 'Lần đo gần nhất' : 'Chưa có số đo'}
        />

        <KpiCard
          title="Chỉ số BMI"
          value={latest?.bmi != null ? latest.bmi : '--'}
          unit={latest?.bmi != null ? 'kg/m²' : ''}
          icon={Activity}
          classification={bmiClass}
          subtitle={latest?.bmi != null ? 'Chuẩn WHO Châu Á' : 'Chưa có số đo'}
        />

        <KpiCard
          title="Tỷ lệ Mỡ (PBF)"
          value={latestPbf != null ? latestPbf : '--'}
          unit={latestPbf != null ? '%' : ''}
          icon={Flame}
          classification={pbfClass}
          delta={pbfDelta}
          deltaUnit="%"
          subtitle={latestPbf != null ? undefined : 'Chưa có số đo'}
        />

        <KpiCard
          title="Cơ xương (SMM)"
          value={latestSmm != null ? latestSmm : '--'}
          unit={latestSmm != null ? 'kg' : ''}
          icon={Dumbbell}
          delta={smmDelta}
          deltaUnit="kg"
          subtitle={latestSmm != null ? 'Khối lượng cơ nạc' : 'Chưa có số đo'}
        />

        <KpiCard
          title="Mỡ Nội Tạng"
          value={latest?.visceral_fat_level != null ? `Cấp ${latest.visceral_fat_level}` : '--'}
          unit=""
          icon={ShieldCheck}
          classification={vflClass}
          delta={vflDelta}
          deltaUnit="cấp"
          subtitle={latest?.visceral_fat_level != null ? undefined : 'Chưa có số đo'}
        />

        <KpiCard
          title="Khối lượng Mỡ"
          value={latestBfm != null ? latestBfm : '--'}
          unit={latestBfm != null ? 'kg' : ''}
          icon={TrendingDown}
          subtitle={latestBfm != null ? 'Khối mỡ cơ thể (BFM)' : 'Chưa có số đo'}
        />
      </div>

      {/* Empty State Banner if no data */}
      {!isLoading && !hasData && !errorMessage && (
        <div className="p-8 rounded-2xl border border-teal-200 bg-white text-center space-y-3 shadow-xs">
          <div className="w-12 h-12 rounded-2xl bg-teal-50 text-teal-700 flex items-center justify-center mx-auto border border-teal-200">
            <Activity className="w-6 h-6" />
          </div>
          <h4 className="text-sm font-bold text-slate-900">Chưa có dữ liệu đo InBody nào trong hồ sơ</h4>
          <p className="text-xs text-slate-600 max-w-md mx-auto leading-relaxed">
            Bạn có thể tải ảnh phiếu đo InBody có sẵn để bóc tách tự động bằng OCR, hoặc nhấn &ldquo;Ghi nhận chỉ số&rdquo; để nhập tay lần đo đầu tiên.
          </p>
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={() => setSubTab('manual')}
              className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold border border-slate-300 transition-colors shadow-xs"
            >
              Ghi nhận thủ công
            </button>
            <button
              onClick={() => setSubTab('ocr')}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-teal-600 to-emerald-600 hover:brightness-105 text-white text-xs font-bold shadow-sm transition-all"
            >
              Quét phiếu InBody (OCR)
            </button>
          </div>
        </div>
      )}

      {/* Sub-Tab Navigation */}
      <div className="flex flex-wrap items-center gap-1.5 p-1 rounded-2xl bg-slate-100 border border-slate-200 text-xs w-fit">
        <button
          onClick={() => setSubTab('overview')}
          className={`px-4 py-2 rounded-xl font-bold flex items-center gap-2 transition-all ${
            subTab === 'overview'
              ? 'bg-white text-teal-900 shadow-xs border border-slate-200/80'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Biểu đồ & Xu hướng</span>
        </button>

        <button
          onClick={() => setSubTab('manual')}
          className={`px-4 py-2 rounded-xl font-bold flex items-center gap-2 transition-all ${
            subTab === 'manual'
              ? 'bg-white text-teal-900 shadow-xs border border-slate-200/80'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <PlusCircle className="w-3.5 h-3.5" />
          <span>Ghi nhận chỉ số</span>
        </button>

        <button
          onClick={() => setSubTab('ocr')}
          className={`px-4 py-2 rounded-xl font-bold flex items-center gap-2 transition-all ${
            subTab === 'ocr'
              ? 'bg-white text-teal-900 shadow-xs border border-slate-200/80'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Quét OCR Phiếu</span>
        </button>

        <button
          onClick={() => setSubTab('history')}
          className={`px-4 py-2 rounded-xl font-bold flex items-center gap-2 transition-all ${
            subTab === 'history'
              ? 'bg-white text-teal-900 shadow-xs border border-slate-200/80'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          <Calendar className="w-3.5 h-3.5" />
          <span>Lịch sử ({measurements.length})</span>
        </button>
      </div>

      {/* Main Tab Content */}
      {subTab === 'overview' && (
        <div className="space-y-6 animate-in fade-in">
          {hasData ? (
            <>
              <ProgressChart measurements={measurements} />
              <MeasurementHistoryTable
                measurements={measurements}
                onDelete={handleDelete}
                sexAtBirth={effectiveSex}
              />
            </>
          ) : (
            <div className="py-12 text-center text-xs text-slate-500 bg-white rounded-2xl border border-slate-200">
              Chưa có dữ liệu lịch sử để vẽ biểu đồ tiến trình Recharts.
            </div>
          )}
        </div>
      )}

      {subTab === 'manual' && (
        <div className="animate-in fade-in">
          <MeasurementForm onSave={handleSave} defaultHeight={latest?.height_cm || 170} />
        </div>
      )}

      {subTab === 'ocr' && (
        <div className="animate-in fade-in">
          <OcrScanner onSaveOcrResult={handleSave} />
        </div>
      )}

      {subTab === 'history' && (
        <div className="animate-in fade-in">
          <MeasurementHistoryTable
            measurements={measurements}
            onDelete={handleDelete}
            sexAtBirth={effectiveSex}
          />
        </div>
      )}
    </div>
  );
}