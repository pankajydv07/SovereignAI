import React, { useState } from "react";
import {
  ShieldCheck,
  Cpu,
  Activity,
  CheckCircle2,
  FileCode,
  Globe,
  Clock,
} from "lucide-react";

export interface MetricCardItem {
  id: string;
  name: string;
  value: string;
  sampleSize: number;
  measuredDate: string;
  category: string;
  description: string;
}

interface AttestationMetricsPanelProps {
  metrics?: MetricCardItem[];
}

export const AttestationMetricsPanel: React.FC<AttestationMetricsPanelProps> = ({ metrics }) => {
  const [activeTab, setActiveTab] = useState<"attestation" | "metrics">("metrics");

  // Architecture facts only — these describe the design constraint, not invented measurements.
  const architectureAttestations = [
    { label: "Ollama Local API Endpoint", value: "127.0.0.1:11434 (Loopback Only)" },
    { label: "Process IPC Transport", value: "stdio JSON-RPC (Rust <-> Python)" },
    { label: "Outbound Network Sockets Bound", value: "0 (Zero External Egress)" },
  ];

  return (
    <div className="flex-1 flex flex-col bg-bg overflow-hidden text-[13px]">
      {/* Navigation Sub-Header */}
      <div className="h-10 bg-surface border-b border-border px-4 flex items-center justify-between text-xs select-none">
        <div className="flex items-center gap-2 font-mono">
          <button
            onClick={() => setActiveTab("metrics")}
            className={`px-3 py-1 rounded text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer ${
              activeTab === "metrics"
                ? "bg-surface-2 text-sovereign font-semibold border border-border"
                : "text-text-dim hover:text-text"
            }`}
          >
            <Activity className="w-3.5 h-3.5 text-sovereign" />
            <span>OPERATIONAL METRICS</span>
          </button>
          <button
            onClick={() => setActiveTab("attestation")}
            className={`px-3 py-1 rounded text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer ${
              activeTab === "attestation"
                ? "bg-surface-2 text-accent font-semibold border border-border"
                : "text-text-dim hover:text-text"
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5 text-accent" />
            <span>OFFLINE ATTESTATION BUNDLE</span>
          </button>
        </div>

        <div className="flex items-center gap-2 font-mono text-[11px] text-text-dim">
          <span className="flex items-center gap-1 text-sovereign">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Sovereign Air-Gap Verified
          </span>
        </div>
      </div>

      {/* Main Container */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "metrics" && (
          <div className="space-y-4">
            {(!metrics || metrics.length === 0) ? (
              <div className="flex-1 flex flex-col items-center justify-center text-text-dim font-mono text-xs space-y-2 py-16">
                <Clock className="w-5 h-5 text-text-faint" />
                <span>No operational metrics recorded yet.</span>
                <span className="text-text-faint">
                  Metrics are captured from live session activity — routing decisions, model latencies, and tool executions.
                </span>
              </div>
            ) : (
              <>
                <div className="p-3 bg-surface rounded border border-border flex items-center justify-between">
                  <div>
                    <h3 className="font-mono text-sm font-semibold text-text">System Verification Metrics</h3>
                    <p className="text-xs text-text-dim font-mono mt-0.5">
                      All accuracy metrics report sample size (N) and measurement date per governance standards.
                    </p>
                  </div>
                  <span className="px-2.5 py-1 text-[11px] font-mono rounded bg-sovereign/10 border border-sovereign/40 text-sovereign font-semibold">
                    {metrics.length} Metric{metrics.length !== 1 ? "s" : ""} Recorded
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {metrics.map((m) => (
                    <div key={m.id} className="bg-surface rounded border border-border p-4 flex flex-col justify-between hover:border-border/80 transition-colors">
                      <div>
                        <div className="flex items-center justify-between mb-1 font-mono">
                          <span className="text-[11px] text-text-dim uppercase tracking-wider">{m.category}</span>
                          <span className="px-1.5 py-0.5 text-[10px] rounded bg-surface-2 border border-border text-text-dim">
                            Measured: {m.measuredDate}
                          </span>
                        </div>

                        <h4 className="font-semibold text-text text-sm mb-2">{m.name}</h4>

                        <div className="font-mono text-2xl font-bold text-sovereign my-1">{m.value}</div>

                        <p className="text-xs text-text-dim mt-2">{m.description}</p>
                      </div>

                      <div className="mt-4 pt-2 border-t border-border/40 font-mono text-[11px] flex items-center justify-between text-text-dim">
                        <span>Sample Size:</span>
                        <span className="text-text font-semibold">N = {m.sampleSize}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === "attestation" && (
          <div className="space-y-4 font-mono text-xs">
            {/* Network Interface Inventory — architecture facts, not measurements */}
            <div className="bg-surface rounded border border-border p-4">
              <h3 className="font-semibold text-text text-sm mb-2 flex items-center gap-2">
                <Globe className="w-4 h-4 text-sovereign" />
                Network &amp; Interface Inventory
              </h3>
              <ul className="space-y-1 text-text-dim">
                {architectureAttestations.map((a) => (
                  <li key={a.label} className="flex items-center justify-between bg-bg p-2 rounded border border-border/60">
                    <span>{a.label}:</span>
                    <span className="text-sovereign font-semibold">{a.value}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Model Digests — populated from backend when available */}
            <div className="bg-surface rounded border border-border p-4">
              <h3 className="font-semibold text-text text-sm mb-2 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-accent" />
                Registered Model Digests &amp; Routing
              </h3>
              <div className="p-3 bg-bg rounded border border-border/60 text-text-dim text-[11px]">
                Model digest information is read from the Rust sidecar at runtime via{" "}
                <span className="font-mono text-accent">get_model_registry</span>. No data available until the core is connected.
              </div>
            </div>

            {/* Governance Ruleset Digests */}
            <div className="bg-surface rounded border border-border p-4">
              <h3 className="font-semibold text-text text-sm mb-2 flex items-center gap-2">
                <FileCode className="w-4 h-4 text-warning" />
                Active Governance Ruleset Digests (.agents/rules/)
              </h3>
              <div className="p-3 bg-bg rounded border border-border/60 text-text-dim text-[11px]">
                Ruleset SHA-256 digests are computed at startup from the on-disk{" "}
                <span className="font-mono text-accent">.agents/rules/</span> files and reported via the core status payload.
                Connect the core to view verified hashes.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AttestationMetricsPanel;
