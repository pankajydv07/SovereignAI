import React, { useState } from "react";
import { Bot, User, Sparkles, Copy, Check } from "lucide-react";
import { MarkdownContent } from "./MarkdownContent";

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  role?: string;
  model?: string;
  taskClass?: string;
  content: string;
  thinking?: string;
  isStreaming?: boolean;
  interrupted?: boolean;
  metrics?: {
    total_duration?: number;
    eval_duration?: number;
    eval_count?: number;
  };
}

export interface MessageItemProps {
  msg: ChatMessage;
}

export const MessageItem: React.FC<MessageItemProps> = ({ msg }) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const isUser = msg.sender === "user";

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div
      className={`p-3 rounded-[4px] border ${
        isUser
          ? "bg-[#121821] border-[#263241] ml-8"
          : "bg-[#0B0F14] border-[#263241] mr-8 border-l-2 border-l-[#4C8DF6]"
      } space-y-2`}
    >
      <div className="flex items-center justify-between select-none">
        <div className="flex items-center gap-2">
          {isUser ? (
            <User className="w-3.5 h-3.5 text-[#8B949E]" />
          ) : (
            <Bot className="w-3.5 h-3.5 text-[#4C8DF6]" />
          )}
          {!isUser && msg.model && (
            <span className="font-mono text-[11px] text-[#8B949E]">
              {msg.model}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {msg.isStreaming && (
            <span className="font-mono text-[10px] text-[#4C8DF6] animate-pulse">
              STREAMING...
            </span>
          )}
          {msg.interrupted && (
            <span className="font-mono text-[10px] text-[#EF4444] px-1.5 py-0.5 bg-[#EF4444]/10 rounded-[4px] border border-[#EF4444]/30">
              INTERRUPTED
            </span>
          )}
          {msg.content && (
            <button
              type="button"
              onClick={() => handleCopy(msg.content, `msg-${msg.id}`)}
              className="p-1 hover:bg-[#263241] rounded text-[#8B949E] hover:text-[#E6EDF3] transition-colors cursor-pointer"
              title="Copy message"
            >
              {copiedId === `msg-${msg.id}` ? (
                <Check className="w-3 h-3 text-[#10B981]" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
            </button>
          )}
        </div>
      </div>

      {msg.thinking && msg.thinking.trim().length > 0 && (
        <details className="group border border-[#263241] rounded-[4px] bg-[#121821] p-2">
          <summary className="cursor-pointer text-[#8B949E] text-[11px] font-mono flex items-center justify-between">
            <div className="flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-[#8B949E]" />
              <span>Thinking Process</span>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleCopy(msg.thinking || "", `think-${msg.id}`);
              }}
              className="px-1.5 py-0.5 hover:bg-[#263241] rounded text-[#8B949E] hover:text-[#E6EDF3] transition-colors flex items-center gap-1 cursor-pointer"
              title="Copy thinking"
            >
              {copiedId === `think-${msg.id}` ? (
                <>
                  <Check className="w-2.5 h-2.5 text-[#10B981]" />
                  <span className="text-[10px] text-[#10B981]">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-2.5 h-2.5" />
                  <span className="text-[10px]">Copy</span>
                </>
              )}
            </button>
          </summary>
          <div className="mt-2 font-mono text-[11px] text-[#8B949E] whitespace-pre-wrap leading-relaxed border-t border-[#263241] pt-2 select-text">
            {msg.thinking}
          </div>
        </details>
      )}

      {msg.content ? (
        <MarkdownContent content={msg.content} />
      ) : msg.isStreaming ? (
        <div className="text-[13px] text-[#8B949E] font-mono animate-pulse">...</div>
      ) : null}
    </div>
  );
};
