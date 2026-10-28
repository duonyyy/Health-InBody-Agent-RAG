'use client';

import React, { useState } from 'react';
import { Search, FileText, Filter } from 'lucide-react';
import { Citation } from '@/types';
import { searchCorpusApi } from '@/lib/api';

export default function CorpusSearch() {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [results, setResults] = useState<Citation[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsSearching(true);
    setHasSearched(true);
    try {
      const data = await searchCorpusApi(query, category);
      setResults(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      <div className="glass-card rounded-2xl p-6 border border-slate-800/80 bg-slate-900/60 shadow-lg space-y-4">
        <div>
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Search className="w-5 h-5 text-emerald-400" />
            <span>Tra cứu Kho Tri thức & Tài liệu Y tế (RAG Corpus)</span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Tìm kiếm ngữ nghĩa đa phương thức trên cơ sở dữ liệu y tế, hướng dẫn InBody và dinh dưỡng thể hình
          </p>
        </div>

        {/* Search Bar Form */}
        <form onSubmit={handleSearch} className="space-y-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Nhập từ khóa hoặc câu hỏi (Ví dụ: Tiêu chuẩn PBF nam, đau ngực khi tập, thâm hụt calo...)"
              className="w-full pl-10 pr-24 py-3 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:border-emerald-500 shadow-inner"
            />
            <button
              type="submit"
              disabled={isSearching}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs shadow-md transition-all active:scale-95"
            >
              {isSearching ? 'Đang tìm...' : 'Tra cứu'}
            </button>
          </div>

          {/* Category Filters */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-slate-400 flex items-center gap-1 text-[11px]">
              <Filter className="w-3 h-3 text-slate-400" />
              <span>Chủ đề:</span>
            </span>

            {[
              { id: 'all', label: 'Tất cả tài liệu' },
              { id: 'inbody_guide', label: 'Tiêu chuẩn InBody' },
              { id: 'medical_safety', label: 'An toàn Y tế & Tim mạch' },
              { id: 'nutrition', label: 'Dinh dưỡng & Macros' },
              { id: 'workout', label: 'Lịch tập Kháng lực' },
            ].map((cat) => (
              <button
                key={cat.id}
                type="button"
                onClick={() => setCategory(cat.id)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                  category === cat.id
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                    : 'bg-slate-950 text-slate-400 border border-slate-800 hover:text-slate-200'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </form>
      </div>

      {/* Results Section */}
      <div className="space-y-3">
        {hasSearched && (
          <div className="text-xs text-slate-400 px-1 font-medium">
            Tìm thấy <span className="text-emerald-400 font-bold">{results.length}</span> đoạn tài liệu phù hợp:
          </div>
        )}

        <div className="grid grid-cols-1 gap-3">
          {results.map((doc, idx) => {
            const scorePct = doc.score ? Math.round(doc.score * 100) : 90;
            return (
              <div
                key={idx}
                className="glass-card rounded-2xl p-4 border border-slate-800/80 bg-slate-900/60 shadow-md space-y-2.5 hover:border-emerald-500/30 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    <h4 className="font-bold text-slate-100 text-sm">{doc.title}</h4>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-800 font-mono font-semibold flex-shrink-0">
                    {scorePct}% match
                  </span>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 font-serif italic">
                  &ldquo;{doc.content}&rdquo;
                </p>

                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/60">
                  <span className="font-mono text-slate-400">Tệp: {doc.source}</span>
                  {doc.category && (
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 uppercase text-[10px] tracking-wider font-semibold">
                      {doc.category}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
