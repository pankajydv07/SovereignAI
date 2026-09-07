import { useEffect } from "react";
import { ChatMessage } from "./MessageItem";
import { PlanStepItem } from "./PlanCard";
import { ProjectInfo } from "../protocol";

interface UseSessionHistoryParams {
  activeSessionId?: string | null;
  activeProject?: ProjectInfo | null;
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  setActiveRouting: React.Dispatch<
    React.SetStateAction<{
      modelTag: string;
      taskClass: string;
      confidence: number;
    } | null>
  >;
  setActivePlanSteps: React.Dispatch<React.SetStateAction<PlanStepItem[] | null>>;
}

export const useSessionHistory = ({
  activeSessionId,
  activeProject,
  setMessages,
  setActiveRouting,
  setActivePlanSteps,
}: UseSessionHistoryParams) => {
  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      setActiveRouting(null);
      setActivePlanSteps(null);
      return;
    }

    const isTauri =
      typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!isTauri) return;

    let isMounted = true;

    const loadSessionHistory = async () => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const res = await invoke<any>("invoke_core_rpc", {
          method: "session/load",
          params: {
            sessionId: activeSessionId,
            projectPath: activeProject?.path || undefined,
          },
        });

        if (!isMounted || !res || !res.events) return;

        const events = res.events as any[];
        const parsedMessages: ChatMessage[] = [];
        let steps: PlanStepItem[] | null = null;
        let lastRouting: {
          modelTag: string;
          taskClass: string;
          confidence: number;
        } | null = null;

        for (const ev of events) {
          if (ev.eventType === "message_started") {
            const rawMsgs = (ev.payload?.messages as any[]) || [];
            const userM = rawMsgs.filter((m) => m.role === "user").pop();
            if (userM && userM.content) {
              parsedMessages.push({
                id: `user-${ev.seq}`,
                sender: "user",
                content: userM.content,
              });
            }
            if (ev.payload?.model) {
              lastRouting = {
                modelTag: String(ev.payload.model),
                taskClass: String(ev.payload.task_class || "other"),
                confidence: 0.95,
              };
            }
          } else if (ev.eventType === "message_completed") {
            parsedMessages.push({
              id: `asst-${ev.seq}`,
              sender: "assistant",
              model: (ev.payload?.model as string) || undefined,
              taskClass: (ev.payload?.task_class as string) || undefined,
              content: (ev.payload?.content as string) || "",
              thinking: (ev.payload?.thinking as string) || undefined,
              isStreaming: false,
            });
          } else if (ev.eventType === "plan_created") {
            if (ev.payload?.steps) {
              steps = ev.payload.steps as PlanStepItem[];
            }
          }
        }

        setMessages(parsedMessages);
        setActivePlanSteps(steps);
        if (lastRouting) {
          setActiveRouting(lastRouting);
        }
      } catch (err) {
        console.error("Failed to load session history:", err);
      }
    };

    loadSessionHistory();

    return () => {
      isMounted = false;
    };
  }, [activeSessionId, activeProject?.path, setMessages, setActiveRouting, setActivePlanSteps]);
};
