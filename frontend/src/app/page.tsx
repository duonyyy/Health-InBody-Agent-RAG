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
import { checkBackendHealth, fetchInBodyMeasurements, fetchUserProfile, clearAccessToken, getAuthMode, hasAccessToken } from '@/lib/api';
import AuthPanel from '@/components/auth/AuthPanel';
import { BrandLogo } from '@/components/branding/BrandLogo';
import { Menu, X } from 'lucide-react';

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabType>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tabParam = params.get('tab') as TabType;
      if (tabParam && ['chat', 'inbody', 'profile', 'search', ...(getAuthMode() === 'development' ? ['dev'] : [])].includes(tabParam)) {
        return tabParam;
      }
    }
    return 'chat';
  });
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [latestMeasurement, setLatestMeasurement] = useState<InBodyMeasurement | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [authenticated, setAuthenticated] = useState(() => getAuthMode() === 'development' || hasAccessToken());
  const [authEpoch, setAuthEpoch] = useState(0);

  useEffect(() => {
    const expire = () => {
      setAuthenticated(false);
      setUserProfile(null);
      setLatestMeasurement(null);
    };
    window.addEventListener('bodywise-auth-expired', expire);
    return () => window.removeEventListener('bodywise-auth-expired', expire);
  }, []);

  // Ref để gọi làm mới phiên chat từ Header
  const chatResetRef = useRef<(() => void) | null>(null);

  const handleSelectTab = useCallback((tab: TabType) => {
    if (tab === 'dev' && getAuthMode() !== 'development') return;
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
    if (!authenticated) return;
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
  }, [authenticated]);

  // Lấy dữ liệu ban đầu
  useEffect(() => {
    if (!authenticated) return;
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
  }, [authenticated, authEpoch]);

  if (!authenticated) {
    return <AuthPanel onAuthenticated={() => { setAuthenticated(true); setAuthEpoch((value) => value + 1); }} />;
  }

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 overflow-hidden font-sans">
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
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm"
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
            className="absolute top-4 right-4 z-20 p-2 text-slate-600 hover:text-slate-900 rounded-xl bg-white border border-slate-200 shadow-md"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen min-w-0 overflow-hidden bg-slate-50">
        {/* Mobile top bar */}
        <div className="md:hidden flex items-center justify-between px-4 py-2.5 bg-white border-b border-slate-200 shadow-xs">
          <button
            onClick={() => setIsMobileMenuOpen(true)}
            aria-label="Mở danh mục điều hướng"
            className="p-1.5 text-slate-700 hover:text-slate-900 rounded-lg bg-slate-100 border border-slate-200"
          >
            <Menu className="w-5 h-5" />
          </button>
          <BrandLogo theme="light" compact height={32} href="/" />
          <div className="flex items-center gap-1.5 text-[11px] text-slate-600">
            <span
              className={`w-2 h-2 rounded-full ${
                health?.status === 'healthy'
                  ? 'bg-teal-500'
                  : health?.status === 'degraded'
                  ? 'bg-amber-500'
                  : 'bg-rose-500'
              }`}
            />
            <span className="text-[10px] uppercase font-mono font-semibold">
              {health?.status === 'healthy' ? 'Online' : 'Offline'}
            </span>
          </div>
        </div>

        <Header
          activeTab={activeTab}
          onNewChat={() => chatResetRef.current?.()}
          latestMeasurement={latestMeasurement}
          onLogout={() => {
            clearAccessToken();
            setUserProfile(null);
            setLatestMeasurement(null);
            setAuthenticated(false);
            setActiveTab('chat');
            setAuthEpoch((value) => value + 1);
          }}
        />

        <main className="flex-1 overflow-y-auto bg-slate-50">
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
          {activeTab === 'dev' && getAuthMode() === 'development' && <DevTools initialHealth={health} />}
        </main>
      </div>
    </div>
  );
}
