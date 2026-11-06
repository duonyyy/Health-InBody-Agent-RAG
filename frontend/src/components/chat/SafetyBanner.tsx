'use client';

import React from 'react';
import { AlertTriangle, AlertCircle, PhoneCall, ShieldAlert } from 'lucide-react';
import { SafetyResult } from '@/types';

interface SafetyBannerProps {
  safety: SafetyResult;
}

export default function SafetyBanner({ safety }: SafetyBannerProps) {
  if (!safety || (!safety.is_urgent && !safety.is_caution && safety.risk_level === 'none')) {
    return null;
  }

  const isUrgent = safety.is_urgent || safety.risk_level === 'urgent';

  if (isUrgent) {
    return (
      <div className="mb-4 p-4 rounded-2xl bg-rose-50 border-2 border-rose-400 text-rose-950 shadow-sm animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-rose-600 flex items-center justify-center flex-shrink-0 text-white shadow-md animate-pulse">
            <AlertTriangle className="w-6 h-6 stroke-[2.5]" />
          </div>

          <div className="flex-1">
            <div className="flex items-center justify-between gap-2">
              <h4 className="font-bold text-rose-900 text-sm tracking-wide uppercase flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-rose-600" />
                <span>Cảnh báo An toàn Y tế Khẩn cấp</span>
              </h4>
              {safety.emergency_hotline && (
                <a
                  href={`tel:${safety.emergency_hotline}`}
                  className="inline-flex items-center gap-1 text-xs px-3 py-1 rounded-full bg-rose-600 hover:bg-rose-700 text-white font-bold transition-transform active:scale-95 shadow-sm"
                >
                  <PhoneCall className="w-3.5 h-3.5" />
                  <span>Gọi Cấp cứu {safety.emergency_hotline}</span>
                </a>
              )}
            </div>

            <p className="text-xs text-rose-900/90 mt-1.5 leading-relaxed font-medium">
              {safety.reason ||
                'Hệ thống phát hiện dấu hiệu bất thường cấp tính. Vui lòng dừng mọi hoạt động gắng sức ngay lập tức và liên hệ cơ sở y tế gần nhất.'}
            </p>

            {safety.recommended_action && (
              <div className="mt-2.5 px-3 py-2 rounded-xl bg-rose-100 border border-rose-300 text-xs text-rose-900 font-semibold flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-rose-600 animate-ping" />
                <span>Hành động cần làm: {safety.recommended_action}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Caution banner
  return (
    <div className="mb-4 p-3.5 rounded-2xl bg-amber-50 border border-amber-300 text-amber-950 shadow-xs">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center flex-shrink-0 border border-amber-300">
          <AlertCircle className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <h4 className="font-bold text-amber-900 text-xs uppercase tracking-wide">
            Lưu ý Thận trọng Y khoa
          </h4>
          <p className="text-xs text-amber-900/90 mt-1 leading-relaxed">
            {safety.reason || safety.disclaimer || 'Vui lòng tham khảo ý kiến bác sĩ chuyên khoa trước khi áp dụng bất kỳ phác đồ dinh dưỡng hoặc bài tập nào.'}
          </p>
        </div>
      </div>
    </div>
  );
}