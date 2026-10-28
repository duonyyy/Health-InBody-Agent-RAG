import { SexType } from '@/types';

export interface ClassificationResult {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  badgeClass: string;
  progressPercent: number; // 0-100 for gauge visualization
  status: 'safe' | 'normal' | 'warning' | 'danger' | 'unknown';
}

/**
 * Phân loại chỉ số BMI theo chuẩn WHO Châu Á (WPRO)
 */
export function classifyBmiAsian(bmi?: number | null): ClassificationResult {
  if (bmi === undefined || bmi === null || bmi <= 0) {
    return {
      label: 'Chưa có số đo',
      color: '#64748b',
      bgColor: '#f1f5f9',
      borderColor: '#cbd5e1',
      badgeClass: 'bg-slate-100 text-slate-600 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
      progressPercent: 0,
      status: 'unknown',
    };
  }

  // WPRO scale: <18.5 (Underweight), 18.5-22.9 (Normal), 23-24.9 (Overweight), >=25 (Obese)
  if (bmi < 18.5) {
    return {
      label: 'Thiếu cân (< 18.5)',
      color: '#3b82f6',
      bgColor: '#eff6ff',
      borderColor: '#93c5fd',
      badgeClass: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800',
      progressPercent: Math.min(100, Math.max(10, (bmi / 18.5) * 35)),
      status: 'warning',
    };
  } else if (bmi <= 22.9) {
    return {
      label: 'Chuẩn bình thường (18.5 - 22.9)',
      color: '#10b981',
      bgColor: '#ecfdf5',
      borderColor: '#6ee7b7',
      badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800',
      progressPercent: 35 + ((bmi - 18.5) / (22.9 - 18.5)) * 30, // 35% - 65%
      status: 'safe',
    };
  } else if (bmi <= 24.9) {
    return {
      label: 'Tiền béo phì (23.0 - 24.9)',
      color: '#f59e0b',
      bgColor: '#fffbeb',
      borderColor: '#fcd34d',
      badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800',
      progressPercent: 65 + ((bmi - 23.0) / (24.9 - 23.0)) * 18, // 65% - 83%
      status: 'warning',
    };
  } else {
    return {
      label: 'Béo phì (≥ 25.0)',
      color: '#ef4444',
      bgColor: '#fef2f2',
      borderColor: '#fca5a5',
      badgeClass: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800',
      progressPercent: Math.min(100, 83 + ((bmi - 25.0) / 10) * 17),
      status: 'danger',
    };
  }
}

/**
 * Phân loại cấp độ mỡ nội tạng (Visceral Fat Level)
 */
export function classifyVisceralFat(level?: number | null): ClassificationResult {
  if (level === undefined || level === null || level < 0) {
    return {
      label: 'Chưa có số đo',
      color: '#64748b',
      bgColor: '#f1f5f9',
      borderColor: '#cbd5e1',
      badgeClass: 'bg-slate-100 text-slate-600 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
      progressPercent: 0,
      status: 'unknown',
    };
  }

  if (level <= 9) {
    return {
      label: `Mức an toàn (${level}/9)`,
      color: '#10b981',
      bgColor: '#ecfdf5',
      borderColor: '#6ee7b7',
      badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800',
      progressPercent: (level / 9) * 45,
      status: 'safe',
    };
  } else if (level <= 14) {
    return {
      label: `Cảnh báo mỡ cao (Level ${level})`,
      color: '#f59e0b',
      bgColor: '#fffbeb',
      borderColor: '#fcd34d',
      badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800',
      progressPercent: 45 + ((level - 9) / 5) * 35,
      status: 'warning',
    };
  } else {
    return {
      label: `Nguy cơ cao (Level ${level} ≥ 15)`,
      color: '#ef4444',
      bgColor: '#fef2f2',
      borderColor: '#fca5a5',
      badgeClass: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800',
      progressPercent: Math.min(100, 80 + ((level - 14) / 10) * 20),
      status: 'danger',
    };
  }
}

/**
 * Phân loại tỷ lệ mỡ cơ thể (PBF) theo giới tính
 */
