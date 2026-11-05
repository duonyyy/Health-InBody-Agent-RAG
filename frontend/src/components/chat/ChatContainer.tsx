'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, Sparkles, PlusCircle } from 'lucide-react';
import { ChatMessage } from '@/types';
import MessageBubble from './MessageBubble';
import QuickPrompts from './QuickPrompts';
import { sendChatMessageApi } from '@/lib/api';

interface ChatContainerProps {
  initialMessages?: ChatMessage[];
  onRegisterReset?: (resetFn: () => void) => void;
  userDisplayName?: string;
}

export default function ChatContainer({
  initialMessages,
  onRegisterReset,
  userDisplayName = 'bạn',
}: ChatContainerProps) {
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [lastUserPrompt, setLastUserPrompt] = useState<string>('');
  const msgCounterRef = useRef(1);

  const getNextMsgId = useCallback((prefix: string) => {
    msgCounterRef.current += 1;
    return `${prefix}-${msgCounterRef.current}`;
  }, []);

  const createWelcomeMessage = useCallback(
    (): ChatMessage => ({
      id: 'msg-welcome',
      role: 'assistant',
      content:
        `👋 Xin chào **${userDisplayName}**! Tôi là **Trợ lý Sức khỏe & Thể trạng BodyWise (Agent RAG)**.\n\n` +
        'Tôi có thể đồng hành cùng bạn:\n' +
        '- 📊 **Đọc và giải nghĩa chỉ số InBody** (BMI, PBF, SMM, mỡ nội tạng theo chuẩn WPRO).\n' +
        '- 🥗 **Tư vấn dinh dưỡng thể trạng** dựa trên mục tiêu tăng cơ giảm mỡ và chế độ ăn.\n' +
        '- 🏋️ **Lên lịch tập kháng lực & cardio** an toàn theo khoa học vận động.\n' +
        '- 🚨 **Sàng lọc an toàn y tế** cảnh báo sớm dấu hiệu nguy hiểm tim mạch/hô hấp.\n\n' +
        '*Bạn muốn kiểm tra chỉ số InBody hay có thắc mắc gì hôm nay?*',
      timestamp: 'Hôm nay',
      selected_agents: ['greeter_node'],
    }),
    [userDisplayName]
  );

  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    if (initialMessages && initialMessages.length > 0) return initialMessages;
    return [createWelcomeMessage()];
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

  const handleSendMessage = useCallback(
    async (textToSend?: string) => {
      const text = (textToSend || input).trim();
      if (!text || isLoading) return;

      setLastUserPrompt(text);
      const userMessage: ChatMessage = {
        id: getNextMsgId('msg-user'),
        role: 'user',
        content: text,
        timestamp: 'Vừa xong',
      };

      setMessages((prev) => [...prev, userMessage]);
      setInput('');
      setIsLoading(true);

      try {
        const assistantResponse = await sendChatMessageApi(text, conversationId);

        // Cập nhật conversation_id do server cấp phát
        if (assistantResponse.conversation_id) {
          setConversationId(assistantResponse.conversation_id);
        }

        setMessages((prev) => [...prev, assistantResponse]);
      } catch (err: unknown) {
        const errorMsg =
          err instanceof Error
            ? err.message
            : 'Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại dịch vụ backend.';

        setMessages((prev) => [
          ...prev,
          {
            id: getNextMsgId('msg-err'),
            role: 'assistant',
            content: `⚠️ **Không thể hoàn tất phản hồi:**\n\n${errorMsg}\n\n*Hệ thống không tạo dữ liệu giả lập. Bạn có thể nhấn nút "Thử lại câu hỏi" bên dưới.*`,
            timestamp: 'Vừa xong',
            status: 'error',
            errors: [errorMsg],
          },
        ]);
      } finally {
        setIsLoading(false);
        if (textareaRef.current) {
          textareaRef.current.style.height = 'auto';
        }
      }
    },
    [input, isLoading, conversationId, getNextMsgId]
  );

  const handleResetChat = useCallback(() => {
    // Reset client session, conversationId = undefined để server tạo session mới ở lượt kế tiếp
    setConversationId(undefined);
    setMessages([
      {
        id: getNextMsgId('msg-welcome'),
        role: 'assistant',
        content:
          '👋 **Đã bắt đầu cuộc trò chuyện mới!**\n\n' +
          'Phiên hội thoại trước đã được lưu trên máy chủ theo phiên làm việc. Tôi sẵn sàng phân tích chỉ số InBody mới hoặc tư vấn câu hỏi sức khỏe tiếp theo của bạn.',
        timestamp: 'Vừa xong',
        selected_agents: ['greeter_node'],
      },
    ]);
  }, [getNextMsgId]);

  // Đăng ký hàm reset ra ngoài (cho nút Header)
  useEffect(() => {
    if (onRegisterReset) {
      onRegisterReset(handleResetChat);
    }
  }, [onRegisterReset, handleResetChat]);

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
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-5xl mx-auto w-full px-3 sm:px-6">
      {/* Scrollable messages container */}
      <div className="flex-1 overflow-y-auto py-5 pr-1 sm:pr-2">
        {messages.map((msg, index) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onRetry={
              msg.status === 'error' && index === messages.length - 1 && lastUserPrompt
                ? () => handleSendMessage(lastUserPrompt)
                : undefined
            }
          />
        ))}

        {/* Loading state indicator */}
        {isLoading && (
          <div className="flex items-start gap-3.5 mb-6 animate-pulse">
            <div className="w-9 h-9 rounded-xl bg-slate-900 border border-teal-500/30 flex items-center justify-center p-1.5 shadow-md shadow-teal-500/20">
              <Sparkles className="w-5 h-5 animate-spin text-teal-400" />
            </div>
            <div className="glass-card rounded-2xl rounded-tl-sm p-4 border border-slate-800/80 shadow-md">
              <div className="flex items-center gap-2 text-xs text-slate-300">
                <Loader2 className="w-4 h-4 animate-spin text-teal-400" />
                <span>Trợ lý Đa tác tử BodyWise đang xử lý & tra cứu kho tri thức...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="pb-4 pt-1">
        {messages.length <= 2 && (
          <QuickPrompts onSelectPrompt={(p) => handleSendMessage(p)} />
        )}

        <div className="relative glass-panel rounded-2xl border border-slate-800 focus-within:border-teal-500/60 focus-within:ring-2 focus-within:ring-teal-500/20 transition-all shadow-xl bg-slate-900/90 p-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Hỏi về chỉ số InBody, thực đơn dinh dưỡng, bài tập hoặc triệu chứng sức khỏe... (Enter để gửi, Shift+Enter xuống dòng)"
            rows={1}
            disabled={isLoading}
            className="w-full bg-transparent text-slate-100 placeholder-slate-500 text-sm px-3 py-2 focus:outline-none resize-none max-h-36 min-h-[44px]"
          />

          <div className="flex items-center justify-between px-3 pt-1 border-t border-slate-800/60 mt-1">
            <div className="flex items-center gap-2 sm:gap-3 text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
                <span className="hidden sm:inline">Kiểm soát An toàn Y tế Hoạt động</span>
                <span className="sm:hidden">An toàn Active</span>
              </span>
              {conversationId && (
                <span className="hidden md:inline font-mono text-[10px] text-slate-500">
                  ID: {conversationId.slice(0, 8)}
                </span>
              )}
              {messages.length > 2 && (
                <button
                  type="button"
                  onClick={handleResetChat}
                  className="flex items-center gap-1 text-slate-400 hover:text-teal-300 transition-colors ml-1 hover:bg-slate-800/80 px-2 py-0.5 rounded-lg"
                  title="Mở phiên hội thoại mới trên giao diện (Không xóa dữ liệu trên máy chủ)"
                >
                  <PlusCircle className="w-3 h-3 text-teal-400" />
                  <span>Đoạn chat mới</span>
                </button>
              )}
            </div>

            <button
              onClick={() => handleSendMessage()}
              disabled={!input.trim() || isLoading}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md ${
                input.trim() && !isLoading
                  ? 'bg-gradient-to-r from-teal-500 to-sky-500 text-slate-950 hover:brightness-110 shadow-teal-500/25 active:scale-95'
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
