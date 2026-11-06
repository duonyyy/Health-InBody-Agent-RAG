'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Copy, Check, RotateCw, AlertTriangle } from 'lucide-react';
import { ChatMessage } from '@/types';
import SafetyBanner from './SafetyBanner';
import MetaChips from './MetaChips';
import AgentTraceView from './AgentTraceView';
import CitationsView from './CitationsView';

interface MessageBubbleProps {
  message: ChatMessage;
  onRetry?: () => void;
}

export default function MessageBubble({ message, onRetry }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';
  const isError = message.status === 'error';
  const isDegraded = message.status === 'degraded';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isUser) {
    return (
      <div className="flex justify-end gap-3 mb-5 group">
        <div className="max-w-2xl">
          <div className="px-4 py-3 rounded-2xl rounded-tr-sm bg-gradient-to-tr from-teal-600 to-sky-600 text-white shadow-md text-sm leading-relaxed font-medium">
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
          <div className="text-[10px] text-slate-500 text-right mt-1 px-1 font-mono">
            {message.timestamp}
          </div>
        </div>

        <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-300 flex items-center justify-center text-slate-700 flex-shrink-0 text-xs font-bold shadow-xs">
          <User className="w-4 h-4" />
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="flex items-start gap-3.5 mb-6 group">
      <div className="w-9 h-9 rounded-xl bg-white border border-teal-200 flex items-center justify-center p-1.5 shadow-sm flex-shrink-0">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/brand/logo-mark.svg"
          alt="BodyWise AI"
          className="w-full h-full object-contain"
        />
      </div>

      <div className="flex-1 max-w-3xl min-w-0">
        <div
          className={`rounded-2xl rounded-tl-sm p-4 border shadow-sm relative group/box ${
            isError
              ? 'border-rose-200 bg-rose-50/70 text-rose-950'
              : isDegraded
              ? 'border-amber-200 bg-amber-50/60 text-amber-950'
              : 'border-slate-200 bg-white text-slate-800'
          }`}
        >
          {/* Copy button */}
          <button
            onClick={handleCopy}
            className="absolute top-3 right-3 p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-800 opacity-0 group-hover/box:opacity-100 transition-opacity border border-slate-200"
            title="Sao chép nội dung"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-teal-600" /> : <Copy className="w-3.5 h-3.5" />}
          </button>

          {/* Degraded mode pill */}
          {isDegraded && (
            <div className="mb-3 px-3 py-1.5 rounded-xl bg-amber-100 border border-amber-300 text-[11px] text-amber-900 font-medium flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
              <span>
                Phản hồi trong trạng thái dịch vụ suy giảm ({message.limitations?.join(', ') || 'Chưa nạp đủ ngữ cảnh bộ nhớ'}).
              </span>
            </div>
          )}

          {/* Safety alert banner if any */}
          {message.safety_result && <SafetyBanner safety={message.safety_result} />}

          {/* Markdown Content */}
          <div className="prose-chat">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Retry button on error */}
          {isError && onRetry && (
            <div className="mt-3 pt-3 border-t border-rose-200 flex justify-end">
              <button
                onClick={onRetry}
                className="px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <RotateCw className="w-3.5 h-3.5" />
                <span>Thử lại câu hỏi</span>
              </button>
            </div>
          )}

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

        <div className="text-[10px] text-slate-500 mt-1.5 px-1 flex items-center gap-2 font-medium">
          <span>{message.timestamp}</span>
          <span>•</span>
          <span className="text-teal-700 font-semibold">BodyWise AI Agent RAG</span>
          {message.conversation_id && (
            <>
              <span>•</span>
              <span className="font-mono text-slate-400 truncate max-w-[140px]">
                Phiên: {message.conversation_id.slice(0, 8)}...
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}