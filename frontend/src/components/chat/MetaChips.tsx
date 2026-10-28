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
    <div className="flex flex-wrap items-center gap-1.5 pt-2 mt-2 border-t border-slate-800/60 text-[11px] text-slate-400">
      {/* Latency chip */}
      {latency_ms !== undefined && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
          <Clock className="w-3 h-3 text-slate-400" />
          <span>{latency_ms} ms</span>
        </span>
      )}

      {/* Fast path badge */}
      {fast_path && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 font-medium">
          <Zap className="w-3 h-3 text-amber-400" />
          <span>Fast-Path: {fast_path}</span>
        </span>
      )}

      {/* Selected agents */}
      {selected_agents && selected_agents.length > 0 && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-500/10 border border-indigo-500/30 text-indigo-300">
          <Bot className="w-3 h-3 text-indigo-400" />
          <span>{selected_agents.join(', ')}</span>
        </span>
      )}

      {/* Personalization */}
      {personalization_used?.profile_loaded && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
          <UserCheck className="w-3 h-3 text-emerald-400" />
          <span>Cá nhân hóa InBody</span>
        </span>
      )}

      {/* Status warning if degraded */}
      {status === 'degraded' && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-500/10 border border-rose-500/30 text-rose-300">
          <AlertTriangle className="w-3 h-3 text-rose-400" />
          <span>Degraded fallback</span>
        </span>
      )}
    </div>
  );
}
