import React from "react";
import {
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  FileText,
  Cpu,
  FileCheck,
  CheckCircle2,
  Clock,
} from "lucide-react";

export interface AuditRecordUI {
  record_index: number;
  record_id: string;
  run_id: string;
  user_id: string;
  action_type: string;
  prompt: string;
  plan: { stepIndex: number; description: string }[];
  steps: { stepIndex: number; status: string }[];
  documents_retrieved: { doc_id: string; title: string; classification: string }[];
  models_used: string[];
  deliverables: { path: string; type: string; sha256: string }[];
  approval_event?: { checker: string; action: string; timestamp: string } | null;
  prev_hash: string;
  record_hash: string;
  created_at_ms: number;
}

export interface AuditVerificationStatus {
  isValid: boolean;
  totalRecords: number;
  failedIndex: number | null;
  failedRecordId: string | null;
  reason: string | null;
}

interface AuditChainPanelProps {
  records?: AuditRecordUI[];
  verification?: AuditVerificationStatus;
  onVerify?: () => void;
}

export const AuditChainPanel: React.FC<AuditChainPanelProps> = ({
  records,
  verification,
  onVerify,
}) => {
  const hasRecords = records && records.length > 0;

  const renderVerificationBanner = () => {
    if (!verification) {
      return (
        <div className="px-4 py-3 border-b flex items-center gap-3 bg-surface border-border text-text-dim">
          <Clock className="w-5 h-5 text-text-dim shrink-0" />
          <div>
            <div className="font-mono font-semibold text-xs tracking-wide uppercase">
              AUDIT CHAIN — AWAITING SESSION DATA
            </div>
            <p className="text-[12px] font-mono mt-0.5 opacity-80">
              Audit records are written when the active session produces tool calls or deliverables.
            </p>
          </div>
        </div>
      );
    }

    return (
      <div
        className={`px-4 py-3 border-b flex items-center justify-between transition-colors ${
          verification.isValid
            ? "bg-sovereign/10 border-sovereign/40 text-sovereign"
            : "bg-critical/15 border-critical text-critical"
        }`}
      >
        <div className="flex items-center gap-3">
          {verification.isValid ? (
            <ShieldCheck className="w-5 h-5 text-sovereign shrink-0" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-critical shrink-0 animate-pulse" />
          )}
          <div>
            <div className="font-mono font-semibold text-xs tracking-wide uppercase flex items-center gap-2">
              <span>
                {verification.isValid
                  ? `AUDIT CHAIN VERIFIED · 100% TAMPER-EVIDENT INTEGRITY (${verification.totalRecords} RECORDS)`
                  : `CRITICAL: TAMPER DETECTED · VERIFICATION FAILED AT RECORD #${verification.failedIndex}`}
              </span>
            </div>
            <p className="text-[12px] opacity-90 font-mono mt-0.5">
              {verification.isValid
                ? "Cryptographic SHA-256 chain links verified across all recorded events. No record mutation detected."
                : verification.reason || "Hash chain mismatch detected."}
            </p>
          </div>
        </div>

        {onVerify && (
          <button
            onClick={onVerify}
            className="px-2.5 py-1 rounded bg-surface border border-border text-text hover:bg-surface-2 flex items-center gap-1.5 cursor-pointer transition-colors font-mono text-[11px]"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Verify Chain
          </button>
        )}
      </div>
    );
  };

  return (
    <div className="flex-1 flex flex-col bg-bg overflow-hidden text-[13px]">
      {renderVerificationBanner()}

      {!hasRecords ? (
        <div className="flex-1 flex flex-col items-center justify-center text-text-dim font-mono text-xs space-y-2 p-8">
          <Clock className="w-5 h-5 text-text-faint" />
          <span>No audit records for this session yet.</span>
          <span className="text-text-faint">
            Records are appended as the agent executes tool calls, calculations, and deliverables.
          </span>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {records!.map((rec) => {
            const isFailedRecord =
              verification &&
              !verification.isValid &&
              verification.failedIndex === rec.record_index;

            return (
              <div
                key={rec.record_id}
                className={`rounded border p-4 transition-all ${
                  isFailedRecord
                    ? "bg-critical/10 border-critical"
                    : "bg-surface border-border hover:border-border/80"
                }`}
              >
                {/* Record Metadata Header */}
                <div className="flex items-center justify-between border-b border-border/60 pb-2 mb-3">
                  <div className="flex items-center gap-2 font-mono text-[12px]">
                    <span className="px-2 py-0.5 rounded bg-surface-2 border border-border font-semibold text-text">
                      #{rec.record_index}
                    </span>
                    <span className="font-semibold text-accent">{rec.record_id}</span>
                    <span className="text-text-dim">·</span>
                    <span className="px-2 py-0.5 rounded bg-accent/10 border border-accent/30 text-accent font-semibold text-[11px]">
                      {rec.action_type}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 font-mono text-[11px] text-text-dim">
                    <span>User: <strong className="text-text">{rec.user_id}</strong></span>
                    <span>Run ID: <strong className="text-text">{rec.run_id}</strong></span>
                    <span>{new Date(rec.created_at_ms).toLocaleTimeString()}</span>
                  </div>
                </div>

                {/* Prompt / Event Description */}
                <div className="mb-3">
                  <div className="text-[11px] font-mono uppercase text-text-dim mb-1">Intent / Prompt</div>
                  <div
                    className={`p-2 rounded font-mono text-xs border ${
                      isFailedRecord
                        ? "bg-critical/20 border-critical text-critical font-bold"
                        : "bg-bg border-border text-text"
                    }`}
                  >
                    {rec.prompt}
                  </div>
                </div>

                {/* Details Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                  <div className="bg-bg/60 rounded border border-border/60 p-2.5">
                    <div className="text-[11px] font-mono text-text-dim uppercase mb-1.5 flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5" />
                      Documents Retrieved ({rec.documents_retrieved.length})
                    </div>
                    {rec.documents_retrieved.length === 0 ? (
                      <span className="text-text-dim text-[11px] font-mono">None</span>
                    ) : (
                      <ul className="space-y-1 text-xs">
                        {rec.documents_retrieved.map((doc) => (
                          <li key={doc.doc_id} className="flex items-center justify-between font-mono">
                            <span className="truncate max-w-[160px]" title={doc.title}>{doc.title}</span>
                            <span className="px-1.5 py-0.5 text-[10px] rounded bg-warning/10 border border-warning/30 text-warning">
                              {doc.classification}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <div className="bg-bg/60 rounded border border-border/60 p-2.5">
                    <div className="text-[11px] font-mono text-text-dim uppercase mb-1.5 flex items-center gap-1">
                      <Cpu className="w-3.5 h-3.5" />
                      Models Used ({rec.models_used.length})
                    </div>
                    {rec.models_used.length === 0 ? (
                      <span className="text-text-dim text-[11px] font-mono">None</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {rec.models_used.map((m) => (
                          <span key={m} className="px-2 py-0.5 text-[11px] font-mono rounded bg-surface-2 border border-border text-text">
                            {m}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="bg-bg/60 rounded border border-border/60 p-2.5">
                    <div className="text-[11px] font-mono text-text-dim uppercase mb-1.5 flex items-center gap-1">
                      <FileCheck className="w-3.5 h-3.5 text-sovereign" />
                      Deliverables ({rec.deliverables.length})
                    </div>
                    {rec.deliverables.length === 0 ? (
                      <span className="text-text-dim text-[11px] font-mono">None</span>
                    ) : (
                      <ul className="space-y-1 text-xs">
                        {rec.deliverables.map((del) => (
                          <li key={del.path} className="font-mono text-[11px]">
                            <div className="text-accent truncate font-semibold">{del.path}</div>
                            <div className="text-[10px] text-text-dim truncate">SHA: {del.sha256.substring(0, 16)}...</div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>

                {/* Approval Event if present */}
                {rec.approval_event && (
                  <div className="mb-3 p-2.5 rounded bg-sovereign/10 border border-sovereign/30 flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-sovereign" />
                      <span>Approval Event: <strong className="text-text">{rec.approval_event.checker}</strong></span>
                    </div>
                    <span className="text-sovereign font-semibold">{rec.approval_event.timestamp}</span>
                  </div>
                )}

                {/* Hash Linkage Chain Footer */}
                <div className="mt-3 pt-2 border-t border-border/40 font-mono text-[11px] space-y-1 bg-bg/40 p-2 rounded">
                  <div className="flex items-center justify-between text-text-dim">
                    <span>PREV_HASH:</span>
                    <span className="text-text font-mono truncate max-w-[420px]">{rec.prev_hash}</span>
                  </div>
                  <div className="flex items-center justify-between text-text-dim">
                    <span>RECORD_HASH (SHA-256):</span>
                    <span className={`font-mono truncate max-w-[420px] font-semibold ${isFailedRecord ? "text-critical" : "text-sovereign"}`}>
                      {rec.record_hash}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AuditChainPanel;
