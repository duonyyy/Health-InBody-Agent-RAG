'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Sidebar, { TabType } from '@/components/layout/Sidebar';
import Header from '@/components/layout/Header';
import ChatContainer from '@/components/chat/ChatContainer';
import InBodyDashboard from '@/components/inbody/InBodyDashboard';
import ProfileAndGoals from '@/components/profile/ProfileAndGoals';
import CorpusSearch from '@/components/search/CorpusSearch';
import DevTools from '@/components/dev/DevTools';
import { BackendHealth, InBodyMeasurement, UserProfile } from '@/types';
import { checkBackendHealth, fetchInBodyMeasurements, fetchUserProfile } from '@/lib/api';
import { BrandLogo } from '@/components/branding/BrandLogo';
import { Menu, X } from 'lucide-react';

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabType>('chat');
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [latestMeasurement, setLatestMeasurement] = useState<InBodyMeasurement | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);

  // Ref để gọi làm mới phiên chat từ Header
  const chatResetRef = useRef<(() => void) | null>(null);

  // Đọc tab từ URL search params khi tải trang (SCR deep-linking)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tabParam = params.get('tab') as TabType;
      if (tabParam && ['chat', 'inbody', 'profile', 'search', 'dev'].includes(tabParam)) {
        setActiveTab(tabParam);
      }
    }
  }, []);

  const handleSelectTab = useCallback((tab: TabType) => {
    setActiveTab(tab);
    setIsMobileMenuOpen(false);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.set('tab', tab);
      window.history.replaceState(null, '', url.toString());
    }
  }, []);
  useEffect(() => {
    let mounted = true;
    const updateHealth = async () => {
      try {
        const res = await checkBackendHealth();
        if (mounted) setHealth(res);
      } catch {
        if (mounted) {
          setHealth({
            status: 'offline',
            timestamp: new Date().toISOString(),
          });
        }
      }
    };

    updateHealth();
    const interval = setInterval(updateHealth, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // Lấy dữ liệu profile và số đo gần nhất
  const refreshUserContext = useCallback(async () => {
    try {
      const [measurements, profile] = await Promise.allSettled([
        fetchInBodyMeasurements(),
        fetchUserProfile(),
      ]);

      if (measurements.status === 'fulfilled' && measurements.value.length > 0) {
        const sorted = [...measurements.value].sort(
          (a, b) => new Date(b.measured_at).getTime() - new Date(a.measured_at).getTime()
        );
        setLatestMeasurement(sorted[0]);
      }
      if (profile.status === 'fulfilled') {
        setUserProfile(profile.value);
      }
    } catch {
      // Backend offline hoặc chưa có dữ liệu
    }
  }, []);

  // Lấy dữ liệu ban đầu
  useEffect(() => {
    let ignore = false;
    const initUserContext = async () => {
      try {
        const [measurements, profile] = await Promise.allSettled([
          fetchInBodyMeasurements(),
          fetchUserProfile(),
        ]);
        if (ignore) return;
        if (measurements.status === 'fulfilled' && measurements.value.length > 0) {
          const sorted = [...measurements.value].sort(
            (a, b) => new Date(b.measured_at).getTime() - new Date(a.measured_at).getTime()
          );
          setLatestMeasurement(sorted[0]);
        }
        if (profile.status === 'fulfilled') {
          setUserProfile(profile.value);
        }
      } catch {
        // Backend offline hoặc chưa có dữ liệu
      }
    };

    initUserContext();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <div className="flex h-screen bg-[#070b14] text-slate-100 overflow-hidden font-sans">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex">
        <Sidebar
          activeTab={activeTab}
          setActiveTab={handleSelectTab}
          health={health}
          userName={userProfile?.display_name || 'Người dùng BodyWise'}
        />
      </div>

      {/* Mobile Drawer */}
      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/75 backdrop-blur-sm"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div className="relative z-10 w-72 h-full">
            <Sidebar
              activeTab={activeTab}
              setActiveTab={handleSelectTab}
              health={health}
              userName={userProfile?.display_name || 'Người dùng BodyWise'}
            />
          </div>
          <button
            onClick={() => setIsMobileMenuOpen(false)}
            aria-label="Đóng thanh điều hướng di động"
            className="absolute top-4 right-4 z-20 p-2 text-slate-300 hover:text-white rounded-xl bg-slate-900 border border-slate-700"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <div className="md:hidden flex items-center justify-between px-4 py-2.5 bg-slate-950 border-b border-slate-800">
          <button
            onClick={() => setIsMobileMenuOpen(true)}
            aria-label="Mở danh mục điều hướng"
            className="p-1.5 text-slate-300 hover:text-white rounded-lg bg-slate-900 border border-slate-800"
          >
            <Menu className="w-5 h-5" />
          </button>
          <BrandLogo theme="dark" compact height={32} href="/" />
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <span
              className={`w-2 h-2 rounded-full ${
                health?.status === 'healthy'
                  ? 'bg-teal-400'
                  : health?.status === 'degraded'
                  ? 'bg-amber-400'
                  : 'bg-rose-400'
              }`}
            />
            <span className="text-[10px] uppercase font-mono">
              {health?.status === 'healthy' ? 'Online' : 'Offline'}
            </span>
          </div>
        </div>

        <Header
          activeTab={activeTab}
          onNewChat={() => chatResetRef.current?.()}
          latestMeasurement={latestMeasurement}
        />

        <main className="flex-1 overflow-y-auto bg-gradient-to-b from-[#090d16] to-[#060910]">
          {activeTab === 'chat' && (
            <ChatContainer
              onRegisterReset={(resetFn) => {
                chatResetRef.current = resetFn;
              }}
              userDisplayName={userProfile?.display_name}
            />
          )}
          {activeTab === 'inbody' && (
            <InBodyDashboard onMeasurementChange={refreshUserContext} />
          )}
          {activeTab === 'profile' && (
            <ProfileAndGoals onProfileSaved={refreshUserContext} />
          )}
          {activeTab === 'search' && <CorpusSearch />}
          {activeTab === 'dev' && <DevTools initialHealth={health} />}
        </main>
      </div>
    </div>
  );
}
