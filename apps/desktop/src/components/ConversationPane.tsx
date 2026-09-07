import React, { useState, useEffect, useRef } from "react";
import { Send, Square, Bot, Paperclip, X } from "lucide-react";
import { ApprovalCard, PermissionOption } from "./ApprovalCard";
import { PlanCard, PlanStepItem } from "./PlanCard";
import { MessageItem, ChatMessage } from "./MessageItem";
import { useChatStreamListeners } from "./useChatStreamListeners";
import { useSessionHistory } from "./useSessionHistory";

export interface ActivePermissionRequest {
  requestId: string;
  tool: string;
  sideEffect: string;
  description: string;
  resource?: string;
  resourcePattern?: string;
  options: PermissionOption[];
}

import { ProjectInfo } from "../protocol";

export interface ConversationPaneProps {
  activeProject?: ProjectInfo | null;
  activeSessionId?: string | null;
}

export const ConversationPane: React.FC<ConversationPaneProps> = ({
  activeProject,
  activeSessionId,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [planFirst, setPlanFirst] = useState(false);
  const [activeStreamId, setActiveStreamId] = useState<number | null>(null);
  const [fallbackSessionId] = useState<string>(() => `session-${Date.now()}`);
  const currentSessionId = activeSessionId || fallbackSessionId;
  const [activeRouting, setActiveRouting] = useState<{
    modelTag: string;
    taskClass: string;
    confidence: number;
  } | null>(null);

  const [pendingPermission, setPendingPermission] =
    useState<ActivePermissionRequest | null>(null);
  const [activePlanSteps, setActivePlanSteps] = useState<PlanStepItem[] | null>(
    null
  );
  const [attachments, setAttachments] = useState<
    Array<{ name: string; path: string }>
  >([]);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const userScrolledUpRef = useRef(false);

  const handleAttachFile = async () => {
    const isTauri =
      typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const filePath = await invoke<string | null>("select_file");
        if (filePath) {
          const fileName = filePath.split(/[/\\]/).pop() || filePath;
          setAttachments((prev) => [
            ...prev,
            { name: fileName, path: filePath },
          ]);
        }
      } catch (err) {
        console.error("Failed to select file:", err);
      }
    }
  };

  const handleRemoveAttachment = (idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    userScrolledUpRef.current = !isNearBottom;
  };

  useEffect(() => {
    if (!userScrolledUpRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, pendingPermission, activePlanSteps]);

  useSessionHistory({
    activeSessionId,
    activeProject,
    setMessages,
    setActiveRouting,
    setActivePlanSteps,
  });

  useChatStreamListeners({
    setMessages,
    setActiveRouting,
    setPendingPermission,
    setActivePlanSteps,
    setActiveStreamId,
  });

  const handleSend = async () => {
    if (!inputText.trim() || activeStreamId !== null) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      content: inputText.trim(),
    };

    setInputText("");
    setMessages((prev) => [...prev, userMsg]);

    const isTauri =
      typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

    if (!isTauri) {
      const assistantId = `assistant-${Date.now()}`;
      const assistantMsg: ChatMessage = {
        id: assistantId,
        sender: "assistant",
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
        params: {
          messages: apiMessages,
          attachments: attachments.map((a) => ({
            name: a.name,
            filename: a.name,
            path: a.path,
          })),
          planFirst,
          projectId: activeProject?.id || "default-project",
          projectPath: activeProject?.path || undefined,
          sessionId: currentSessionId,
        },
      });

      setAttachments([]);
      setActiveStreamId(streamId);
      userScrolledUpRef.current = false;
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });

      const assistantMsg: ChatMessage = {
        id: String(streamId),
        sender: "assistant",
        model: "routing...",
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
        model: "error",
        content: `Error invoking chat stream: ${String(err)}`,
        isStreaming: false,
        interrupted: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  };

  const handlePermissionRespond = async (
    requestId: string,
    option: PermissionOption,
    chosenPattern?: string
  ) => {
    const isTauri =
      typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("respond_permission", {
          requestId,
          selectedOption: option,
          resourcePattern: chosenPattern,
        });
      } catch (err) {
        console.error("Failed to respond to permission request:", err);
      }
    }
    setPendingPermission(null);
  };

  const handleRunPlan = async () => {
    if (!activePlanSteps || activePlanSteps.length === 0) return;
    const isTauri =
      typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const streamId = await invoke<number>("run_plan", {
          sessionId: currentSessionId,
          projectId: activeProject?.id || "default-project",
          projectPath: activeProject?.path || undefined,
          steps: activePlanSteps,
        });

        setActiveStreamId(streamId);
        setActivePlanSteps(null);

        const assistantMsg: ChatMessage = {
          id: String(streamId),
          sender: "assistant",
          model: "executing plan...",
          content: "",
          thinking: "",
          isStreaming: true,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        userScrolledUpRef.current = false;
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      } catch (err) {
        console.error("Failed to execute plan:", err);
      }
    }
  };

  const handleStop = async () => {
    if (activeStreamId === null) return;
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("cancel_chat_stream", { streamId: activeStreamId });
      setActiveStreamId(null);
      setPendingPermission(null);
    } catch (err) {
      console.error("Failed to cancel chat stream:", err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#0B0F14] border-r border-[#263241] text-[13px] text-[#E6EDF3] font-sans">
      {/* Dynamic Header with Routing Status */}
      <div className="px-4 py-2 bg-[#121821] border-b border-[#263241] flex items-center justify-between font-mono text-[12px]">
        <div className="flex items-center gap-2">
          <span className="font-bold text-[#4C8DF6]">CONVERSATION</span>
          {activeRouting && (
            <span className="px-2 py-0.5 bg-[#263241] rounded-[4px] text-[#10B981] text-[11px]">
              [{activeRouting.modelTag} •{" "}
              {Math.round(activeRouting.confidence * 100)}% •{" "}
              {activeRouting.taskClass}]
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 cursor-pointer text-[12px] select-none text-[#8B949E]">
            <input
              type="checkbox"
              checked={planFirst}
              onChange={(e) => setPlanFirst(e.target.checked)}
              className="rounded-[2px] bg-[#0B0F14] border-[#263241] text-[#4C8DF6] focus:ring-0"
            />
            <span>Plan first</span>
          </label>
        </div>
      </div>

      {/* Messages Scroll View */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-4"
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-[#8B949E] space-y-2">
            <Bot className="w-8 h-8 text-[#263241]" />
            <p className="font-mono text-[12px]">SWARAJ AIR-GAPPED WORKBENCH</p>
            <p className="text-[12px]">
              All queries routed dynamically to local models.
            </p>
          </div>
        ) : (
          messages.map((msg) => <MessageItem key={msg.id} msg={msg} />)
        )}

        {/* Inline Structured Execution Plan Card */}
        {activePlanSteps && activePlanSteps.length > 0 && (
          <PlanCard
            steps={activePlanSteps}
            onRunPlan={handleRunPlan}
            onCancelPlan={() => setActivePlanSteps(null)}
          />
        )}

        {/* Inline Permission Request Card */}
        {pendingPermission && (
          <ApprovalCard
            requestId={pendingPermission.requestId}
            tool={pendingPermission.tool}
            sideEffect={pendingPermission.sideEffect}
            description={pendingPermission.description}
            resource={pendingPermission.resource}
            resourcePattern={pendingPermission.resourcePattern}
            onRespond={handlePermissionRespond}
          />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Composer Footer */}
      <div className="p-3 bg-[#121821] border-t border-[#263241] flex flex-col gap-2">
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pb-1">
            {attachments.map((att, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-[#1B2431] border border-[#263241] rounded-[4px] font-mono text-[11px] text-[#4C8DF6]"
              >
                <Paperclip className="w-3 h-3 text-[#8B949E]" />
                <span className="truncate max-w-[180px]" title={att.path}>
                  {att.name}
                </span>
                <button
                  type="button"
                  onClick={() => handleRemoveAttachment(idx)}
                  className="hover:text-[#EF4444] transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2">
          <button
            type="button"
            onClick={handleAttachFile}
            title="Attach document/file for context"
            className="p-2 text-[#8B949E] hover:text-[#E6EDF3] bg-[#0B0F14] border border-[#263241] rounded-[4px] transition-colors shrink-0"
          >
            <Paperclip className="w-4 h-4" />
          </button>
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter prompt or operational query..."
            rows={2}
            className="flex-1 bg-[#0B0F14] border border-[#263241] rounded-[4px] p-2 text-[13px] text-[#E6EDF3] placeholder-[#8B949E] resize-none focus:outline-none focus:border-[#4C8DF6] font-sans"
          />

          {activeStreamId !== null ? (
            <button
              type="button"
              onClick={handleStop}
              className="px-3 py-2 bg-[#EF4444]/20 border border-[#EF4444]/40 text-[#EF4444] rounded-[4px] font-mono text-[12px] font-semibold hover:bg-[#EF4444]/30 flex items-center gap-1.5 transition-colors cursor-pointer select-none shrink-0"
            >
              <Square className="w-3.5 h-3.5 fill-[#EF4444]" />
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!inputText.trim() && attachments.length === 0}
              className="px-3 py-2 bg-[#4C8DF6]/20 border border-[#4C8DF6]/40 text-[#4C8DF6] disabled:opacity-40 disabled:cursor-not-allowed rounded-[4px] font-mono text-[12px] font-semibold hover:bg-[#4C8DF6]/30 flex items-center gap-1.5 transition-colors cursor-pointer select-none shrink-0"
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
