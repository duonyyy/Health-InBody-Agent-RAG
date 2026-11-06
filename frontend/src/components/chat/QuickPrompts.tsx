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
      borderColor: 'hover:border-emerald-500 hover:bg-emerald-50/50',
      iconColor: 'text-emerald-700 bg-emerald-100',
    },
    {
      title: 'Thực đơn tăng cơ giảm mỡ',
      text: 'Gợi ý cho tôi thực đơn mẫu tái tạo thể trạng (Body Recomposition) phù hợp kiêng lactose.',
      icon: Utensils,
      borderColor: 'hover:border-sky-500 hover:bg-sky-50/50',
      iconColor: 'text-sky-700 bg-sky-100',
    },
    {
      title: 'Test An toàn Y tế (115)',
      text: 'Tôi bị đau thắt ngực dữ dội và cảm giác khó thở khi hít sâu, tôi nên làm gì?',
      icon: ShieldAlert,
      borderColor: 'hover:border-rose-500 hover:bg-rose-50/50',
      iconColor: 'text-rose-700 bg-rose-100',
    },
    {
      title: 'Lịch tập kháng lực 4 buổi',
      text: 'Tư vấn cho tôi lịch tập gym Upper/Lower 4 buổi/tuần để tăng cơ xương SMM hiệu quả.',
      icon: Dumbbell,
      borderColor: 'hover:border-indigo-500 hover:bg-indigo-50/50',
      iconColor: 'text-indigo-700 bg-indigo-100',
    },
  ];

  return (
    <div className="mb-4">
      <div className="flex items-center gap-1.5 text-xs font-bold text-slate-600 mb-2 px-1">
        <Sparkles className="w-3.5 h-3.5 text-teal-600" />
        <span>Gợi ý câu hỏi nhanh:</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {prompts.map((p, idx) => {
          const Icon = p.icon;
          return (
            <button
              key={idx}
              onClick={() => onSelectPrompt(p.text)}
              className={`p-3 rounded-xl border border-slate-200 bg-white text-left transition-all duration-150 group flex items-start gap-2.5 shadow-xs ${p.borderColor}`}
            >
              <div className={`p-1.5 rounded-lg ${p.iconColor} group-hover:scale-105 transition-transform flex-shrink-0`}>
                <Icon className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-slate-800 group-hover:text-slate-950 truncate">
                  {p.title}
                </div>
                <div className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
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