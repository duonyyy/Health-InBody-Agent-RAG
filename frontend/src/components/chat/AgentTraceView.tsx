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
    <div className="mt-3 border border-slate-200 rounded-xl overflow-hidden bg-slate-50">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3.5 py-2 flex items-center justify-between text-xs text-slate-700 hover:text-slate-900 hover:bg-slate-100/80 transition-colors font-medium"
      >
        <div className="flex items-center gap-2">
          <GitCommit className="w-3.5 h-3.5 text-indigo-600" />
          <span>Luồng thực thi Multi-Agent ({trace.length} bước)</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white text-slate-600 border border-slate-200 font-mono font-semibold">
            {totalTime} ms
          </span>
        </div>
        {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {isOpen && (
        <div className="p-3.5 border-t border-slate-200 bg-white text-xs space-y-3">
          <div className="relative pl-6 space-y-3 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
            {trace.map((step, idx) => (
              <div key={idx} className="relative group">
                {/* Dot */}
                <div className="absolute -left-6 top-1 w-2.5 h-2.5 rounded-full bg-indigo-600 border-2 border-white shadow-xs group-hover:scale-125 transition-transform" />

                <div className="flex items-center justify-between gap-2">
                  <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                    <span className="text-teal-700 font-mono text-[11px]">
                      {step.node || `Node ${idx + 1}`}
                    </span>
                    {step.agent && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 font-medium">
                        {step.agent}
                      </span>
                    )}
                  </div>
                  {step.duration_ms !== undefined && (
                    <div className="flex items-center gap-1 text-[10px] text-slate-500 font-mono">
                      <Clock className="w-3 h-3 text-slate-400" />
                      <span>{step.duration_ms} ms</span>
                    </div>
                  )}
                </div>

                {step.action && (
                  <p className="text-[11px] text-slate-600 mt-0.5 leading-snug">
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