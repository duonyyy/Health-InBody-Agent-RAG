'use client';

import React from 'react';
import { Clock, Zap, Bot, UserCheck, AlertTriangle } from 'lucide-react';
import { ChatMessage } from '@/types';

interface MetaChipsProps {
  message: ChatMessage;
}

export default function MetaChips({ message }: MetaChipsProps) {
  const { latency_ms, fast_path, selected_agents, personalization_used, status } = message;

  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-2.5 mt-2.5 border-t border-slate-100 text-[11px] text-slate-500">
      {/* Latency chip */}
      {latency_ms !== undefined && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 font-mono">
          <Clock className="w-3 h-3 text-slate-500" />
          <span>{latency_ms} ms</span>
        </span>
      )}

      {/* Fast path badge */}
      {fast_path && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 border border-amber-300 text-amber-900 font-semibold">
          <Zap className="w-3 h-3 text-amber-600" />
          <span>Fast-Path: {fast_path}</span>
        </span>
      )}

      {/* Selected agents */}
      {selected_agents && selected_agents.length > 0 && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-50 border border-indigo-200 text-indigo-800 font-medium">
          <Bot className="w-3 h-3 text-indigo-600" />
          <span>{selected_agents.join(', ')}</span>
        </span>
      )}

      {/* Personalization */}
      {personalization_used?.profile_loaded && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-800 font-medium">
          <UserCheck className="w-3 h-3 text-emerald-600" />
          <span>Cá nhân hóa InBody</span>
        </span>
      )}

      {/* Status warning if degraded */}
      {status === 'degraded' && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-50 border border-rose-200 text-rose-800 font-medium">
          <AlertTriangle className="w-3 h-3 text-rose-600" />
          <span>Degraded fallback</span>
        </span>
      )}
    </div>
  );
}