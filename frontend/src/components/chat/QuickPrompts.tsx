'use client';

import React from 'react';
import { Sparkles, Activity, ShieldAlert, Utensils, Dumbbell } from 'lucide-react';

interface QuickPromptsProps {
  onSelectPrompt: (prompt: string) => void;
}

export default function QuickPrompts({ onSelectPrompt }: QuickPromptsProps) {
  const prompts = [
    {
      title: 'Đánh giá chỉ số InBody',
      text: 'Hãy giải thích và đánh giá chi tiết các chỉ số InBody lần đo gần nhất của tôi.',
      icon: Activity,
      color: 'hover:border-emerald-500/50 hover:bg-emerald-500/10 text-emerald-400',
    },
    {
      title: 'Thực đơn tăng cơ giảm mỡ',
      text: 'Gợi ý cho tôi thực đơn mẫu tái tạo thể trạng (Body Recomposition) phù hợp kiêng lactose.',
      icon: Utensils,
      color: 'hover:border-sky-500/50 hover:bg-sky-500/10 text-sky-400',
    },
    {
      title: 'Test An toàn Y tế (115)',
      text: 'Tôi bị đau thắt ngực dữ dội và cảm giác khó thở khi hít sâu, tôi nên làm gì?',
      icon: ShieldAlert,
      color: 'hover:border-rose-500/50 hover:bg-rose-500/10 text-rose-400',
    },
    {
      title: 'Lịch tập kháng lực 4 buổi',
      text: 'Tư vấn cho tôi lịch tập gym Upper/Lower 4 buổi/tuần để tăng cơ xương SMM hiệu quả.',
      icon: Dumbbell,
      color: 'hover:border-indigo-500/50 hover:bg-indigo-500/10 text-indigo-400',
    },
  ];

  return (
    <div className="mb-4">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 mb-2 px-1">
        <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
        <span>Gợi ý câu hỏi nhanh:</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {prompts.map((p, idx) => {
          const Icon = p.icon;
          return (
            <button
              key={idx}
              onClick={() => onSelectPrompt(p.text)}
              className={`p-2.5 rounded-xl border border-slate-800 bg-slate-900/60 text-left transition-all duration-200 group flex items-start gap-2.5 ${p.color}`}
            >
              <div className="p-1.5 rounded-lg bg-slate-800 text-slate-300 group-hover:scale-105 transition-transform flex-shrink-0">
                <Icon className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-slate-200 group-hover:text-white truncate">
                  {p.title}
                </div>
                <div className="text-[11px] text-slate-400 line-clamp-1 mt-0.5">
                  {p.text}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
