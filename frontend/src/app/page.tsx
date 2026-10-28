'use client';

import React, { useState, useEffect } from 'react';
import Sidebar, { TabType } from '@/components/layout/Sidebar';
import Header from '@/components/layout/Header';
import ChatContainer from '@/components/chat/ChatContainer';
import InBodyDashboard from '@/components/inbody/InBodyDashboard';
import ProfileAndGoals from '@/components/profile/ProfileAndGoals';
import CorpusSearch from '@/components/search/CorpusSearch';
import DevTools from '@/components/dev/DevTools';
import { BackendHealth } from '@/types';
import { checkBackendHealth } from '@/lib/api';
import { Menu, X } from 'lucide-react';

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabType>('chat');
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Initial health check & polling
  useEffect(() => {
    let mounted = true;
    const updateHealth = async () => {
      try {
        const res = await checkBackendHealth();
        if (mounted) setHealth(res);
      } catch (err) {
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

  return (
    <div className="flex h-screen bg-[#070b14] text-slate-100 overflow-hidden font-sans">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex">
        <Sidebar
          activeTab={activeTab}
          setActiveTab={(tab) => {
            setActiveTab(tab);
            setIsMobileMenuOpen(false);
          }}
          health={health}
          userName="Nguyễn Minh Khoa"
        />
      </div>

      {/* Mobile Drawer */}
      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div className="relative z-10 w-72 h-full">
            <Sidebar
              activeTab={activeTab}
              setActiveTab={(tab) => {
                setActiveTab(tab);
                setIsMobileMenuOpen(false);
              }}
              health={health}
              userName="Nguyễn Minh Khoa"
            />
          </div>
          <button
            onClick={() => setIsMobileMenuOpen(false)}
            className="absolute top-4 right-4 z-20 p-2 text-slate-300 hover:text-white rounded-lg bg-slate-900 border border-slate-700"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen min-w-0 overflow-hidden">
        {/* Mobile menu trigger */}
        <div className="md:hidden flex items-center justify-between px-4 py-2 bg-slate-950 border-b border-slate-800">
          <button
            onClick={() => setIsMobileMenuOpen(true)}
            className="p-1.5 text-slate-300 hover:text-white rounded-lg bg-slate-900 border border-slate-800"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="font-bold text-sm text-slate-100">Health / InBody AI</span>
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
        </div>

        <Header activeTab={activeTab} />

        <main className="flex-1 overflow-y-auto bg-gradient-to-b from-[#090d16] to-[#060910]">
          {activeTab === 'chat' && <ChatContainer />}
          {activeTab === 'inbody' && <InBodyDashboard />}
          {activeTab === 'profile' && <ProfileAndGoals />}
          {activeTab === 'search' && <CorpusSearch />}
          {activeTab === 'dev' && <DevTools initialHealth={health} />}
        </main>
      </div>
    </div>
  );
}
