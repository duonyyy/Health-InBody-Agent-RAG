'use client';

import React, { useState } from 'react';
import {
  PlusCircle,
  Settings,
  Sparkles,
  Server,
  CheckCircle2,
  X,
  AlertTriangle,
  User,
} from 'lucide-react';
import { TabType } from './Sidebar';
import {
  getApiBaseUrl,
  setApiBaseUrl,
  getAuthMode,
  getActiveUserId,
  setActiveUserId,
  isExplicitDemoMode,
  setExplicitDemoMode,
} from '@/lib/api';
import { InBodyMeasurement } from '@/types';

interface HeaderProps {
  activeTab: TabType;
  onNewChat?: () => void;
  latestMeasurement?: InBodyMeasurement | null;
}

export default function Header({
  activeTab,
  onNewChat,
  latestMeasurement,
}: HeaderProps) {
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [apiUrlInput, setApiUrlInput] = useState('');
  const [devUserIdInput, setDevUserIdInput] = useState('');
  const [demoModeInput, setDemoModeInput] = useState(false);

  const titles: Record<TabType, { title: string; subtitle: string }> = {
    chat: {
      title: 'Trợ lý AI Thể trạng & Dinh dưỡng BodyWise',
      subtitle: 'Định tuyến tác tử chuyên sâu: Sàng lọc An toàn, Phân tích InBody, Dinh dưỡng & Kế hoạch tập',
    },
    inbody: {
      title: 'Chỉ số Thể trạng & Bảng Điều Khiển InBody',
      subtitle: 'Đối chiếu chuẩn WHO Tây Thái Bình Dương (WPRO), biểu đồ tiến trình và bóc tách phiếu đo OCR',
    },
    profile: {
      title: 'Hồ sơ Cá nhân, Mục tiêu & Ký ức AI',
      subtitle: 'Quản lý thông tin nhân trắc học, nhật ký vận động check-in và minh bạch ký ức cá nhân hóa',
    },
    search: {
      title: 'Thư viện Kiến thức & Tra cứu Kho Tri thức Y sinh',
      subtitle: 'Tìm kiếm ngữ nghĩa đa phương thức trên kho dữ liệu InBody và y tế an toàn',
    },
    dev: {
      title: 'Kiểm tra Hệ thống & Hộp Cát Kỹ thuật (Dev Sandbox)',
      subtitle: 'Giám sát dịch vụ backend, độ trễ và kiểm thử thuật toán độc lập',
    },
  };

  const handleOpenSettings = () => {
    setApiUrlInput(getApiBaseUrl());
    setDevUserIdInput(getActiveUserId());
    setDemoModeInput(isExplicitDemoMode());
    setShowSettingsModal(true);
  };

  const handleSaveSettings = () => {
    if (apiUrlInput.trim()) {
      setApiBaseUrl(apiUrlInput.trim());
    }
    if (devUserIdInput.trim()) {
      setActiveUserId(devUserIdInput.trim());
    }
    setExplicitDemoMode(demoModeInput);
    setShowSettingsModal(false);
    window.location.reload();
  };

  const weight = latestMeasurement?.weight_kg;
  const pbf = latestMeasurement?.pbf_percent ?? latestMeasurement?.percent_body_fat;
  const smm = latestMeasurement?.smm_kg ?? latestMeasurement?.skeletal_muscle_mass_kg;

  return (
    <>
      <header className="h-16 px-6 glass-panel border-b border-slate-800/80 bg-slate-950/80 flex items-center justify-between sticky top-0 z-30">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm sm:text-base font-bold text-slate-100 tracking-tight">
              {titles[activeTab].title}
            </h2>
            <span className="hidden sm:inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-slate-800/80 text-teal-300 border border-teal-500/30">
              <Sparkles className="w-3 h-3 text-teal-400" />
              <span>Multi-Agent RAG</span>
            </span>
          </div>
          <p className="text-[11px] sm:text-xs text-slate-400 truncate max-w-xl">
            {titles[activeTab].subtitle}
          </p>
        </div>

        {/* Quick summary metrics & actions */}
        <div className="flex items-center gap-3">
          {/* Latest metrics badge */}
          {latestMeasurement && (
            <div className="hidden lg:flex items-center gap-2 bg-slate-900/90 px-3 py-1.5 rounded-xl border border-slate-800/80 text-xs">
              <span className="text-slate-400 font-medium">Lần đo mới nhất:</span>
              <div className="flex items-center gap-2.5">
                {weight !== undefined && (
                  <span className="text-slate-200 font-semibold">{weight} kg</span>
                )}
                {pbf !== undefined && (
                  <>
                    <span className="w-1 h-1 rounded-full bg-slate-600" />
                    <span className="text-teal-400 font-semibold">{pbf}% Mỡ</span>
                  </>
                )}
                {smm !== undefined && (
                  <>
                    <span className="w-1 h-1 rounded-full bg-slate-600" />
                    <span className="text-sky-400 font-semibold">{smm} kg Cơ</span>
                  </>
                )}
              </div>
            </div>
          )}

          {activeTab === 'chat' && onNewChat && (
            <button
              onClick={onNewChat}
              className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 hover:text-teal-300 border border-slate-800 hover:border-teal-500/40 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-sm"
              title="Bắt đầu phiên hội thoại mới trên giao diện (Lịch sử máy chủ được lưu riêng theo phiên)"
            >
              <PlusCircle className="w-3.5 h-3.5 text-teal-400" />
              <span>Cuộc trò chuyện mới</span>
            </button>
          )}

          <button
            onClick={handleOpenSettings}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 transition-colors"
            title="Cấu hình kết nối Backend & Chế độ Demo"
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
                <Server className="w-5 h-5 text-teal-400" />
                <span>Cấu hình Hệ thống BodyWise</span>
              </div>
              <button
                onClick={() => setShowSettingsModal(false)}
                className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="py-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Địa chỉ Cổng Backend API (FastAPI)
                </label>
                <input
                  type="text"
                  value={apiUrlInput}
                  onChange={(e) => setApiUrlInput(e.target.value)}
                  placeholder="http://localhost:8000"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-teal-500 font-mono"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Mặc định: <code className="text-teal-400">http://localhost:8000</code>.
                </p>
              </div>

              {getAuthMode() === 'development' && (
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-teal-400" />
                    <span>Mã định danh Kiểm thử (X-Dev-User-Id)</span>
                  </label>
                  <input
                    type="text"
                    value={devUserIdInput}
                    onChange={(e) => setDevUserIdInput(e.target.value)}
                    placeholder="demo-user"
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-teal-500 font-mono"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">
                    Đang ở chế độ <b>Development</b>. Header này dùng để đối soát dữ liệu cá nhân theo từng tài khoản dev độc lập.
                  </p>
                </div>
              )}

              {/* Explicit Demo Mode Toggle */}
              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold text-slate-200">Chế độ Demo Dữ liệu Mẫu</div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={demoModeInput}
                      onChange={(e) => setDemoModeInput(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-teal-500"></div>
                  </label>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Khi bật, giao diện sẽ nạp dữ liệu mẫu để duyệt thử UI khi chưa khởi động backend. Khi tắt (mặc định), hệ thống kết nối trực tiếp 100% API thật và báo lỗi trung thực khi máy chủ ngoại tuyến.
                </p>
              </div>

              {getAuthMode() === 'production' && (
                <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-800/60 text-xs text-amber-200 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                  <span>
                    Chế độ Production: Hệ thống yêu cầu phiên đăng nhập có chữ ký bảo mật từ Auth Gateway. Các chức năng lưu trữ được quản lý nghiêm ngặt.
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                onClick={() => setShowSettingsModal(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Đóng
              </button>
              <button
                onClick={handleSaveSettings}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-teal-500 to-sky-500 hover:brightness-110 text-slate-950 text-xs font-bold shadow-md shadow-teal-500/25 flex items-center gap-1.5"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Áp dụng & Tải lại</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
