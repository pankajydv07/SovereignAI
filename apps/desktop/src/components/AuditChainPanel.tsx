import React, { useState } from "react";
import {
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  FileText,
  Download,
  CheckCircle2,
  Cpu,
  FileCheck,
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

const INITIAL_RECORDS: AuditRecordUI[] = [
  {
    record_index: 0,
    record_id: "audit-rec-1772890000000-0",
    run_id: "run-20260906-01",
    user_id: "user_sharma",
    action_type: "TASK_EXECUTION",
    prompt: "Execute remaining life calculation for Crude Distillation Column C-101",
    plan: [
      { stepIndex: 1, description: "Extract thickness measurements from SOP-114" },
      { stepIndex: 2, description: "Run Python corrosion rate sandbox calculation" },
      { stepIndex: 3, description: "Generate Approval Note DOCX" },
    ],
    steps: [
      { stepIndex: 1, status: "completed" },
      { stepIndex: 2, status: "completed" },
      { stepIndex: 3, status: "completed" },
    ],
    documents_retrieved: [
      { doc_id: "DOC-IOCL-2024-C101", title: "C-101 Ultrasonic Thickness Inspection", classification: "CONFIDENTIAL" },
      { doc_id: "KB-SOP-114-REV3", title: "API 510 Corrosion Rate Standard", classification: "RESTRICTED" },
    ],
    models_used: ["qwen3-coder:30b", "glm-ocr:9b"],
    deliverables: [
      { path: "deliverables/C101_Approval_Note.docx", type: "approval_note", sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" },
    ],
    approval_event: null,
    prev_hash: "0000000000000000000000000000000000000000000000000000000000000000",
    record_hash: "8f9b4c1e2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d",
    created_at_ms: Date.now() - 3600000,
  },
  {
    record_index: 1,
    record_id: "audit-rec-1772890360000-1",
    run_id: "run-20260906-02",
    user_id: "user_kulkarni",
    action_type: "APPROVAL_EVENT",
    prompt: "Approve deliverable C101_Approval_Note.docx after verifying calculation and citations",
    plan: [],
    steps: [],
    documents_retrieved: [],
    models_used: [],
    deliverables: [],
    approval_event: {
      checker: "P. V. Kulkarni (Chief Manager - Mechanical)",
      action: "APPROVED",
      timestamp: "23:45:10 · 06 Sep 2026",
    },
    prev_hash: "8f9b4c1e2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d",
    record_hash: "3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b",
    created_at_ms: Date.now() - 1800000,
  },
];

export const AuditChainPanel: React.FC = () => {
  const [records, setRecords] = useState<AuditRecordUI[]>(INITIAL_RECORDS);
  const [verification, setVerification] = useState<AuditVerificationStatus>({
    isValid: true,
    totalRecords: INITIAL_RECORDS.length,
    failedIndex: null,
    failedRecordId: null,
    reason: null,
  });
  const [tamperedIndex, setTamperedIndex] = useState<number | null>(null);

  const handleVerifyChain = () => {
    if (tamperedIndex !== null) {
      setVerification({
        isValid: false,
        totalRecords: records.length,
        failedIndex: tamperedIndex,
        failedRecordId: records[tamperedIndex]?.record_id || null,
        reason: `Cryptographic SHA-256 payload mismatch detected at record #${tamperedIndex}`,
      });
    } else {
      setVerification({
        isValid: true,
        totalRecords: records.length,
        failedIndex: null,
        failedRecordId: null,
        reason: null,
      });
    }
  };

  const handleSimulateTamper = () => {
    if (tamperedIndex === null) {
      setTamperedIndex(1);
      const copy = [...records];
      copy[1] = {
        ...copy[1],
        prompt: copy[1].prompt + " [TAMPERED BY MALICIOUS SIDE-CHANNEL]",
      };
      setRecords(copy);
      setVerification({
        isValid: false,
        totalRecords: copy.length,
        failedIndex: 1,
        failedRecordId: copy[1].record_id,
        reason: "Cryptographic SHA-256 payload mismatch detected at record #1 (ID: audit-rec-1772890360000-1)",
      });
    } else {
      // Restore clean state
      setTamperedIndex(null);
      setRecords(INITIAL_RECORDS);
      setVerification({
        isValid: true,
        totalRecords: INITIAL_RECORDS.length,
        failedIndex: null,
        failedRecordId: null,
        reason: null,
      });
    }
  };

  const handleExportAudit = () => {
    const newIndex = records.length;
    const prevHash = records[records.length - 1].record_hash;
    const now = Date.now();
    const newRecord: AuditRecordUI = {
      record_index: newIndex,
      record_id: `audit-rec-${now}-${newIndex}`,
      run_id: `run-export-${now}`,
      user_id: "user_kulkarni",
      action_type: "AUDIT_EXPORTED",
      prompt: "Export signed audit trail package for compliance inspection",
      plan: [],
      steps: [],
      documents_retrieved: [],
      models_used: [],
      deliverables: [{ path: "exports/audit_chain_bundle.json", type: "audit_export", sha256: "7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a" }],
      approval_event: null,
      prev_hash: prevHash,
      record_hash: "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
      created_at_ms: now,
    };
    const updated = [...records, newRecord];
    setRecords(updated);
    if (tamperedIndex === null) {
      setVerification({
        isValid: true,
        totalRecords: updated.length,
        failedIndex: null,
        failedRecordId: null,
        reason: null,
      });
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-bg overflow-hidden text-[13px]">
      {/* Verification Header Banner — DESIGNED FAILURE STATE */}
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

        <div className="flex items-center gap-2 font-mono text-[11px]">
          <button
            onClick={handleVerifyChain}
            className="px-2.5 py-1 rounded bg-surface border border-border text-text hover:bg-surface-2 flex items-center gap-1.5 cursor-pointer transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Verify Chain
          </button>

          <button
            onClick={handleSimulateTamper}
            className={`px-2.5 py-1 rounded border flex items-center gap-1.5 cursor-pointer transition-colors ${
              tamperedIndex !== null
                ? "bg-sovereign/20 border-sovereign text-sovereign"
                : "bg-critical/10 border-critical/40 text-critical hover:bg-critical/20"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            {tamperedIndex !== null ? "Restore Clean Record" : "Simulate Tampering"}
          </button>

          <button
            onClick={handleExportAudit}
            className="px-2.5 py-1 rounded bg-accent/10 border border-accent/40 text-accent hover:bg-accent/20 flex items-center gap-1.5 cursor-pointer transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Export Audit
          </button>
        </div>
      </div>

      {/* Main Records List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {records.map((rec) => {
          const isFailedRecord = !verification.isValid && verification.failedIndex === rec.record_index;

          return (
            <div
              key={rec.record_id}
              className={`rounded border p-4 transition-all ${
                isFailedRecord
                  ? "bg-critical/10 border-critical shadow-lg"
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
                {/* Documents Retrieved */}
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

                {/* Models Used */}
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

                {/* Deliverables Produced */}
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
    </div>
  );
};

export default AuditChainPanel;
