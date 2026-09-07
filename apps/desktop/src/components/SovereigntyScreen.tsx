import React, { useEffect, useRef, useState } from "react";
import { Shield, CheckCircle2, AlertTriangle, Check, RefreshCw, Terminal, FileText, Activity } from "lucide-react";

export interface NetworkInterfaceEvidence {
  interface_name: string;
  description: string;
  operational_status: string;
  interface_type: string;
  physical: boolean;
  excluded: boolean;
  reason: string;
}

export interface VerificationEvent {
  timestamp: string;
  event: string;
  detail: string;
}

export interface SovereigntyVerification {
  timestamp: string;
  active_physical_links: number;
  physical_interfaces: number;
  virtual_interfaces: number;
  loopback_interfaces: number;
  route_status: string;
  egress_status: string;
  verdict: string;
  verdict_detail: string;
  interfaces: NetworkInterfaceEvidence[];
  events: VerificationEvent[];
  log_file_path: string;
  success: boolean;
  error_message?: string | null;
}

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
  status: "air_gapped" | "physical_airgap" | "sampled" | "failed";
  egress_count: number;
  active_link: boolean;
  monitor_active: boolean;
  assertions: SystemAssertion[];
  verification?: SovereigntyVerification | null;
  log_file_path?: string;
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
    verification: null,
    log_file_path: "sovereignty_events.jsonl",
  });

  const [events, setEvents] = useState<EgressEvent[]>([]);
  const [verificationLog, setVerificationLog] = useState<VerificationEvent[]>([]);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verifyButtonState, setVerifyButtonState] = useState<string>("IDLE");
  const logTerminalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (!isTauri) return;

    let unlistenStatus: (() => void) | undefined;
    let unlistenEvents: (() => void) | undefined;
    let unlistenVer: (() => void) | undefined;

    const setupSovereignty = async () => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const { listen } = await import("@tauri-apps/api/event");

        const initialStatus = await invoke<SovereigntyStatus>("get_sovereignty_status");
        setStatus(initialStatus);
        if (initialStatus.verification?.events) {
          setVerificationLog(initialStatus.verification.events);
        }

        const initialEvents = await invoke<EgressEvent[]>("get_egress_events");
        setEvents(initialEvents);

        unlistenStatus = await listen<SovereigntyStatus>("sovereignty-status-changed", (e) => {
          setStatus(e.payload);
          if (e.payload.verification?.events) {
            setVerificationLog(e.payload.verification.events);
          }
        });

        unlistenEvents = await listen<EgressEvent>("egress-attempt-recorded", (e) => {
          setEvents((prev) => [e.payload, ...prev]);
        });

        unlistenVer = await listen<SovereigntyVerification>("sovereignty-verification-completed", (e) => {
          setStatus((prev) => ({ ...prev, verification: e.payload }));
          if (e.payload.events) {
            setVerificationLog(e.payload.events);
          }
        });
      } catch (err) {
        console.error("Failed to load sovereignty monitor data:", err);
      }
    };

    setupSovereignty();

    return () => {
      if (unlistenStatus) unlistenStatus();
      if (unlistenEvents) unlistenEvents();
      if (unlistenVer) unlistenVer();
    };
  }, []);

  useEffect(() => {
    if (logTerminalRef.current) {
      logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight;
    }
  }, [verificationLog]);

  const handleRunVerification = async () => {
    setIsVerifying(true);
    setVerifyButtonState("VERIFYING...");

    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const result = await invoke<SovereigntyVerification>("get_sovereignty_verification");
        setStatus((prev) => ({ ...prev, verification: result, active_link: result.active_physical_links > 0 }));
        if (result.events) {
          setVerificationLog(result.events);
        }
        setVerifyButtonState("VERIFICATION COMPLETE");
      } catch (err) {
        console.error("Verification command failed:", err);
        setVerifyButtonState("ERROR");
      }
    } else {
      setVerifyButtonState("VERIFICATION COMPLETE");
    }

    setTimeout(() => {
      setIsVerifying(false);
      setVerifyButtonState("IDLE");
    }, 1800);
  };

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
    const mockEvent: EgressEvent = {
      id: `ev-${Date.now()}`,
      timestamp: new Date().toLocaleTimeString(),
      pid: 8492,
      process_name: "curl.exe",
      destination: "192.0.2.1",
      port: 443,
      protocol: "TCP",
      verdict: "detected_external",
      acknowledged: false,
    };
    setEvents((prev) => [mockEvent, ...prev]);
    setStatus((prev) => ({ ...prev, egress_count: prev.egress_count + 1 }));
  };

  const verification = status.verification;
  const isFailed = verification && !verification.success;
  const isAirGapped = verification ? verification.active_physical_links === 0 && verification.success : !status.active_link;
  const pinnedEvents = events.filter((e) => e.verdict === "detected_external" && !e.acknowledged);
  const unpinnedEvents = events.filter((e) => !(e.verdict === "detected_external" && !e.acknowledged));

  return (
    <div className="flex-1 flex flex-col bg-bg overflow-y-auto p-5 font-sans select-none text-text">
      <div className="max-w-6xl mx-auto w-full space-y-5">
        {/* Top Status Banner */}
        {isFailed ? (
          <div className="p-3.5 rounded bg-critical/10 border border-critical text-critical flex items-center justify-between font-mono text-xs shadow-sm">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              <div>
                <div className="font-bold text-[13px]">⚠ VERIFICATION FAILED — Unable to complete native network inspection.</div>
                <div className="text-[11px] opacity-90 mt-0.5">
                  {verification?.error_message || "Native OS network table probe returned an error. Air-gap status unverified."}
                </div>
              </div>
            </div>
            <button
              onClick={handleRunVerification}
              disabled={isVerifying}
              className="px-3 py-1.5 rounded bg-critical/20 hover:bg-critical/30 border border-critical/50 text-critical text-[11px] font-bold transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isVerifying ? "animate-spin" : ""}`} />
              {verifyButtonState !== "IDLE" ? verifyButtonState : "RETRY INSPECTION"}
            </button>
          </div>
        ) : isAirGapped ? (
          <div className="p-3.5 rounded bg-sovereign/10 border border-sovereign text-sovereign flex items-center justify-between font-mono text-xs shadow-sm">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
              <div>
                <div className="font-bold text-[13px]">✓ AIR-GAPPED — No active physical network interface detected.</div>
                <div className="text-[11px] opacity-90 mt-0.5">
                  Native OS network inspection completed. 0 active physical interface routes.
                </div>
              </div>
            </div>
            <button
              onClick={handleRunVerification}
              disabled={isVerifying}
              className="px-3 py-1.5 rounded bg-sovereign/20 hover:bg-sovereign/30 border border-sovereign/40 text-sovereign text-[11px] font-bold transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isVerifying ? "animate-spin" : ""}`} />
              {verifyButtonState !== "IDLE" ? verifyButtonState : "RUN VERIFICATION"}
            </button>
          </div>
        ) : (
          <div className="p-3.5 rounded bg-verify/10 border border-verify text-verify flex items-center justify-between font-mono text-xs shadow-sm">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              <div>
                <div className="font-bold text-[13px]">⚠ PHYSICAL NETWORK LINK ACTIVE — External interface route detected.</div>
                <div className="text-[11px] opacity-90 mt-0.5">
                  Native OS inspection detected {verification?.active_physical_links || 1} active physical network link(s). Real-time egress monitoring active.
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleRunVerification}
                disabled={isVerifying}
                className="px-3 py-1.5 rounded bg-verify/20 hover:bg-verify/30 border border-verify/40 text-verify text-[11px] font-bold transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isVerifying ? "animate-spin" : ""}`} />
                {verifyButtonState !== "IDLE" ? verifyButtonState : "RUN VERIFICATION"}
              </button>
              {process.env.NODE_ENV !== "production" && (
                <button
                  onClick={handleSimulateEgress}
                  className="px-2.5 py-1.5 rounded bg-critical/20 hover:bg-critical/30 border border-critical/40 text-critical text-[11px] font-semibold transition-colors cursor-pointer"
                >
                  Simulate Egress
                </button>
              )}
            </div>
          </div>
        )}

        {/* Supervisor Evidence Card & Assertions */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-stretch">
          {/* Supervisor Evidence Card */}
          <div className="md:col-span-6 bg-surface border border-border rounded p-4 flex flex-col justify-between space-y-3">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <div className="flex items-center gap-2 font-mono text-xs font-semibold text-accent">
                <Activity className="w-4 h-4 text-accent" />
                <span>SOVEREIGNTY VERIFICATION EVIDENCE</span>
              </div>
              <span className="font-mono text-[11px] text-text-dim">
                {verification?.timestamp ? `Verified ${verification.timestamp}` : "Live"}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2.5 font-mono text-xs">
              <div className="p-2.5 rounded bg-surface-2 border border-border flex justify-between items-center">
                <span className="text-text-dim text-[11px]">Physical Adapters:</span>
                <span className="font-bold text-text">{verification?.physical_interfaces ?? 0}</span>
              </div>
              <div className="p-2.5 rounded bg-surface-2 border border-border flex justify-between items-center">
                <span className="text-text-dim text-[11px]">Active Physical Links:</span>
                <span className={`font-bold ${verification?.active_physical_links ? "text-verify" : "text-sovereign"}`}>
                  {verification?.active_physical_links ?? 0}
                </span>
              </div>
              <div className="p-2.5 rounded bg-surface-2 border border-border flex justify-between items-center">
                <span className="text-text-dim text-[11px]">Virtual Adapters:</span>
                <span className="font-bold text-text-dim">{verification?.virtual_interfaces ?? 0}</span>
              </div>
              <div className="p-2.5 rounded bg-surface-2 border border-border flex justify-between items-center">
                <span className="text-text-dim text-[11px]">Loopback Devices:</span>
                <span className="font-bold text-text-dim">{verification?.loopback_interfaces ?? 0}</span>
              </div>
              <div className="col-span-2 p-2.5 rounded bg-surface-2 border border-border flex justify-between items-center">
                <span className="text-text-dim text-[11px]">External Route:</span>
                <span className="font-semibold text-[11px] text-text">
                  {verification?.route_status || (status.active_link ? "Active Gateway" : "No External Physical Route")}
                </span>
              </div>
            </div>

            <div className="pt-2 border-t border-border flex items-center justify-between">
              <div className="font-mono text-[11px] text-text-dim">FINAL VERDICT:</div>
              {isFailed ? (
                <span className="px-2.5 py-1 rounded bg-critical/15 text-critical border border-critical/30 font-mono text-xs font-bold">
                  ✖ VERIFICATION FAILED
                </span>
              ) : isAirGapped ? (
                <span className="px-2.5 py-1 rounded bg-sovereign/15 text-sovereign border border-sovereign/30 font-mono text-xs font-bold">
                  ✓ NO ACTIVE PHYSICAL NETWORK LINK
                </span>
              ) : (
                <span className="px-2.5 py-1 rounded bg-verify/15 text-verify border border-verify/30 font-mono text-xs font-bold">
                  ⚠ ACTIVE PHYSICAL LINK DETECTED
                </span>
              )}
            </div>
          </div>

          {/* 4 Live System Assertions */}
          <div className="md:col-span-6 bg-surface border border-border rounded p-4 flex flex-col justify-between space-y-3">
            <div className="text-xs font-mono font-semibold text-accent flex items-center justify-between border-b border-border pb-2">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-accent" />
                <span>LIVE SYSTEM SECURITY ASSERTIONS</span>
              </div>
              <span className="text-[11px] text-text-dim">4 CONTROLS</span>
            </div>

            <div className="space-y-2 font-mono text-xs">
              {status.assertions.map((ast) => (
                <div
                  key={ast.id}
                  className="p-2 rounded bg-surface-2 border border-border flex items-start justify-between gap-3"
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
                    {ast.state === "failed" && (
                      <span className="px-2 py-0.5 rounded bg-critical/15 text-critical border border-critical/30 text-[10px] font-bold">
                        FAILED
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Network Interface Inspection Table */}
        <div className="bg-surface border border-border rounded p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border pb-2 font-mono text-xs">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-accent" />
              <span className="font-semibold text-accent">NETWORK INTERFACE INSPECTION</span>
            </div>
            <span className="text-[11px] text-text-dim">
              {verification?.interfaces.length ?? 0} OS INTERFACES ENUMERATED
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs border-collapse">
              <thead>
                <tr className="border-b border-border text-text-dim text-[11px]">
                  <th className="py-2 px-2.5 font-semibold">Interface</th>
                  <th className="py-2 px-2.5 font-semibold">Status</th>
                  <th className="py-2 px-2.5 font-semibold">Type</th>
                  <th className="py-2 px-2.5 font-semibold">Physical</th>
                  <th className="py-2 px-2.5 font-semibold">Decision</th>
                  <th className="py-2 px-2.5 font-semibold">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-[11px]">
                {verification?.interfaces && verification.interfaces.length > 0 ? (
                  verification.interfaces.map((iface, idx) => (
                    <tr key={idx} className="hover:bg-surface-2 transition-colors">
                      <td className="py-2 px-2.5">
                        <div className="font-bold text-text">{iface.interface_name}</div>
                        <div className="text-[10px] text-text-faint">{iface.description}</div>
                      </td>
                      <td className="py-2 px-2.5">
                        <span
                          className={`px-1.5 py-0.5 rounded font-bold text-[10px] ${
                            iface.operational_status === "UP"
                              ? "bg-sovereign/15 text-sovereign border border-sovereign/30"
                              : "bg-surface-2 text-text-dim border border-border"
                          }`}
                        >
                          {iface.operational_status}
                        </span>
                      </td>
                      <td className="py-2 px-2.5 text-text-dim">{iface.interface_type}</td>
                      <td className="py-2 px-2.5">
                        <span
                          className={`font-semibold ${
                            iface.physical ? "text-text" : "text-text-faint"
                          }`}
                        >
                          {iface.physical ? "YES" : "NO"}
                        </span>
                      </td>
                      <td className="py-2 px-2.5">
                        {iface.excluded ? (
                          <span className="px-1.5 py-0.5 rounded bg-surface text-text-dim border border-border text-[10px]">
                            EXCLUDED
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded bg-verify/15 text-verify border border-verify/30 text-[10px] font-bold">
                            ACTIVE
                          </span>
                        )}
                      </td>
                      <td className="py-2 px-2.5 text-text-dim text-[11px]">{iface.reason}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-4 text-center text-text-dim">
                      {isFailed ? "Inspection query failed." : "No network interfaces returned by OS."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Live Verification Log & Audit Evidence */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-stretch">
          {/* Live Verification Log */}
          <div className="md:col-span-8 bg-surface border border-border rounded p-4 space-y-2 flex flex-col justify-between">
            <div className="flex items-center justify-between border-b border-border pb-2 font-mono text-xs">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-accent" />
                <span className="font-semibold text-accent">LIVE VERIFICATION LOG</span>
              </div>
              <span className="text-[11px] text-text-dim">ROLLING OS INSPECTION TRACE</span>
            </div>

            <div
              ref={logTerminalRef}
              className="p-2.5 rounded bg-[#070A0E] border border-border font-mono text-[11px] space-y-1 h-44 overflow-y-auto"
            >
              {verificationLog.length > 0 ? (
                verificationLog.map((log, idx) => (
                  <div key={idx} className="flex items-start gap-2 leading-tight">
                    <span className="text-text-faint flex-shrink-0">{log.timestamp}</span>
                    <span
                      className={`font-bold flex-shrink-0 ${
                        log.event === "VERDICT_GENERATED"
                          ? "text-sovereign"
                          : log.event === "INSPECTION_FAILED"
                          ? "text-critical"
                          : "text-accent"
                      }`}
                    >
                      {log.event}
                    </span>
                    <span className="text-text-dim truncate">{log.detail}</span>
                  </div>
                ))
              ) : (
                <div className="text-text-faint text-center py-4">Awaiting verification run...</div>
              )}
            </div>
          </div>

          {/* Audit Evidence Card */}
          <div className="md:col-span-4 bg-surface border border-border rounded p-4 space-y-3 flex flex-col justify-between">
            <div className="flex items-center justify-between border-b border-border pb-2 font-mono text-xs">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-sovereign" />
                <span className="font-semibold text-accent">AUDIT EVIDENCE</span>
              </div>
              <span className="px-1.5 py-0.2 rounded bg-sovereign/15 text-sovereign border border-sovereign/30 text-[10px] font-bold">
                ACTIVE
              </span>
            </div>

            <div className="space-y-2 font-mono text-xs">
              <div className="p-2 rounded bg-surface-2 border border-border">
                <div className="text-[10px] text-text-dim uppercase">Format</div>
                <div className="font-bold text-text text-[11px]">JSONL (Append-Only)</div>
              </div>
              <div className="p-2 rounded bg-surface-2 border border-border">
                <div className="text-[10px] text-text-dim uppercase">Last Event</div>
                <div className="font-semibold text-text text-[11px]">
                  {verification?.timestamp || "Session start"}
                </div>
              </div>
              <div className="p-2 rounded bg-surface-2 border border-border">
                <div className="text-[10px] text-text-dim uppercase">Durable Evidence File</div>
                <div className="font-mono text-[10px] text-text-dim truncate" title={status.log_file_path || "sovereignty_events.jsonl"}>
                  {status.log_file_path || "sovereignty_events.jsonl"}
                </div>
              </div>
            </div>

            <div className="font-mono text-[10px] text-text-faint text-center pt-1">
              Cryptographically timestamped & persisted
            </div>
          </div>
        </div>

        {/* Live Socket & DNS Monitor Feed */}
        <div className="bg-surface border border-border rounded p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border pb-2 font-mono text-xs">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-sovereign" />
              <span className="font-semibold text-accent">LIVE SOCKET & DNS MONITOR FEED</span>
            </div>
            <span className="text-[11px] text-text-dim">
              {status.egress_count} EXTERNAL ATTEMPTS DETECTED
            </span>
          </div>

          <div className="space-y-2 font-mono text-xs max-h-60 overflow-y-auto pr-1">
            {/* Pinned External Attempt Rows */}
            {pinnedEvents.map((ev) => (
              <div
                key={ev.id}
                className="p-2.5 rounded bg-critical/10 border-l-4 border-l-critical border border-critical/30 flex items-center justify-between text-text"
              >
                <div className="flex items-center gap-2.5">
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
                  className="p-2 rounded bg-surface-2 border border-border flex items-center justify-between text-text-dim text-[11px]"
                >
                  <div className="flex items-center gap-2.5">
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
                <div className="p-4 text-center text-text-faint text-xs">
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
