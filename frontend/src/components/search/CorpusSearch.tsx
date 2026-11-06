'use client';

import React, { useState } from 'react';
import { Search, FileText, Filter, AlertCircle, RefreshCw, BookOpen, Layers } from 'lucide-react';
import { Citation } from '@/types';
import { searchCorpusApi } from '@/lib/api';

export default function CorpusSearch() {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [results, setResults] = useState<Citation[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setHasSearched(true);
    setErrorMessage(null);

    try {
      const data = await searchCorpusApi(query.trim(), category);
      setResults(data);
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Không thể kết nối đến máy chủ để tìm kiếm tài liệu.';
      setErrorMessage(msg);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleCategoryChange = (catId: string) => {
    setCategory(catId);
    if (query.trim()) {
      setIsSearching(true);
      setHasSearched(true);
      setErrorMessage(null);
      searchCorpusApi(query.trim(), catId)
        .then((data) => setResults(data))
        .catch((err) => {
          setErrorMessage(err instanceof Error ? err.message : 'Lỗi tra cứu tài liệu.');
          setResults([]);
        })
        .finally(() => setIsSearching(false));
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Search Header & Bar */}
      <div className="rounded-2xl p-6 border border-slate-200 bg-white shadow-xs space-y-4">
        <div>
          <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Search className="w-5 h-5 text-teal-600" />
            <span>Thư viện Tri thức & RAG Corpus</span>
          </h3>
          <p className="text-xs text-slate-600 mt-1 leading-relaxed">
            Tra cứu văn bản chuẩn hóa trên tập tài liệu y tế, chuẩn InBody, dinh dưỡng thể thao và an toàn sức khỏe.
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
              placeholder="Nhập từ khóa tìm kiếm (Ví dụ: Tiêu chuẩn PBF nam, đau ngực khó thở, thâm hụt calo, creatine...)"
              className="w-full pl-10 pr-28 py-3 rounded-xl bg-slate-50 border border-slate-300 text-slate-900 text-sm focus:bg-white focus:outline-none focus:border-teal-600 shadow-inner"
            />
            <button
              type="submit"
              disabled={isSearching || !query.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-bold text-xs shadow-sm transition-all active:scale-95 flex items-center gap-1.5"
            >
              {isSearching ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Đang tìm...</span>
                </>
              ) : (
                <span>Tra cứu</span>
              )}
            </button>
          </div>

          {/* Category Filters */}
          <div className="flex flex-wrap items-center gap-2 text-xs pt-1">
            <span className="text-slate-500 flex items-center gap-1 text-[11px] font-medium">
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
                onClick={() => handleCategoryChange(cat.id)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                  category === cat.id
                    ? 'bg-teal-50 text-teal-800 border border-teal-200 font-bold shadow-xs'
                    : 'bg-slate-100 text-slate-600 border border-slate-200 hover:text-slate-900 hover:bg-slate-200/60'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </form>
      </div>

      {/* Error state */}
      {errorMessage && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start justify-between gap-3 shadow-xs">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-rose-800">Không thể thực hiện tra cứu tài liệu</p>
              <p className="text-rose-700 mt-0.5">{errorMessage}</p>
            </div>
          </div>
          <button
            onClick={() => handleSearch()}
            className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold flex-shrink-0 flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Thử lại</span>
          </button>
        </div>
      )}

      {/* Loading state */}
      {isSearching && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-2xl p-4 border border-slate-200 bg-white space-y-3 shadow-xs animate-pulse"
            >
              <div className="h-4 bg-slate-200 rounded w-1/3" />
              <div className="h-14 bg-slate-100 rounded-xl" />
              <div className="h-3 bg-slate-200 rounded w-1/4" />
            </div>
          ))}
        </div>
      )}

      {/* Results Section */}
      {!isSearching && !errorMessage && hasSearched && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-600 px-1 font-medium">
            <span>
              Tìm thấy <strong className="text-teal-700">{results.length}</strong> đoạn tài liệu phù hợp:
            </span>
            <span className="text-[11px] text-slate-500">
              Điểm tương đồng phản ánh độ trùng khớp ngữ nghĩa của thuật toán Vector/BM25
            </span>
          </div>

          {results.length === 0 ? (
            <div className="rounded-2xl p-8 border border-slate-200 bg-white text-center space-y-3 shadow-xs">
              <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-500 flex items-center justify-center mx-auto border border-slate-200">
                <BookOpen className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-semibold text-slate-900">
                Không tìm thấy đoạn trích phù hợp
              </h4>
              <p className="text-xs text-slate-600 max-w-md mx-auto">
                Không có tài liệu nào trong thư viện trùng khớp với từ khóa &ldquo;{query}&rdquo; thuộc chủ đề đã chọn. Bạn hãy thử từ khóa ngắn hơn hoặc chọn &ldquo;Tất cả tài liệu&rdquo;.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {results.map((doc, idx) => {
                const scorePct = doc.score ? Math.round(doc.score * 100) : 90;
                return (
                  <div
                    key={idx}
                    className="rounded-2xl p-4 border border-slate-200 bg-white shadow-xs space-y-2.5 hover:border-teal-500 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-teal-600 flex-shrink-0" />
                        <h4 className="font-bold text-slate-900 text-sm">{doc.title}</h4>
                      </div>
                      <span
                        className="text-[11px] px-2.5 py-0.5 rounded-full bg-teal-50 text-teal-800 border border-teal-200 font-mono font-semibold flex-shrink-0"
                        title="Độ tương đồng ngữ nghĩa vector/BM25, không phải độ chính xác y khoa"
                      >
                        Tương đồng: {scorePct}%
                      </span>
                    </div>

                    <p className="text-xs text-slate-800 leading-relaxed bg-slate-50 p-3.5 rounded-xl border border-slate-200 font-serif italic selection:bg-teal-100">
                      &ldquo;{doc.content}&rdquo;
                    </p>

                    <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1.5 border-t border-slate-100">
                      <span className="font-mono text-slate-600 truncate max-w-md">
                        Nguồn trích dẫn: {doc.source}
                      </span>
                      {doc.category && (
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 uppercase text-[10px] tracking-wider font-semibold flex-shrink-0 border border-slate-200">
                          {doc.category}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Initial empty helper */}
      {!hasSearched && !isSearching && (
        <div className="rounded-2xl p-8 border border-slate-200 bg-white text-center space-y-3 shadow-xs">
          <div className="w-12 h-12 rounded-2xl bg-teal-50 text-teal-600 flex items-center justify-center mx-auto border border-teal-200">
            <Layers className="w-6 h-6" />
          </div>
          <h4 className="text-sm font-semibold text-slate-900">
            Tra cứu trực tiếp trên Corpus đã lập chỉ mục
          </h4>
          <p className="text-xs text-slate-600 max-w-lg mx-auto leading-relaxed">
            Dữ liệu bao gồm các hướng dẫn phân tích InBody, tiêu chuẩn mỡ nội tạng WHO WPRO, phác đồ an toàn y tế và nguyên tắc dinh dưỡng kháng lực. Nhập câu hỏi để bắt đầu.
          </p>
        </div>
      )}
    </div>
  );
}