'use client';

import React, { useState } from 'react';
import {
  Trash2,
  Settings,
  Sparkles,
  Server,
  CheckCircle2,
  X,
} from 'lucide-react';
import { TabType } from './Sidebar';
import { getApiBaseUrl, setApiBaseUrl } from '@/lib/api';

interface HeaderProps {
  activeTab: TabType;
  onClearChat?: () => void;
  latestWeight?: number;
  latestPbf?: number;
  latestSmm?: number;
}

export default function Header({
  activeTab,
  onClearChat,
  latestWeight = 72.4,
  latestPbf = 19.5,
  latestSmm = 33.8,
}: HeaderProps) {
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [apiUrlInput, setApiUrlInput] = useState('');

  const titles: Record<TabType, { title: string; subtitle: string }> = {
    chat: {
      title: 'Trợ lý AI Thể trạng & InBody',
      subtitle: 'Hệ thống định tuyến đa tác tử: An toàn Y tế, Phân tích InBody, Dinh dưỡng & Lịch tập',
    },
    inbody: {
      title: 'Chỉ số Thể trạng & Tiến trình InBody',
      subtitle: 'Theo dõi 5 chỉ số cốt lõi, biểu đồ Recharts timeline, và công cụ quét OCR phiếu InBody',
    },
    profile: {
      title: 'Hồ sơ Cá nhân & Mục tiêu Tập luyện',
      subtitle: 'Quản lý thông tin thể chất, khảo sát check-in định kỳ và ký ức cá nhân hóa',
    },
    search: {
      title: 'Tra cứu Corpus & Kiến thức Y tế',
      subtitle: 'Tìm kiếm ngữ nghĩa đa phương thức trên kho dữ liệu InBody và y tế an toàn',
    },
    dev: {
      title: 'Dev Tools & Kiểm thử Hệ thống',
      subtitle: 'Kiểm tra độ trễ endpoints, chạy thử nghiệm tools và giám sát trạng thái backend',
    },
  };

  const handleOpenSettings = () => {
    setApiUrlInput(getApiBaseUrl());
    setShowSettingsModal(true);
  };

  const handleSaveSettings = () => {
    if (apiUrlInput.trim()) {
      setApiBaseUrl(apiUrlInput.trim());
      setShowSettingsModal(false);
      window.location.reload();
    }
  };

  return (
    <>
      <header className="h-18 px-6 glass-panel border-b border-slate-800/80 bg-slate-950/80 flex items-center justify-between sticky top-0 z-30">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-slate-100 tracking-tight">
              {titles[activeTab].title}
            </h2>
            <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-slate-800/80 text-emerald-400 border border-emerald-500/30">
              <Sparkles className="w-3 h-3 text-emerald-400" />
              <span>Agentic AI</span>
            </span>
          </div>
          <p className="text-xs text-slate-400">{titles[activeTab].subtitle}</p>
        </div>

        {/* Quick summary metrics & actions */}
        <div className="flex items-center gap-4">
          <div className="hidden lg:flex items-center gap-2 bg-slate-900/90 px-3 py-1.5 rounded-xl border border-slate-800/80 text-xs">
            <span className="text-slate-400 font-medium">Chỉ số mới nhất:</span>
            <div className="flex items-center gap-2.5">
              <span className="text-slate-200 font-semibold">{latestWeight} kg</span>
              <span className="w-1 h-1 rounded-full bg-slate-600" />
              <span className="text-emerald-400 font-semibold">{latestPbf}% Mỡ</span>
              <span className="w-1 h-1 rounded-full bg-slate-600" />
              <span className="text-sky-400 font-semibold">{latestSmm} kg Cơ</span>
            </div>
          </div>

          {activeTab === 'chat' && onClearChat && (
            <button
              onClick={onClearChat}
              className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-rose-300 border border-slate-800 hover:border-rose-900/50 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-sm"
              title="Xóa lịch sử trò chuyện hiện tại"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Xóa chat</span>
            </button>
          )}

          <button
            onClick={handleOpenSettings}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 transition-colors"
            title="Cấu hình kết nối Backend"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Settings Modal */}
      {showSettingsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-md p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2 text-slate-100 font-semibold">
                <Server className="w-5 h-5 text-emerald-400" />
                <span>Cấu hình Cổng Kết nối Backend</span>
              </div>
              <button
                onClick={() => setShowSettingsModal(false)}
                className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="py-4 space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Backend API Base URL (FastAPI)
                </label>
                <input
                  type="text"
                  value={apiUrlInput}
                  onChange={(e) => setApiUrlInput(e.target.value)}
                  placeholder="http://localhost:8000"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:border-emerald-500 font-mono"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Mặc định: <code className="text-emerald-400">http://localhost:8000</code>. Khi chạy Docker, có thể cấu hình cổng tương ứng.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 text-xs text-slate-300 space-y-1">
                <div className="font-medium text-emerald-400">Ghi chú tự động dự phòng:</div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Nếu backend chưa khởi động, giao diện Next.js sẽ tự động kích hoạt bộ máy mô phỏng Agent RAG nội bộ đầy đủ logic (Safety Fast-Path, InBody Advisor, Recharts timeline).
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                onClick={() => setShowSettingsModal(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Hủy
              </button>
              <button
                onClick={handleSaveSettings}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium shadow-md shadow-emerald-600/30 flex items-center gap-1.5"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Lưu & Áp dụng</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
