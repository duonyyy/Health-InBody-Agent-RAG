'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { HeartPulse, User, Copy, Check } from 'lucide-react';
import { ChatMessage } from '@/types';
import SafetyBanner from './SafetyBanner';
import MetaChips from './MetaChips';
import AgentTraceView from './AgentTraceView';
import CitationsView from './CitationsView';

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isUser) {
    return (
      <div className="flex justify-end gap-3 mb-5 group">
        <div className="max-w-2xl">
          <div className="px-4 py-3 rounded-2xl rounded-tr-sm bg-gradient-to-tr from-indigo-600 to-indigo-500 text-white shadow-lg shadow-indigo-600/20 text-sm leading-relaxed">
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
          <div className="text-[10px] text-slate-500 text-right mt-1 px-1">
            {message.timestamp}
          </div>
        </div>

        <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 flex-shrink-0 text-xs font-semibold">
          <User className="w-4 h-4" />
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="flex items-start gap-3.5 mb-6 group">
      <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center text-slate-950 flex-shrink-0 shadow-md shadow-emerald-500/20 font-bold">
        <HeartPulse className="w-5 h-5 stroke-[2.2]" />
      </div>

      <div className="flex-1 max-w-3xl min-w-0">
        <div className="glass-card rounded-2xl rounded-tl-sm p-4 border border-slate-800/80 shadow-md relative group/box">
          {/* Copy button */}
          <button
            onClick={handleCopy}
            className="absolute top-3 right-3 p-1.5 rounded-lg bg-slate-800/60 hover:bg-slate-700 text-slate-400 hover:text-slate-200 opacity-0 group-hover/box:opacity-100 transition-opacity"
            title="Sao chép nội dung"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>

          {/* Safety alert banner if any */}
          {message.safety_result && <SafetyBanner safety={message.safety_result} />}

          {/* Markdown Content */}
          <div className="prose-chat">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Citations */}
          {message.citations && message.citations.length > 0 && (
            <CitationsView citations={message.citations} />
          )}

          {/* Collapsible Agent Trace */}
          {message.agent_trace && message.agent_trace.length > 0 && (
            <AgentTraceView trace={message.agent_trace} />
          )}

          {/* Meta Chips */}
          <MetaChips message={message} />
        </div>

        <div className="text-[10px] text-slate-500 mt-1 px-1 flex items-center gap-2">
          <span>{message.timestamp}</span>
          <span>•</span>
          <span className="text-emerald-500/80 font-medium">Health/InBody Agent RAG</span>
        </div>
      </div>
    </div>
  );
}
