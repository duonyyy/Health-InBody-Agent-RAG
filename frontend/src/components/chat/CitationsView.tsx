'use client';

import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, FileText } from 'lucide-react';
import { Citation } from '@/types';

interface CitationsViewProps {
  citations: Citation[];
}

/**
 * Escape chuỗi để phòng ngừa XSS trong nội dung trích dẫn
 */
function sanitizeText(text: string): string {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export default function CitationsView({ citations }: CitationsViewProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-3 pt-3 border-t border-slate-200">
      <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 mb-2">
        <BookOpen className="w-3.5 h-3.5 text-teal-600" />
        <span>Tài liệu trích dẫn & Nguồn chứng cứ y sinh ({citations.length})</span>
      </div>

      <div className="space-y-1.5">
        {citations.map((cite, idx) => {
          const isExpanded = expandedId === idx;
          // Điểm similarity là độ tương đồng vector/từ vựng của Qdrant/BM25, KHÔNG PHẢI độ chính xác y khoa
          const scorePct = typeof cite.score === 'number' ? Math.round(cite.score * 100) : null;
          const safeTitle = sanitizeText(cite.title || cite.source || `Tài liệu tham chiếu #${idx + 1}`);
          const safeContent = sanitizeText(cite.content || '');
          const safeSource = sanitizeText(cite.source || '');

          return (
            <div
              key={idx}
              className="rounded-xl border border-slate-200 bg-slate-50/70 hover:border-slate-300 transition-colors overflow-hidden"
            >
              <button
                onClick={() => setExpandedId(isExpanded ? null : idx)}
                aria-expanded={isExpanded}
                className="w-full px-3 py-2 text-left flex items-center justify-between text-xs gap-2"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                  <span
                    className="font-medium text-slate-800 truncate"
                    dangerouslySetInnerHTML={{ __html: safeTitle }}
                  />
                  {scorePct !== null && (
                    <span
                      title="Chỉ số tương đồng ngữ nghĩa đối chiếu vector/từ khóa (Không phải độ chính xác y khoa)"
                      className="text-[10px] px-1.5 py-0.5 rounded bg-teal-50 text-teal-800 border border-teal-200 font-mono font-semibold flex-shrink-0"
                    >
                      Tương đồng {scorePct}%
                    </span>
                  )}
                </div>

                {isExpanded ? (
                  <ChevronUp className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                )}
              </button>

              {isExpanded && (
                <div className="p-3 bg-white border-t border-slate-200 text-xs text-slate-700 leading-relaxed space-y-2">
                  <p
                    className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 font-serif italic text-slate-800"
                    dangerouslySetInnerHTML={{ __html: `&ldquo;${safeContent}&rdquo;` }}
                  />
                  <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                    <span
                      className="truncate max-w-[280px] font-mono text-[10px]"
                      dangerouslySetInnerHTML={{ __html: `Tệp nguồn: ${safeSource}` }}
                    />
                    {cite.category && (
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium uppercase text-[10px] border border-slate-200">
                        {cite.category}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}