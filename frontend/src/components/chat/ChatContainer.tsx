'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Sparkles, AlertCircle } from 'lucide-react';
import { ChatMessage } from '@/types';
import MessageBubble from './MessageBubble';
import QuickPrompts from './QuickPrompts';
import { sendChatMessageApi } from '@/lib/api';

interface ChatContainerProps {
  initialMessages?: ChatMessage[];
}

export default function ChatContainer({ initialMessages }: ChatContainerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    if (initialMessages && initialMessages.length > 0) return initialMessages;
    return [
      {
        id: 'msg-welcome',
        role: 'assistant',
        content:
          '👋 Xin chào **Nguyễn Minh Khoa**! Tôi là **Trợ lý Sức khỏe & Thể trạng InBody (Agent RAG)**.\n\n' +
          'Tôi có thể giúp bạn:\n' +
          '- 📊 **Đọc và giải nghĩa các chỉ số InBody** (BMI, PBF, SMM, mỡ nội tạng theo chuẩn WPRO).\n' +
          '- 🥗 **Tư vấn dinh dưỡng cá nhân hóa** dựa trên tiền sử dị ứng và mục tiêu thể trạng.\n' +
          '- 🏋️ **Xây dựng lịch tập kháng lực** an toàn, hiệu quả.\n' +
          '- 🚨 **Sàng lọc an toàn y tế** cảnh báo sớm triệu chứng nguy hiểm.\n\n' +
          '*Bạn muốn kiểm tra hay hỏi gì hôm nay?*',
        timestamp: 'Hôm nay',
        selected_agents: ['greeter_node'],
      },
    ];
  });

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || isLoading) return;

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Build history
      const history = messages.slice(-8).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const assistantResponse = await sendChatMessageApi(text, undefined, history);
      setMessages((prev) => [...prev, assistantResponse]);
    } catch (err) {
      console.error('Chat error:', err);
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-err-${Date.now()}`,
          role: 'assistant',
          content: '⚠️ Có lỗi xảy ra khi kết nối tới hệ thống. Vui lòng thử lại sau giây lát.',
          timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
          status: 'error',
        },
      ]);
    } finally {
      setIsLoading(false);
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4.5rem)] max-w-5xl mx-auto w-full px-4 sm:px-6">
      {/* Scrollable messages container */}
      <div className="flex-1 overflow-y-auto py-6 pr-2">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Loading state indicator */}
        {isLoading && (
          <div className="flex items-start gap-3.5 mb-6 animate-pulse">
            <div className="w-9 h-9 rounded-xl bg-slate-800 flex items-center justify-center text-emerald-400 border border-slate-700">
              <Sparkles className="w-5 h-5 animate-spin" />
            </div>
            <div className="glass-card rounded-2xl rounded-tl-sm p-4 border border-slate-800/80 shadow-md">
              <div className="flex items-center gap-2 text-xs text-slate-300">
                <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                <span>Multi-Agent đang phối hợp phân tích & tra cứu RAG...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="pb-6 pt-2">
        {messages.length <= 2 && (
          <QuickPrompts onSelectPrompt={(p) => handleSendMessage(p)} />
        )}

        <div className="relative glass-panel rounded-2xl border border-slate-800 focus-within:border-emerald-500/60 focus-within:ring-2 focus-within:ring-emerald-500/20 transition-all shadow-xl bg-slate-900/90 p-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Hỏi về chỉ số InBody, triệu chứng sức khỏe, thực đơn tăng cơ giảm mỡ... (Enter để gửi, Shift+Enter xuống dòng)"
            rows={1}
            disabled={isLoading}
            className="w-full bg-transparent text-slate-100 placeholder-slate-500 text-sm px-3 py-2 focus:outline-none resize-none max-h-36 min-h-[44px]"
          />

          <div className="flex items-center justify-between px-3 pt-1 border-t border-slate-800/60 mt-1">
            <div className="flex items-center gap-2 text-[11px] text-slate-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span>Safety Pre-check Active</span>
            </div>

            <button
              onClick={() => handleSendMessage()}
              disabled={!input.trim() || isLoading}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md ${
                input.trim() && !isLoading
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-400 text-slate-950 hover:brightness-110 shadow-emerald-500/25 active:scale-95'
                  : 'bg-slate-800 text-slate-400 cursor-not-allowed'
              }`}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Đang xử lý</span>
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  <span>Gửi tin</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
