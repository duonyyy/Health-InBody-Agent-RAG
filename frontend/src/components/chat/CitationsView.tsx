'use client';

import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, FileText, ExternalLink } from 'lucide-react';
import { Citation } from '@/types';

interface CitationsViewProps {
  citations: Citation[];
  defaultExpandedIdx?: number | null;
}

function isValidHttpUrl(urlString?: string | null): boolean {
  if (!urlString) return false;
  try {
    const url = new URL(urlString);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

export default function CitationsView({
  citations,
  defaultExpandedIdx = null,
}: CitationsViewProps) {
  const [expandedId, setExpandedId] = useState<number | null>(defaultExpandedIdx);

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
          const displayId = cite.id != null ? String(cite.id) : String(idx + 1);
          const title = cite.title || cite.source || `Tài liệu tham chiếu [${displayId}]`;
          const excerptText = cite.excerpt || cite.content || 'Chưa có đoạn trích nội dung.';
          const sourceText = cite.source || 'Nguồn tài liệu y tế';
          const validUrl = isValidHttpUrl(cite.source_url || cite.url) ? (cite.source_url || cite.url)! : null;
          const score = typeof cite.retrieval_score === 'number'
            ? cite.retrieval_score
            : typeof cite.score === 'number'
            ? cite.score
            : null;

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
                  <span className="font-mono text-teal-700 font-bold flex-shrink-0">
                    [{displayId}]
                  </span>
                  <span className="font-medium text-slate-800 truncate">
                    {title}
                  </span>
                  {score !== null && (
                    <span
                      title="Điểm số truy xuất thông tin (retrieval score), không phải xác suất y khoa"
                      className="text-[10px] px-1.5 py-0.5 rounded bg-teal-50 text-teal-800 border border-teal-200 font-mono font-semibold flex-shrink-0"
                    >
                      Điểm: {score.toFixed(2)}
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
                  <blockquote className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 font-serif italic text-slate-800 whitespace-pre-wrap">
                    &ldquo;{excerptText}&rdquo;
                  </blockquote>

                  <div className="flex flex-wrap items-center justify-between text-[11px] text-slate-500 gap-2 pt-1">
                    <div className="flex items-center gap-1.5 truncate max-w-md">
                      <span className="font-mono text-[10px] text-slate-600 truncate">
                        Nguồn: {sourceText}
                      </span>
                      {cite.source_version && (
                        <span className="text-[10px] font-mono text-slate-400">
                          (v{cite.source_version})
                        </span>
                      )}
                      {validUrl && (
                        <a
                          href={validUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-0.5 text-teal-600 hover:text-teal-700 hover:underline font-medium text-[10px]"
                        >
                          <span>Liên kết gốc</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5">
                      {cite.source_tier && (
                        <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 font-medium text-[10px] border border-blue-200">
                          {cite.source_tier}
                        </span>
                      )}
                      {(cite.category || cite.content_type) && (
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium uppercase text-[10px] border border-slate-200">
                          {cite.category || cite.content_type}
                        </span>
                      )}
                    </div>
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