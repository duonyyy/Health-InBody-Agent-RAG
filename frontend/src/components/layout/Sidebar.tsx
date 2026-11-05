'use client';

import React from 'react';
import {
  MessageSquare,
  Activity,
  UserCheck,
  Search,
  Sliders,
  ShieldCheck,
  ChevronRight,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { BackendHealth } from '@/types';
import { BrandLogo } from '@/components/branding/BrandLogo';
import { getAuthMode, getActiveUserId, isExplicitDemoMode } from '@/lib/api';

export type TabType = 'chat' | 'inbody' | 'profile' | 'search' | 'dev';

interface SidebarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  health: BackendHealth | null;
  userName?: string;
}

export default function Sidebar({
  activeTab,
  setActiveTab,
  health,
  userName = 'Người dùng',
}: SidebarProps) {
  const isDevEnvironment = process.env.NODE_ENV !== 'production' || getAuthMode() === 'development';
  const isDemo = isExplicitDemoMode();

  const navItems: Array<{
    id: TabType;
    label: string;
    desc: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: string;
  }> = [
    {
      id: 'chat',
      label: 'Trợ lý AI & Chat',
      desc: 'Hỏi đáp thể trạng & dinh dưỡng',
      icon: MessageSquare,
      badge: 'Đa tác tử',
    },
    {
      id: 'inbody',
      label: 'Thể trạng & InBody',
      desc: 'Biểu đồ, đo đạc & OCR',
      icon: Activity,
      badge: 'Chuẩn WPRO',
    },
    {
      id: 'profile',
      label: 'Hồ sơ & Mục tiêu',
      desc: 'Check-in, bệnh nền & ký ức',
      icon: UserCheck,
    },
    {
      id: 'search',
      label: 'Thư viện kiến thức',
      desc: 'Tài liệu InBody & Y tế',
      icon: Search,
    },
  ];

  // Chỉ hiển thị tab Kỹ thuật & Sandbox khi ở môi trường development
  if (isDevEnvironment) {
    navItems.push({
      id: 'dev',
      label: 'Hệ thống & Sandbox',
      desc: 'Health check & API tools',
      icon: Sliders,
      badge: 'Dev',
    });
  }

  return (
    <aside className="w-72 flex-shrink-0 flex flex-col h-screen glass-panel border-r border-slate-800/80 bg-slate-950/90 select-none">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-800/60">
        <BrandLogo theme="dark" href="/" priority />
      </div>

      {/* Navigation List */}
      <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
        <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider uppercase text-slate-400">
          Chức năng chính
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full text-left px-3.5 py-2.5 rounded-xl flex items-center justify-between transition-all duration-200 group ${
                isActive
                  ? 'bg-gradient-to-r from-teal-500/20 to-sky-500/10 border border-teal-500/40 text-teal-200 shadow-sm'
                  : 'text-slate-300 hover:bg-slate-800/50 hover:text-slate-100 border border-transparent'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                    isActive
                      ? 'bg-teal-500 text-slate-950 font-semibold shadow-md shadow-teal-500/30'
                      : 'bg-slate-800 text-slate-400 group-hover:text-slate-200 group-hover:bg-slate-700'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-medium">{item.label}</div>
                  <div className="text-[11px] text-slate-400">{item.desc}</div>
                </div>
              </div>

              {item.badge ? (
                <span
                  className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                    isActive
                      ? 'bg-teal-500/30 text-teal-300 border border-teal-500/40'
                      : 'bg-slate-800 text-slate-400 border border-slate-700'
                  }`}
                >
                  {item.badge}
                </span>
              ) : (
                <ChevronRight
                  className={`w-4 h-4 text-slate-400 transition-transform ${
                    isActive ? 'text-teal-400 translate-x-0.5' : 'group-hover:translate-x-0.5'
                  }`}
                />
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom Health & User Status */}
      <div className="p-3 border-t border-slate-800/60 space-y-2.5 bg-slate-950/60">
        {/* Demo banner indicator if explicit demo mode is on */}
        {isDemo && (
          <div className="px-3 py-1 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[11px] font-medium text-center">
            Đang bật Chế độ Demo Dữ liệu Mẫu
          </div>
        )}

        {/* Backend Connectivity Status */}
        <div className="px-3 py-2 rounded-lg bg-slate-900/90 border border-slate-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  health?.status === 'healthy'
                    ? 'bg-teal-400'
                    : health?.status === 'degraded'
                    ? 'bg-amber-400'
                    : 'bg-rose-400'
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  health?.status === 'healthy'
                    ? 'bg-teal-500'
                    : health?.status === 'degraded'
                    ? 'bg-amber-500'
                    : 'bg-rose-500'
                }`}
              />
            </span>
            <span className="text-slate-300 font-medium">
              {health?.status === 'healthy'
                ? 'Máy chủ Sẵn sàng'
                : health?.status === 'degraded'
                ? 'Dịch vụ Suy giảm'
                : 'Mất kết nối Máy chủ'}
            </span>
          </div>

          <div className="flex items-center gap-1 text-[11px] text-slate-400">
            {health?.status === 'offline' ? (
              <WifiOff className="w-3.5 h-3.5 text-rose-400" />
            ) : (
              <Wifi className="w-3.5 h-3.5 text-teal-400" />
            )}
            <span>{health?.latency_ms ? `${health.latency_ms}ms` : '--'}</span>
          </div>
        </div>

        {/* User Card */}
        <div className="flex items-center justify-between px-2 py-1">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-teal-500 to-sky-500 flex items-center justify-center text-xs font-bold text-slate-950 shadow-sm">
              BW
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-200">{userName}</div>
              <div className="text-[10px] text-slate-400 font-mono">
                {getAuthMode() === 'development' ? `Dev ID: ${getActiveUserId()}` : 'Xác thực Máy chủ'}
              </div>
            </div>
          </div>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-teal-300 border border-slate-700">
            P1 Beta
          </span>
        </div>

        {/* Medical disclaimer note */}
        <div className="flex items-start gap-1.5 px-2 text-[10px] text-slate-400 leading-tight">
          <ShieldCheck className="w-3.5 h-3.5 text-teal-400 flex-shrink-0 mt-0.5" />
          <span>Thông tin tham khảo thể trạng, không thay thế chẩn đoán y khoa.</span>
        </div>
      </div>
    </aside>
  );
}
