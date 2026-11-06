'use client';

import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus, LucideIcon } from 'lucide-react';
import { ClassificationResult } from '@/lib/classifiers';

interface KpiCardProps {
  title: string;
  value: number | string;
  unit: string;
  icon: LucideIcon;
  classification?: ClassificationResult;
  delta?: number;
  deltaLabel?: string;
  deltaUnit?: string;
  subtitle?: string;
}

export default function KpiCard({
  title,
  value,
  unit,
  icon: Icon,
  classification,
  delta,
  deltaLabel = 'so với mốc đầu',
  deltaUnit = '',
  subtitle,
}: KpiCardProps) {
  const isPositive = delta !== undefined && delta > 0;
  const isNegative = delta !== undefined && delta < 0;

  return (
    <div className="rounded-2xl p-4 border border-slate-200 bg-white shadow-xs relative overflow-hidden flex flex-col justify-between hover:border-teal-300 hover:shadow-md transition-all">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between gap-2 mb-2">
          <span className="text-xs font-bold text-slate-500 tracking-wide uppercase">{title}</span>
          <div className="w-8 h-8 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-center text-teal-700">
            <Icon className="w-4 h-4" />
          </div>
        </div>

        {/* Main Value */}
        <div className="flex items-baseline gap-1.5 my-1">
          <span className="text-2xl font-black text-slate-900 tracking-tight font-mono">
            {value}
          </span>
          <span className="text-xs font-semibold text-slate-500">{unit}</span>
        </div>

        {/* Classification Badge if present */}
        {classification && (
          <div className="mt-1.5 mb-2">
            <span
              className={`inline-flex items-center text-[10px] px-2 py-0.5 rounded-full font-bold border ${classification.badgeClass}`}
            >
              {classification.label}
            </span>
          </div>
        )}

        {/* Visual Gauge Meter */}
        {classification && classification.progressPercent > 0 && (
          <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden my-2">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${classification.progressPercent}%`,
                backgroundColor: classification.color,
              }}
            />
          </div>
        )}
      </div>

      {/* Footer Delta / Subtitle */}
      <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
        {delta !== undefined ? (
          <div className="flex items-center gap-1 font-semibold">
            {isPositive ? (
              <span className="flex items-center text-emerald-700">
                <ArrowUpRight className="w-3.5 h-3.5" />
                <span>+{delta} {deltaUnit}</span>
              </span>
            ) : isNegative ? (
              <span className="flex items-center text-sky-700">
                <ArrowDownRight className="w-3.5 h-3.5" />
                <span>{delta} {deltaUnit}</span>
              </span>
            ) : (
              <span className="flex items-center text-slate-500">
                <Minus className="w-3.5 h-3.5" />
                <span>0 {deltaUnit}</span>
              </span>
            )}
            <span className="text-slate-400 font-normal">{deltaLabel}</span>
          </div>
        ) : (
          <span className="text-slate-400 font-medium">{subtitle || 'Chỉ số đo tiêu chuẩn'}</span>
        )}
      </div>
    </div>
  );
}