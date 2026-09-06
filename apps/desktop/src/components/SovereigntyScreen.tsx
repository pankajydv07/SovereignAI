import React, { useEffect, useState } from "react";
import { Shield, CheckCircle2, AlertTriangle, Check } from "lucide-react";

export interface SystemAssertion {
  id: string;
  label: string;
  detail: string;
  state: "verified" | "sampled" | "pending" | "active_gateway" | "failed";
}

export interface EgressEvent {
  id: string;
  timestamp: string;
  pid: number;
  process_name: string;
  destination: string;
  port: number;
  protocol: string;
  verdict: "blocked" | "detected_external" | "internal_allowed" | "internal_non_standard_port";
  acknowledged: boolean;
}

export interface SovereigntyStatus {
  status: "air_gapped" | "physical_airgap" | "sampled";
  egress_count: number;
  active_link: boolean;
  monitor_active: boolean;
  assertions: SystemAssertion[];
}

export const SovereigntyScreen: React.FC = () => {
  const [status, setStatus] = useState<SovereigntyStatus>({
    status: "sampled",
    egress_count: 0,
    active_link: true,
    monitor_active: true,
    assertions: [
      {
        id: "kernel_policy",
        label: "Kernel Socket Monitor",
        detail: "High-frequency ETW / socket sampler active (50-100ms window)",
        state: "sampled",
      },
      {
        id: "gateway_route",
        label: "Egress Gateway Route",
        detail: "External route available on active network interface",
        state: "active_gateway",
      },
      {
        id: "sandbox_interfaces",
        label: "Sandbox Network Interfaces",
        detail: "Pending — bubblewrap container sandbox is scheduled for Milestone 4",
        state: "pending",
      },
      {
        id: "egress_tools",
        label: "Egress Tool Registry",
        detail: "Pending — tool registry policy enforcement scheduled for Milestone 2",
        state: "pending",
      },
    ],
  });

  const [events, setEvents] = useState<EgressEvent[]>([]);

  useEffect(() => {
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

    if (!isTauri) return;

    let unlistenStatus: (() => void) | undefined;
    let unlistenEvents: (() => void) | undefined;

    const setupSovereignty = async () => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const { listen } = await import("@tauri-apps/api/event");

        const initialStatus = await invoke<SovereigntyStatus>("get_sovereignty_status");
        setStatus(initialStatus);

        const initialEvents = await invoke<EgressEvent[]>("get_egress_events");
        setEvents(initialEvents);

        unlistenStatus = await listen<SovereigntyStatus>("sovereignty-status-changed", (e) => {
          setStatus(e.payload);
        });

        unlistenEvents = await listen<EgressEvent>("egress-attempt-recorded", (e) => {
          setEvents((prev) => [e.payload, ...prev]);
        });
      } catch (err) {
        console.error("Failed to load sovereignty monitor data:", err);
      }
    };

    setupSovereignty();

    return () => {
      if (unlistenStatus) unlistenStatus();
      if (unlistenEvents) unlistenEvents();
    };
  }, []);

  const handleAcknowledge = async (id: string) => {
    setEvents((prev) =>
      prev.map((ev) => (ev.id === id ? { ...ev, acknowledged: true } : ev))
    );

    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("acknowledge_egress_event", { id });
      } catch (err) {
        console.error("Failed to acknowledge event:", err);
      }
    }
  };

  const handleSimulateEgress = async () => {
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (isTauri) {
      // Execute curl in PTY / shell or command
    } else {
      const mockEvent: EgressEvent = {
        id: `ev-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString(),
        pid: 8492,
        process_name: "curl.exe",
        destination: "api.anthropic.com",
        port: 443,
        protocol: "TCP",
        verdict: "detected_external",
        acknowledged: false,
      };
      setEvents((prev) => [mockEvent, ...prev]);
      setStatus((prev) => ({ ...prev, egress_count: prev.egress_count + 1 }));
    }
  };

  const pinnedEvents = events.filter((e) => e.verdict === "detected_external" && !e.acknowledged);
  const unpinnedEvents = events.filter((e) => !(e.verdict === "detected_external" && !e.acknowledged));

  return (
    <div className="flex-1 flex flex-col bg-bg overflow-y-auto p-6 font-sans select-none">
      <div className="max-w-5xl mx-auto w-full space-y-6">
        {/* Status Banners */}
        {!status.active_link ? (
          <div className="p-4 rounded bg-sovereign/10 border border-sovereign text-sovereign flex items-center gap-3 font-mono text-xs shadow-sm">
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
            <div>
              <div className="font-bold text-sm">✓ AIR-GAPPED — no physical network link detected.</div>
              <div className="text-[11px] opacity-90">
                All functions nominal. 0 physical active interface route. Zero data egress possible.
              </div>
            </div>
          </div>
        ) : (
          <div className="p-3.5 rounded bg-verify/10 border border-verify text-verify flex items-center justify-between font-mono text-xs">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-verify flex-shrink-0" />
              <span>
                <strong>Egress monitoring sampled</strong> — enforcement active. Network interface detected.
              </span>
            </div>
            {process.env.NODE_ENV !== "production" && (
              <button
                onClick={handleSimulateEgress}
                className="px-2.5 py-1 rounded bg-critical/20 hover:bg-critical/30 border border-critical/40 text-critical text-[11px] transition-colors cursor-pointer"
              >
                Simulate Outbound Egress
              </button>
            )}
          </div>
        )}

        {/* Hero Counter & Assertions Grid */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-stretch">
          {/* Hero Counter */}
          <div className="md:col-span-5 bg-surface border border-border rounded p-6 flex flex-col items-center justify-center text-center">
            <div
              className={`font-mono text-8xl font-black tracking-tight ${
                status.egress_count > 0 ? "text-critical" : "text-sovereign"
              }`}
            >
              {status.egress_count}
            </div>
            <div className="font-mono text-[11px] text-text-dim mt-2 tracking-wider uppercase font-semibold">
              EXTERNAL EGRESS ATTEMPTS · THIS SESSION
            </div>
          </div>

          {/* 4 Live System Assertions */}
          <div className="md:col-span-7 bg-surface border border-border rounded p-4 flex flex-col justify-between space-y-3">
            <div className="text-xs font-mono font-semibold text-accent flex items-center justify-between border-b border-border pb-2">
              <span>LIVE SYSTEM SECURITY ASSERTIONS</span>
              <span className="text-[11px] text-text-dim">4 CONTROLS</span>
            </div>

            <div className="space-y-2 font-mono text-xs">
              {status.assertions.map((ast) => (
                <div
                  key={ast.id}
                  className="p-2.5 rounded bg-surface-2 border border-border flex items-start justify-between gap-3"
                >
                  <div className="space-y-0.5">
                    <div className="font-semibold text-text text-[12px]">{ast.label}</div>
                    <div className="text-[11px] text-text-dim leading-tight">{ast.detail}</div>
                  </div>
                  <div className="flex-shrink-0">
                    {ast.state === "verified" && (
                      <span className="px-2 py-0.5 rounded bg-sovereign/15 text-sovereign border border-sovereign/30 text-[10px] font-bold">
                        VERIFIED
                      </span>
                    )}
                    {ast.state === "sampled" && (
                      <span className="px-2 py-0.5 rounded bg-verify/15 text-verify border border-verify/30 text-[10px] font-bold">
                        SAMPLED
                      </span>
                    )}
                    {ast.state === "pending" && (
                      <span className="px-2 py-0.5 rounded bg-surface border border-border text-text-faint text-[10px] font-semibold">
                        PENDING
                      </span>
                    )}
                    {ast.state === "active_gateway" && (
                      <span className="px-2 py-0.5 rounded bg-verify/15 text-verify border border-verify/30 text-[10px] font-bold">
                        ACTIVE GATEWAY
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Live Monospace Event Feed */}
        <div className="bg-surface border border-border rounded p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border pb-2 font-mono text-xs">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-sovereign" />
              <span className="font-semibold text-accent">LIVE SOCKET & DNS MONITOR FEED</span>
            </div>
            <span className="text-[11px] text-text-dim">LOGGED TO DISK (JSONL)</span>
          </div>

          <div className="space-y-2 font-mono text-xs max-h-80 overflow-y-auto pr-1">
            {/* Pinned External Attempt Rows */}
            {pinnedEvents.map((ev) => (
              <div
                key={ev.id}
                className="p-3 rounded bg-critical/10 border-l-4 border-l-critical border border-critical/30 flex items-center justify-between text-text"
              >
                <div className="flex items-center gap-3">
                  <span className="px-1.5 py-0.5 rounded bg-critical text-bg font-bold text-[10px]">
                    DETECTED · EXTERNAL
                  </span>
                  <span className="text-text-dim text-[11px]">{ev.timestamp}</span>
                  <span className="text-critical font-bold">{ev.process_name}</span>
                  <span className="text-text-faint text-[11px]">(PID {ev.pid})</span>
                  <span className="text-text font-mono font-semibold">
                    → {ev.destination}:{ev.port} [{ev.protocol}]
                  </span>
                </div>
                <button
                  onClick={() => handleAcknowledge(ev.id)}
                  className="px-2 py-1 rounded bg-surface hover:bg-surface-2 border border-border text-text text-[11px] flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <Check className="w-3 h-3 text-sovereign" />
                  Acknowledge
                </button>
              </div>
            ))}

            {/* Unpinned / Normal Rows */}
            {unpinnedEvents.length > 0 ? (
              unpinnedEvents.map((ev) => (
                <div
                  key={ev.id}
                  className="p-2.5 rounded bg-surface-2 border border-border flex items-center justify-between text-text-dim text-[11px]"
                >
                  <div className="flex items-center gap-3">
                    {ev.verdict === "detected_external" ? (
                      <span className="px-1.5 py-0.5 rounded bg-critical/20 text-critical text-[10px] font-bold">
                        ACKNOWLEDGED
                      </span>
                    ) : (
                      <span className="px-1.5 py-0.5 rounded bg-sovereign/20 text-sovereign text-[10px] font-bold">
                        INTERNAL
                      </span>
                    )}
                    <span>{ev.timestamp}</span>
                    <span className="text-text font-semibold">{ev.process_name}</span>
                    <span>PID {ev.pid}</span>
                    <span>
                      → {ev.destination}:{ev.port} [{ev.protocol}]
                    </span>
                  </div>
                  <span className="text-text-faint text-[10px]">LOGGED</span>
                </div>
              ))
            ) : (
              pinnedEvents.length === 0 && (
                <div className="p-6 text-center text-text-faint text-xs">
                  Zero external socket or DNS egress attempts detected in current session.
                </div>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SovereigntyScreen;
