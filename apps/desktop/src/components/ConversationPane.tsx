import React, { useState, useEffect, useRef } from "react";
import { Send, Square, Bot, User, Sparkles } from "lucide-react";
import { RoutingBadge } from "./RoutingBadge";

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  role?: string;
  model?: string;
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

const ROLE_TINT_BORDERS: Record<string, string> = {
  planner: "border-l-[#6366F1]",
  coder: "border-l-[#8B5CF6]",
  vision: "border-l-[#06B6D4]",
  writer: "border-l-[#8B5CF6]",
};

export const ConversationPane: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [selectedRole, setSelectedRole] = useState("writer");
  const [activeStreamId, setActiveStreamId] = useState<number | null>(null);

  const pendingTokensRef = useRef<{
    [msgId: string]: { deltaContent: string; deltaThinking: string; role?: string; model?: string };
  }>({});
  const rafIdRef = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Set up Tauri event listeners for streaming tokens & completions
  useEffect(() => {
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!isTauri) return;

    let unlistenToken: (() => void) | undefined;
    let unlistenComplete: (() => void) | undefined;
    let unlistenInterrupt: (() => void) | undefined;

    const setupListeners = async () => {
      const { listen } = await import("@tauri-apps/api/event");

      unlistenToken = await listen<{
        id: number;
        role: string;
        model: string;
        delta: string;
        thinking_delta: string;
        content: string;
        thinking: string;
      }>("chat-token-received", (event) => {
        const { id, role, model, delta, thinking_delta, content, thinking } = event.payload;
        const msgIdStr = String(id);

        if (!pendingTokensRef.current[msgIdStr]) {
          pendingTokensRef.current[msgIdStr] = {
            deltaContent: content || delta || "",
            deltaThinking: thinking || thinking_delta || "",
            role,
            model,
          };
        } else {
          if (content) {
            pendingTokensRef.current[msgIdStr].deltaContent = content;
          } else {
            pendingTokensRef.current[msgIdStr].deltaContent += delta || "";
          }
          if (thinking) {
            pendingTokensRef.current[msgIdStr].deltaThinking = thinking;
          } else {
            pendingTokensRef.current[msgIdStr].deltaThinking += thinking_delta || "";
          }
        }

        // Schedule token coalescing via requestAnimationFrame (~16ms)
        if (rafIdRef.current === null) {
          rafIdRef.current = requestAnimationFrame(() => {
            rafIdRef.current = null;
            const updates = pendingTokensRef.current;
            pendingTokensRef.current = {};

            setMessages((prev) =>
              prev.map((msg) => {
                const u = updates[msg.id];
                if (u) {
                  return {
                    ...msg,
                    content: u.deltaContent,
                    thinking: u.deltaThinking,
                    role: u.role || msg.role,
                    model: u.model || msg.model,
                    isStreaming: true,
                  };
                }
                return msg;
              })
            );
          });
        }
      });

      unlistenComplete = await listen<{
        id: number;
        result: {
          role: string;
          model: string;
          content: string;
          thinking: string;
          metrics?: Record<string, number>;
        };
      }>("chat-stream-completed", (event) => {
        const { id, result } = event.payload;
        const msgIdStr = String(id);

        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.id === msgIdStr) {
              return {
                ...msg,
                content: result.content,
                thinking: result.thinking,
                role: result.role,
                model: result.model,
                metrics: result.metrics,
                isStreaming: false,
              };
            }
            return msg;
          })
        );
        setActiveStreamId(null);
      });

      unlistenInterrupt = await listen<{ id?: number; reason?: string }>(
        "chat-stream-interrupted",
        (event) => {
          const targetId = event.payload.id ? String(event.payload.id) : null;
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.isStreaming && (!targetId || msg.id === targetId)) {
                return { ...msg, isStreaming: false, interrupted: true };
              }
              return msg;
            })
          );
          setActiveStreamId(null);
        }
      );
    };

    setupListeners();

    return () => {
      if (unlistenToken) unlistenToken();
      if (unlistenComplete) unlistenComplete();
      if (unlistenInterrupt) unlistenInterrupt();
      if (rafIdRef.current !== null) cancelAnimationFrame(rafIdRef.current);
    };
  }, []);

  const handleSend = async () => {
    if (!inputText.trim() || activeStreamId !== null) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      content: inputText.trim(),
    };

    const currentRole = selectedRole;
    setInputText("");
    setMessages((prev) => [...prev, userMsg]);

    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

    if (!isTauri) {
      // Demo streaming fallback for browser dev
      const assistantId = `assistant-${Date.now()}`;
      const assistantMsg: ChatMessage = {
        id: assistantId,
        sender: "assistant",
        role: currentRole,
        model: "resolving...",
        content: "Browser mock mode: stdio RPC requires Tauri runtime.",
        isStreaming: false,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      return;
    }

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const apiMessages = [...messages, userMsg].map((m) => ({
        role: m.sender,
        content: m.content,
      }));

      const streamId = await invoke<number>("send_chat_message", {
        role: currentRole,
        messages: apiMessages,
      });

      setActiveStreamId(streamId);

      const assistantMsg: ChatMessage = {
        id: String(streamId),
        sender: "assistant",
        role: currentRole,
        model: "resolving...",
        content: "",
        thinking: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error("Failed to send chat message:", err);
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: "assistant",
        role: currentRole,
        model: "error",
        content: `Error invoking chat stream: ${String(err)}`,
        isStreaming: false,
        interrupted: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  };

  const handleStop = async () => {
    if (activeStreamId === null) return;
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("cancel_chat_stream", { streamId: activeStreamId });
    } catch (err) {
      console.error("Failed to stop chat stream:", err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-bg text-text overflow-hidden">
      {/* Messages Scroll Viewport */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-text-dim space-y-2 select-none">
            <Bot className="w-8 h-8 text-accent opacity-60" />
            <div className="font-mono text-xs font-semibold text-text">SWARAJ Model Router Console</div>
            <p className="text-xs max-w-sm text-text-faint">
              Select a role below and submit a prompt. Streaming inference runs on local Ollama via stdio sidecar.
            </p>
          </div>
        ) : (
          messages.map((msg) => {
            if (msg.sender === "user") {
              return (
                <div
                  key={msg.id}
                  className="bg-surface-2 border border-border border-l-[3px] border-l-[#6B7A8A] rounded p-3 text-xs text-text space-y-1"
                >
                  <div className="flex items-center gap-1.5 font-mono text-[11px] text-text-faint select-none">
                    <User className="w-3.5 h-3.5 text-text-dim" />
                    <span>USER</span>
                  </div>
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                </div>
              );
            }

            const borderClass = ROLE_TINT_BORDERS[msg.role?.toLowerCase() || "writer"] || "border-l-[#8B5CF6]";

            return (
              <div
                key={msg.id}
                className={`bg-transparent border-t border-b border-r border-border border-l-[2px] ${borderClass} rounded p-3 text-xs text-text space-y-2`}
              >
                {/* Header with Routing Badge */}
                <div className="flex items-center justify-between select-none">
                  <div className="flex items-center gap-2">
                    <Bot className="w-3.5 h-3.5 text-text-dim" />
                    {msg.role && msg.model && (
                      <RoutingBadge
                        role={msg.role}
                        model={msg.model}
                        latencySeconds={
                          msg.metrics?.eval_duration ? msg.metrics.eval_duration / 1e9 : undefined
                        }
                      />
                    )}
                  </div>
                  {msg.isStreaming && (
                    <span className="font-mono text-[10px] text-accent animate-pulse">STREAMING...</span>
                  )}
                  {msg.interrupted && (
                    <span className="font-mono text-[10px] text-critical px-1.5 py-0.5 bg-critical/10 rounded border border-critical/30">
                      INTERRUPTED
                    </span>
                  )}
                </div>

                {/* Thinking Disclosure */}
                {msg.thinking && msg.thinking.trim().length > 0 && (
                  <details className="group border border-border/50 rounded bg-surface/50 p-2">
                    <summary className="cursor-pointer text-text-faint hover:text-text-dim text-[11px] select-none font-mono flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-text-faint" />
                      <span>Thinking Process</span>
                    </summary>
                    <div className="mt-2 font-mono text-[11px] text-text-faint whitespace-pre-wrap leading-relaxed border-t border-border/40 pt-2">
                      {msg.thinking}
                    </div>
                  </details>
                )}

                {/* Main Content */}
                <div className="whitespace-pre-wrap text-text leading-relaxed">
                  {msg.content || (msg.isStreaming ? "..." : "")}
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Task Composer Bar */}
      <div className="p-3 bg-surface border-t border-border flex flex-col gap-2">
        <div className="flex items-center justify-between font-mono text-[11px]">
          <div className="flex items-center gap-2 text-text-dim">
            <span>TARGET ROLE:</span>
            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
              className="bg-surface-2 border border-border rounded px-2 py-0.5 text-text font-mono text-xs focus:outline-none focus:border-accent cursor-pointer"
            >
              <option value="planner">planner (Planner Indigo)</option>
              <option value="coder">coder (Coder Violet)</option>
              <option value="vision">vision (Vision Cyan)</option>
              <option value="writer">writer (Writer Violet)</option>
            </select>
          </div>
          <span className="text-text-faint">Press Cmd+Enter or Ctrl+Enter to send</span>
        </div>

        <div className="flex items-end gap-2">
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter prompt or operational query..."
            rows={2}
            className="flex-1 bg-surface-2 border border-border rounded p-2 text-xs text-text placeholder-text-faint resize-none focus:outline-none focus:border-accent font-sans"
          />

          {activeStreamId !== null ? (
            <button
              onClick={handleStop}
              className="px-3 py-2 bg-critical/20 border border-critical/40 text-critical rounded font-mono text-xs font-semibold hover:bg-critical/30 flex items-center gap-1.5 transition-colors cursor-pointer select-none shrink-0"
            >
              <Square className="w-3.5 h-3.5 fill-critical" />
              Stop
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!inputText.trim()}
              className="px-3 py-2 bg-accent/20 border border-accent/40 text-accent disabled:opacity-40 disabled:cursor-not-allowed rounded font-mono text-xs font-semibold hover:bg-accent/30 flex items-center gap-1.5 transition-colors cursor-pointer select-none shrink-0"
            >
              <Send className="w-3.5 h-3.5" />
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
