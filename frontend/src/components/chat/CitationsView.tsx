'use client';

import React, { useState } from 'react';
import { BookOpen, ExternalLink, ChevronDown, ChevronUp, FileText } from 'lucide-react';
import { Citation } from '@/types';

interface CitationsViewProps {
  citations: Citation[];
}

export default function CitationsView({ citations }: CitationsViewProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-3 pt-3 border-t border-slate-800/80">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 mb-2">
        <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
        <span>Tài liệu trích dẫn & Cơ sở bằng chứng ({citations.length})</span>
      </div>

      <div className="space-y-1.5">
        {citations.map((cite, idx) => {
          const isExpanded = expandedId === idx;
          const scorePct = cite.score ? Math.round(cite.score * 100) : null;

          return (
            <div
              key={idx}
              className="rounded-xl border border-slate-800 bg-slate-950/70 hover:border-slate-700 transition-colors overflow-hidden"
            >
              <button
                onClick={() => setExpandedId(isExpanded ? null : idx)}
                className="w-full px-3 py-2 text-left flex items-center justify-between text-xs gap-2"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                  <span className="font-medium text-slate-200 truncate">
                    {cite.title || cite.source || `Trích dẫn #${idx + 1}`}
                  </span>
                  {scorePct && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800/60 font-mono">
                      {scorePct}% match
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
                  <p className="italic text-slate-300 bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 font-serif">
                    &ldquo;{cite.content}&rdquo;
                  </p>
                  {cite.source && (
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>Nguồn tài liệu: {cite.source}</span>
                      {cite.category && (
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                          {cite.category}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
