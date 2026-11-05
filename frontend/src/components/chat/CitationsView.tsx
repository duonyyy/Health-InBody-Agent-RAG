'use client';

import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, FileText, ExternalLink } from 'lucide-react';
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
    <div className="mt-3 pt-3 border-t border-slate-800/80">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 mb-2">
        <BookOpen className="w-3.5 h-3.5 text-teal-400" />
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
              className="rounded-xl border border-slate-800 bg-slate-950/70 hover:border-slate-700 transition-colors overflow-hidden"
            >
              <button
                onClick={() => setExpandedId(isExpanded ? null : idx)}
                aria-expanded={isExpanded}
                className="w-full px-3 py-2 text-left flex items-center justify-between text-xs gap-2"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                  <span
                    className="font-medium text-slate-200 truncate"
                    dangerouslySetInnerHTML={{ __html: safeTitle }}
                  />
                  {scorePct !== null && (
                    <span
                      title="Chỉ số tương đồng ngữ nghĩa đối chiếu vector/từ khóa (Không phải độ chính xác y khoa)"
                      className="text-[10px] px-1.5 py-0.5 rounded bg-teal-950/80 text-teal-300 border border-teal-800/60 font-mono flex-shrink-0"
                    >
                      Tương đồng {scorePct}%
                    </span>
                  )}
                </div>

                {isExpanded ? (
                  <ChevronUp className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                )}
              </button>

              {isExpanded && (
                <div className="p-3 bg-slate-900/60 border-t border-slate-800/80 text-xs text-slate-300 leading-relaxed space-y-2">
                  <p
                    className="italic text-slate-300 bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 font-serif leading-relaxed"
                    dangerouslySetInnerHTML={{ __html: `&ldquo;${safeContent}&rdquo;` }}
                  />
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400 pt-1">
                    <span className="font-mono text-slate-400">
                      Nguồn: <span dangerouslySetInnerHTML={{ __html: safeSource }} />
                    </span>
                    {cite.url && (
                      <a
                        href={cite.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-teal-400 hover:underline"
                      >
                        <span>Xem liên kết</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    {cite.category && (
                      <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] uppercase font-semibold">
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
