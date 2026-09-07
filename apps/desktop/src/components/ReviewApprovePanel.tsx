import React, { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, ChevronRight, FileText, UserCheck } from "lucide-react";
import { DeliverableDocPreview } from "./DeliverableDocPreview";
import { ReviewProvenanceSidebar } from "./ReviewProvenanceSidebar";
import { RejectDeliverableModal } from "./RejectDeliverableModal";
import { ReviewApproveEmptyState } from "./ReviewApproveEmptyState";
import {
  AuditedField,
  ClaimCitation,
  UserIdentity,
  OrgConfig,
  CalcExecutionData,
  ReviewApprovePanelProps,
  ROSTER_USERS,
  DEFAULT_ORG_CONFIG,
  DEFAULT_CALC_EXECUTION,
  DEFAULT_INITIAL_FIELDS,
  DEFAULT_INITIAL_CITATIONS,
} from "./reviewApproveTypes";

export type {
  AuditedField,
  ClaimCitation,
  UserIdentity,
  OrgConfig,
  CalcExecutionData,
  ReviewApprovePanelProps,
};

export const ReviewApprovePanel: React.FC<ReviewApprovePanelProps> = ({
  projectId,
  sessionId,
  projectPath: _projectPath,
  deliverableId: propDeliverableId,
  title: propTitle = "TECHNICAL APPROVAL NOTE: Remaining Life & Inspection Sanction",
  subject: propSubject = "Crude Distillation Column C-101 Remaining Life & Inspection Sanction",
  maker: propMaker = ROSTER_USERS[1],
  checker: propChecker = ROSTER_USERS[0],
  currentUser: propCurrentUser,
  orgConfig: propOrgConfig = DEFAULT_ORG_CONFIG,
  initialFields: propFields,
  initialCitations: propCitations,
  calcExecution: propCalcExecution = DEFAULT_CALC_EXECUTION,
  modelsUsed: propModels = ["glm-ocr", "qwen3-coder:30b", "deepseek-r1:14b"],
  initialStatus: propStatus = "PENDING_CHECK",
  initialStampText: _propStampText = "",
  isConcurrent = false,
  onApproveSuccess,
  onRejectSuccess,
}) => {
  const isDirectMode = Boolean(propDeliverableId || propFields || propCitations);
  const [deliverablesList, setDeliverablesList] = useState<{ id: string; title: string; status: string }[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(propDeliverableId || null);
  const [loading, setLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [rpcError, setRpcError] = useState<string | null>(null);

  const [deliverableId, setDeliverableId] = useState<string>(propDeliverableId || "");
  const [title, setTitle] = useState<string>(propTitle);
  const [subject, setSubject] = useState<string>(propSubject);
  const [maker, setMaker] = useState<UserIdentity>(propMaker);
  const [checker, setChecker] = useState<UserIdentity>(propChecker);
  const [currentUser, setCurrentUser] = useState<UserIdentity>(propCurrentUser || propChecker);
  const [orgConfig, setOrgConfig] = useState<OrgConfig>(propOrgConfig);
  const [fields, setFields] = useState<AuditedField[]>(propFields || DEFAULT_INITIAL_FIELDS);
  const [citations, setCitations] = useState<ClaimCitation[]>(propCitations || DEFAULT_INITIAL_CITATIONS);
  const [calcExecution, setCalcExecution] = useState<CalcExecutionData>(propCalcExecution);
  const [modelsUsed, setModelsUsed] = useState<string[]>(propModels);
  const [status, setStatus] = useState<"DRAFT" | "PENDING_CHECK" | "APPROVED" | "REJECTED">(
    isConcurrent ? "APPROVED" : propStatus
  );
  const [activeCropFieldId, setActiveCropFieldId] = useState<string | null>(null);
  const [isEditingNarrative, setIsEditingNarrative] = useState<boolean>(false);
  const [narrativeText, setNarrativeText] = useState<string>(
    "Ultrasonic thickness gauging indicates nominal wall thinning in shell course 3. Corrosion rate conforms to historical crude distillate service envelope. Remaining operational life meets statutory requirements for extended run sanction."
  );
  const [isRejectModalOpen, setIsRejectModalOpen] = useState<boolean>(false);
  const [rejectionReason, setRejectionReason] = useState<string>("");

  useEffect(() => {
    if (propDeliverableId) setDeliverableId(propDeliverableId);
    if (propTitle) setTitle(propTitle);
    if (propSubject) setSubject(propSubject);
    if (propMaker) setMaker(propMaker);
    if (propChecker) setChecker(propChecker);
    if (propCurrentUser) setCurrentUser(propCurrentUser);
    if (propFields) setFields(propFields);
    if (propCitations) setCitations(propCitations);
  }, [propDeliverableId, propTitle, propSubject, propMaker, propChecker, propCurrentUser, propFields, propCitations]);

  const loadDeliverables = async () => {
    if (typeof window === "undefined" || !(window as any).__TAURI_INTERNALS__) return;
    try {
      setLoading(true);
      setRpcError(null);
      const { invoke } = await import("@tauri-apps/api/core");
      const resp = (await invoke("invoke_core_rpc", {
        request: {
          method: "deliverable/list",
          params: { projectId: projectId || undefined, sessionId: sessionId || undefined },
        },
      })) as any;
      if (resp && resp.deliverables) {
        setDeliverablesList(resp.deliverables);
        if (resp.deliverables.length > 0 && !selectedId) {
          await loadDeliverableDetails(resp.deliverables[0].id);
        }
      } else if (resp && resp.error) {
        setRpcError(typeof resp.error === "string" ? resp.error : resp.error.message || "Failed to list deliverables");
      }
    } catch (err: any) {
      setRpcError(err?.message || String(err) || "Failed to list deliverables from core");
    } finally {
      setLoading(false);
    }
  };

  const loadDeliverableDetails = async (id: string) => {
    if (typeof window === "undefined" || !(window as any).__TAURI_INTERNALS__) return;
    try {
      setLoading(true);
      setSelectedId(id);
      setRpcError(null);
      const { invoke } = await import("@tauri-apps/api/core");
      const resp = (await invoke("invoke_core_rpc", {
        request: { method: "deliverable/get", params: { deliverableId: id } },
      })) as any;
      if (resp && resp.deliverable) {
        const d = resp.deliverable;
        setDeliverableId(d.id);
        setTitle(d.title || propTitle);
        setSubject(d.subject || propSubject);
        if (d.maker) setMaker(d.maker);
        if (d.checker) setChecker(d.checker);
        if (d.orgConfig) setOrgConfig(d.orgConfig);
        if (d.fields) setFields(d.fields);
        if (d.citations) setCitations(d.citations);
        if (d.calcExecution) setCalcExecution(d.calcExecution);
        if (d.modelsUsed) setModelsUsed(d.modelsUsed);
        if (d.narrative) setNarrativeText(d.narrative);
        if (d.status) setStatus(d.status);
      } else if (resp && resp.error) {
        setRpcError(typeof resp.error === "string" ? resp.error : resp.error.message || "Failed to load deliverable");
      }
    } catch (err: any) {
      setRpcError(err?.message || String(err) || "Failed to load deliverable details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isDirectMode && (projectId || sessionId)) {
      loadDeliverables();
    }
  }, [projectId, sessionId]);

  const isMakerSelfApproving = currentUser.id === maker.id;
  const unverifiedCount = fields.filter((f) => f.requires_verification && !f.is_verified).length;
  const uncitedCount = citations.filter((c) => !c.is_cited).length;
  const hasBlockers = isMakerSelfApproving || unverifiedCount > 0 || uncitedCount > 0;

  const handleVerifyField = async (fieldId: string) => {
    setRpcError(null);
    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ && deliverableId) {
      try {
        setActionLoading(true);
        const { invoke } = await import("@tauri-apps/api/core");
        const resp = (await invoke("invoke_core_rpc", {
          request: {
            method: "deliverable/verify_field",
            params: { deliverableId, fieldId, verifiedBy: currentUser.id },
          },
        })) as any;
        if (resp && resp.error) {
          setRpcError(typeof resp.error === "string" ? resp.error : resp.error.message || "Failed to verify field");
          return;
        }
        setActiveCropFieldId(null);
        await loadDeliverableDetails(deliverableId);
      } catch (err: any) {
        setRpcError(err?.message || String(err) || "Field verification rejected by core");
      } finally {
        setActionLoading(false);
      }
    } else {
      setFields((prev) =>
        prev.map((f) => (f.id === fieldId ? { ...f, is_verified: true, requires_verification: false } : f))
      );
      setActiveCropFieldId(null);
    }
  };

  const handleApprove = async () => {
    if (hasBlockers) return;
    setRpcError(null);
    const stamp = `APPROVED BY: ${checker.name} (${checker.designation})\nPREPARED BY: ${maker.name} (${maker.designation})\nDATE: ${new Date().toISOString().split("T")[0]}\nREF: MRPL/INSP/2026/09`;

    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ && deliverableId) {
      try {
        setActionLoading(true);
        const { invoke } = await import("@tauri-apps/api/core");
        const resp = (await invoke("invoke_core_rpc", {
          request: {
            method: "deliverable/approve",
            params: { deliverableId, checker, stampText: stamp },
          },
        })) as any;
        if (resp && resp.error) {
          setRpcError(typeof resp.error === "string" ? resp.error : resp.error.message || "Approval refused by core");
          return;
        }
        await loadDeliverableDetails(deliverableId);
        if (onApproveSuccess) {
          onApproveSuccess(resp?.approvalResult?.auditRecord || { action: "APPROVED", deliverableId, maker, checker });
        }
      } catch (err: any) {
        setRpcError(err?.message || String(err) || "Core approval RPC failed");
      } finally {
        setActionLoading(false);
      }
    } else {
      setStatus("APPROVED");
      const auditRecord = {
        action: "APPROVED",
        deliverableId,
        maker,
        checker,
        approvedAt: new Date().toISOString(),
        stampText: stamp,
        orgConfig,
      };
      if (onApproveSuccess) onApproveSuccess(auditRecord);
    }
  };

  const handleReject = async () => {
    if (!rejectionReason.trim()) return;
    setRpcError(null);

    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ && deliverableId) {
      try {
        setActionLoading(true);
        const { invoke } = await import("@tauri-apps/api/core");
        const resp = (await invoke("invoke_core_rpc", {
          request: {
            method: "deliverable/reject",
            params: { deliverableId, checker, reason: rejectionReason },
          },
        })) as any;
        if (resp && resp.error) {
          setRpcError(typeof resp.error === "string" ? resp.error : resp.error.message || "Rejection refused by core");
          return;
        }
        setIsRejectModalOpen(false);
        await loadDeliverableDetails(deliverableId);
        if (onRejectSuccess) {
          onRejectSuccess(resp?.rejectionResult?.auditRecord || { action: "REJECTED", deliverableId, checker, reason: rejectionReason });
        }
      } catch (err: any) {
        setRpcError(err?.message || String(err) || "Core rejection RPC failed");
      } finally {
        setActionLoading(false);
      }
    } else {
      setStatus("REJECTED");
      setIsRejectModalOpen(false);
      const auditRecord = {
        action: "REJECTED",
        deliverableId,
        checker,
        reason: rejectionReason,
        rejectedAt: new Date().toISOString(),
      };
      if (onRejectSuccess) onRejectSuccess(auditRecord);
    }
  };

  if (!isDirectMode && deliverablesList.length === 0 && !loading && !propFields) {
    return <ReviewApproveEmptyState loading={loading} onRefresh={loadDeliverables} />;
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0B0F14] text-[#E6EDF3] text-[13px] overflow-hidden">
      {/* Top Header Bar */}
      <div className="h-10 bg-[#121821] border-b border-[#263241] px-4 flex items-center justify-between shrink-0 font-mono text-[12px]">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-[#4C8DF6]" />
          <span className="font-bold text-[#E6EDF3]">MAKER-CHECKER WORKBENCH</span>
          <span className="text-[#9AA7B4]">·</span>
          <span className="text-[#9AA7B4]">{deliverableId || "DELIV-ACTIVE"}</span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-[#0B0F14] px-2 py-0.5 border border-[#263241] rounded-[4px]">
            <UserCheck className="w-3.5 h-3.5 text-[#10B981]" />
            <span className="text-[#9AA7B4]">Role:</span>
            <select
              value={currentUser.id}
              onChange={(e) => {
                const u = ROSTER_USERS.find((usr) => usr.id === e.target.value);
                if (u) setCurrentUser(u);
              }}
              className="bg-transparent text-[#E6EDF3] font-bold text-[11px] focus:outline-none cursor-pointer"
            >
              <option value="user_kulkarni" className="bg-[#121821]">P. V. Kulkarni (Checker)</option>
              <option value="user_sharma" className="bg-[#121821]">A. Sharma (Maker)</option>
            </select>
          </div>
          <span className={`px-2 py-0.5 rounded-[4px] font-mono text-[11px] font-bold ${
            status === "APPROVED" ? "bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/40" :
            status === "REJECTED" ? "bg-[#EF4444]/20 text-[#EF4444] border border-[#EF4444]/40" :
            "bg-[#F59E0B]/20 text-[#F59E0B] border border-[#F59E0B]/40"
          }`}>
            {status}
          </span>
        </div>
      </div>

      {/* Persistent RPC Error Banner */}
      {rpcError && (
        <div data-testid="rpc-error-banner" className="bg-[#EF4444]/20 border-b border-[#EF4444]/50 px-4 py-2 text-[12px] flex items-center justify-between text-[#EF4444] font-mono">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-[#EF4444] shrink-0" />
            <span>CORE ERROR: {rpcError}</span>
          </div>
          <button
            onClick={() => setRpcError(null)}
            className="text-[#E6EDF3] hover:text-white px-2 py-0.5 rounded bg-[#EF4444]/30 hover:bg-[#EF4444]/50 cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Concurrent Signed Notice */}
      {isConcurrent && (
        <div className="bg-[#10B981]/15 border-b border-[#10B981]/30 px-4 py-2 text-[12px] flex items-center justify-between text-[#10B981]">
          <div className="flex items-center gap-2 font-mono">
            <CheckCircle className="w-4 h-4" />
            <span className="font-bold">APPROVED & SIGNED</span>
            <span>— This deliverable was approved by {checker.name} ({checker.designation}).</span>
          </div>
        </div>
      )}

      {/* Blocking Warning Banner */}
      {!isConcurrent && hasBlockers && (
        <div data-testid="blocking-banner" className="bg-[#EF4444]/15 border-b border-[#EF4444]/30 px-4 py-2 text-[12px] flex items-center justify-between text-[#EF4444]">
          <div className="flex items-center gap-2 font-mono">
            <AlertTriangle className="w-4 h-4 text-[#EF4444] shrink-0" />
            <span>
              {isMakerSelfApproving
                ? `You prepared this deliverable (${maker.name}). Maker cannot check their own work — please switch to an independent checker.`
                : `Approval blocked: ${unverifiedCount} unverified field(s) require crop review.`}
            </span>
          </div>
          {!isMakerSelfApproving && unverifiedCount > 0 && (
            <button
              data-testid="jump-unverified-link"
              onClick={() => {
                const first = fields.find((f) => f.requires_verification && !f.is_verified);
                if (first) setActiveCropFieldId(first.id);
              }}
              className="text-[#E6EDF3] bg-[#EF4444]/30 hover:bg-[#EF4444]/50 px-2 py-0.5 rounded-[4px] text-[11px] font-mono flex items-center gap-1 cursor-pointer"
            >
              Review Provenance <ChevronRight className="w-3 h-3" />
            </button>
          )}
        </div>
      )}

      {/* Main Two-Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        <DeliverableDocPreview
          orgConfig={orgConfig}
          subject={subject}
          title={title}
          isEditingNarrative={isEditingNarrative}
          setIsEditingNarrative={setIsEditingNarrative}
          narrativeText={narrativeText}
          setNarrativeText={setNarrativeText}
          calcExecution={calcExecution}
          status={status}
          isConcurrent={isConcurrent}
          checker={checker}
          maker={maker}
        />

        <ReviewProvenanceSidebar
          fields={fields}
          citations={citations}
          modelsUsed={modelsUsed}
          activeCropFieldId={activeCropFieldId}
          setActiveCropFieldId={setActiveCropFieldId}
          actionLoading={actionLoading}
          isConcurrent={isConcurrent}
          status={status}
          hasBlockers={hasBlockers}
          onVerifyField={handleVerifyField}
          onOpenRejectModal={() => setIsRejectModalOpen(true)}
          onApprove={handleApprove}
        />
      </div>

      <RejectDeliverableModal
        isOpen={isRejectModalOpen}
        rejectionReason={rejectionReason}
        setRejectionReason={setRejectionReason}
        actionLoading={actionLoading}
        onClose={() => setIsRejectModalOpen(false)}
        onConfirmReject={handleReject}
      />
    </div>
  );
};