export function classifyPbf(pbf?: number | null, sex: SexType = 'male'): ClassificationResult {
  if (pbf === undefined || pbf === null || pbf <= 0) {
    return {
      label: 'Chưa có số đo',
      color: '#64748b',
      bgColor: '#f1f5f9',
      borderColor: '#cbd5e1',
      badgeClass: 'bg-slate-100 text-slate-600 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
      progressPercent: 0,
      status: 'unknown',
    };
  }

  const isFemale = (sex || '').toLowerCase() === 'female';

  if (isFemale) {
    if (pbf < 18.0) {
      return {
        label: 'Mỡ rất thấp (< 18%)',
        color: '#3b82f6',
        bgColor: '#eff6ff',
        borderColor: '#93c5fd',
        badgeClass: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800',
        progressPercent: (pbf / 18) * 30,
        status: 'warning',
      };
    } else if (pbf <= 28.0) {
      return {
        label: 'Lý tưởng (18 - 28%)',
        color: '#10b981',
        bgColor: '#ecfdf5',
        borderColor: '#6ee7b7',
        badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800',
        progressPercent: 30 + ((pbf - 18) / 10) * 35,
        status: 'safe',
      };
    } else if (pbf <= 32.0) {
      return {
        label: 'Mức trung bình (28 - 32%)',
        color: '#f59e0b',
        bgColor: '#fffbeb',
        borderColor: '#fcd34d',
        badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800',
        progressPercent: 65 + ((pbf - 28) / 4) * 18,
        status: 'warning',
      };
    } else {
      return {
        label: 'Tỷ lệ mỡ cao (> 32%)',
        color: '#ef4444',
        bgColor: '#fef2f2',
        borderColor: '#fca5a5',
        badgeClass: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800',
        progressPercent: Math.min(100, 83 + ((pbf - 32) / 15) * 17),
        status: 'danger',
      };
    }
  } else {
    // Nam
    if (pbf < 10.0) {
      return {
        label: 'Mỡ rất thấp (< 10%)',
        color: '#3b82f6',
        bgColor: '#eff6ff',
        borderColor: '#93c5fd',
        badgeClass: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800',
        progressPercent: (pbf / 10) * 30,
        status: 'warning',
      };
    } else if (pbf <= 20.0) {
      return {
        label: 'Lý tưởng (10 - 20%)',
        color: '#10b981',
        bgColor: '#ecfdf5',
        borderColor: '#6ee7b7',
        badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800',
        progressPercent: 30 + ((pbf - 10) / 10) * 35,
        status: 'safe',
      };
    } else if (pbf <= 25.0) {
      return {
        label: 'Mức trung bình (20 - 25%)',
        color: '#f59e0b',
        bgColor: '#fffbeb',
        borderColor: '#fcd34d',
        badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800',
        progressPercent: 65 + ((pbf - 20) / 5) * 18,
        status: 'warning',
      };
    } else {
      return {
        label: 'Tỷ lệ mỡ cao (> 25%)',
        color: '#ef4444',
        bgColor: '#fef2f2',
        borderColor: '#fca5a5',
        badgeClass: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800',
        progressPercent: Math.min(100, 83 + ((pbf - 25) / 15) * 17),
        status: 'danger',
      };
    }
  }
}

/**
 * Tính toán nhanh chỉ số BMI từ cân nặng và chiều cao
 */
export function calculateBmi(weightKg?: number, heightCm?: number): number | undefined {
  if (!weightKg || !heightCm || heightCm <= 0) return undefined;
  const heightM = heightCm / 100;
  return Number((weightKg / (heightM * heightM)).toFixed(1));
}

/**
 * Tính ước tính BMR theo công thức Mifflin-St Jeor
 */
export function calculateBmr(weightKg: number, heightCm: number, age: number, sex: SexType = 'male'): number {
  if (sex === 'male') {
    return Math.round(10 * weightKg + 6.25 * heightCm - 5 * age + 5);
  } else {
    return Math.round(10 * weightKg + 6.25 * heightCm - 5 * age - 161);
  }
}
