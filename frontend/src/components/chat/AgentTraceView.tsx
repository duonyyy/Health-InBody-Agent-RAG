'use client';

import React, { useState } from 'react';
import { GitCommit, ChevronDown, ChevronUp, Clock } from 'lucide-react';
import { AgentTraceStep } from '@/types';

interface AgentTraceViewProps {
  trace: AgentTraceStep[];
}

export default function AgentTraceView({ trace }: AgentTraceViewProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (!trace || trace.length === 0) return null;

  const totalTime = trace.reduce((acc, step) => acc + (step.duration_ms || 0), 0);

  return (
    <div className="mt-3 border border-slate-800 rounded-xl overflow-hidden bg-slate-950/60">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3.5 py-2 flex items-center justify-between text-xs text-slate-300 hover:text-slate-100 hover:bg-slate-900/60 transition-colors"
      >
        <div className="flex items-center gap-2">
          <GitCommit className="w-3.5 h-3.5 text-indigo-400" />
          <span className="font-medium">Luồng thực thi Multi-Agent ({trace.length} bước)</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
            {totalTime} ms
          </span>
        </div>
        {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {isOpen && (
        <div className="p-3.5 border-t border-slate-800 bg-slate-950/90 text-xs space-y-3">
          <div className="relative pl-6 space-y-3 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
            {trace.map((step, idx) => (
              <div key={idx} className="relative group">
                {/* Dot */}
                <div className="absolute -left-6 top-1 w-2.5 h-2.5 rounded-full bg-indigo-500 border-2 border-slate-950 group-hover:scale-125 transition-transform" />

                <div className="flex items-center justify-between gap-2">
                  <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                    <span className="text-emerald-400 font-mono text-[11px]">
                      {step.node || `Node ${idx + 1}`}
                    </span>
                    {step.agent && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800/60">
                        {step.agent}
                      </span>
                    )}
                  </div>
                  {step.duration_ms !== undefined && (
                    <div className="flex items-center gap-1 text-[10px] text-slate-400">
                      <Clock className="w-3 h-3 text-slate-400" />
                      <span>{step.duration_ms} ms</span>
                    </div>
                  )}
                </div>

                {step.action && (
                  <p className="text-[11px] text-slate-400 mt-0.5 leading-snug">
                    {step.action}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
