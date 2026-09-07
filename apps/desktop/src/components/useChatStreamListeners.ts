import { useEffect, useRef } from "react";
import { ChatMessage } from "./MessageItem";
import { ActivePermissionRequest } from "./ConversationPane";
import { PlanStepItem } from "./PlanCard";

export interface UseChatStreamListenersProps {
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  setActiveRouting: React.Dispatch<
    React.SetStateAction<{
      modelTag: string;
      taskClass: string;
      confidence: number;
    } | null>
  >;
  setPendingPermission: React.Dispatch<
    React.SetStateAction<ActivePermissionRequest | null>
  >;
  setActivePlanSteps: React.Dispatch<
    React.SetStateAction<PlanStepItem[] | null>
  >;
  setActiveStreamId: React.Dispatch<React.SetStateAction<number | null>>;
}

export function useChatStreamListeners({
  setMessages,
  setActiveRouting,
  setPendingPermission,
  setActivePlanSteps,
  setActiveStreamId,
}: UseChatStreamListenersProps) {
  const pendingTokensRef = useRef<{
    [msgId: string]: {
      deltaContent: string;
      deltaThinking: string;
      role?: string;
      model?: string;
      taskClass?: string;
    };
  }>({});
  const rafIdRef = useRef<number | null>(null);

  useEffect(() => {
    const isTauri =
      typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!isTauri) return;

    let unlistenToken: (() => void) | undefined;
    let unlistenComplete: (() => void) | undefined;
    let unlistenInterrupt: (() => void) | undefined;
    let unlistenRouting: (() => void) | undefined;
    let unlistenPermission: (() => void) | undefined;
    let unlistenSessionUpdate: (() => void) | undefined;

    const setupListeners = async () => {
      const { listen } = await import("@tauri-apps/api/event");

      unlistenToken = await listen<{
        id: number;
        sessionId?: string;
        model: string;
        delta: string;
        thinking_delta: string;
        content: string;
        thinking: string;
      }>("chat-token-received", (event) => {
        const { id, model, delta, thinking_delta, content, thinking } =
          event.payload;
        const msgIdStr = String(id);

        if (!pendingTokensRef.current[msgIdStr]) {
          pendingTokensRef.current[msgIdStr] = {
            deltaContent: content || delta || "",
            deltaThinking: thinking || thinking_delta || "",
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
            pendingTokensRef.current[msgIdStr].deltaThinking +=
              thinking_delta || "";
          }
        }

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

      unlistenRouting = await listen<{
        sessionId: string;
        taskClass: string;
        modelTag: string;
        confidence: number;
        reasoning?: string;
      }>("chat-routing", (event) => {
        const { taskClass, modelTag, confidence } = event.payload;
        setActiveRouting({ taskClass, modelTag, confidence });
      });

      unlistenPermission = await listen<ActivePermissionRequest>(
        "permission-request",
        (event) => {
          setPendingPermission(event.payload);
        }
      );

      unlistenSessionUpdate = await listen<{
        sessionId: string;
        update: {
          type: string;
          steps?: PlanStepItem[];
        };
      }>("session-update", (event) => {
        if (
          event.payload.update.type === "plan" &&
          event.payload.update.steps
        ) {
          setActivePlanSteps(event.payload.update.steps);
        }
      });

      unlistenComplete = await listen<{
        id: number;
        result: {
          model: string;
          taskClass?: string;
          content: string;
          thinking: string;
          metrics?: Record<string, number>;
          steps?: PlanStepItem[];
        };
      }>("chat-stream-completed", (event) => {
        const { id, result } = event.payload;
        const msgIdStr = String(id);

        if (result.steps) {
          setActivePlanSteps(result.steps);
        }

        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.id === msgIdStr) {
              return {
                ...msg,
                content: result.content,
                thinking: result.thinking,
                model: result.model,
                taskClass: result.taskClass,
                metrics: result.metrics,
                isStreaming: false,
              };
            }
            return msg;
          })
        );
        setActiveStreamId(null);
      });

      unlistenInterrupt = await listen<{
        id?: number;
        reason?: string;
      }>("chat-stream-interrupted", (event) => {
        const targetId = event.payload.id ? String(event.payload.id) : null;
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.isStreaming && (!targetId || msg.id === targetId)) {
              return {
                ...msg,
                isStreaming: false,
                interrupted: true,
              };
            }
            return msg;
          })
        );
        setActiveStreamId(null);
        setPendingPermission(null);
      });
    };

    setupListeners();

    return () => {
      if (unlistenToken) unlistenToken();
      if (unlistenComplete) unlistenComplete();
      if (unlistenInterrupt) unlistenInterrupt();
      if (unlistenRouting) unlistenRouting();
      if (unlistenPermission) unlistenPermission();
      if (unlistenSessionUpdate) unlistenSessionUpdate();
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, [setMessages, setActiveRouting, setPendingPermission, setActivePlanSteps, setActiveStreamId]);
}
