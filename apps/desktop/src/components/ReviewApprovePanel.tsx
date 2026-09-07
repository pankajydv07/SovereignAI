import React, { useState } from "react";
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Edit3,
  Lock,
  ExternalLink,
  ChevronRight,
} from "lucide-react";
import { InlineCropPreview } from "./InlineCropPreview";

export interface AuditedField {
  id: string;
  field_name: string;
  value: string;
  unit?: string;
  confidence: number;
  is_verified: boolean;
  requires_verification: boolean;
  page: number;
  bbox?: [number, number, number, number];
  imagePath: string;
}

export interface ClaimCitation {
  id: string;
  doc_id: string;
  title: string;
  clause_or_section: string;
  claim_text: string;
  is_cited: boolean;
}

export interface UserIdentity {
  id: string;
  name: string;
  designation: string;
}

export interface OrgConfig {
  orgName: string;
  divisionName: string;
  logoText: string;
  terminology: string;
}

export interface ReviewApprovePanelProps {
  deliverableId: string;
  title: string;
  subject: string;
  maker: UserIdentity;
  checker: UserIdentity;
  currentUser: UserIdentity;
  orgConfig?: OrgConfig;
  initialFields?: AuditedField[];
  initialCitations?: ClaimCitation[];
  calcExecution?: {
    run_id: string;
    calc_type: string;
    status: string;
    executed_derivation: {
      equipment_tag: string;
      governing_standard: string;
      t_actual_mm: number;
      t_min_mm: number;
      corrosion_rate_mm_yr: number;
      remaining_life_years: number;
    };
  };
  modelsUsed?: string[];
  initialStatus?: "DRAFT" | "PENDING_CHECK" | "APPROVED" | "REJECTED";
  initialStampText?: string;
  isConcurrent?: boolean;
  onApproveSuccess?: (auditRecord: unknown) => void;
  onRejectSuccess?: (auditRecord: unknown) => void;
}

export const ReviewApprovePanel: React.FC<ReviewApprovePanelProps> = ({
  deliverableId,
  title,
  subject,
  maker,
  checker,
  currentUser,
  orgConfig = {
    orgName: "MANGALORE REFINERY AND PETROCHEMICALS LIMITED",
    divisionName: "Inspection & Engineering Division",
    logoText: "MRPL / ONGC GROUP",
    terminology: "APPROVED",
  },
  initialFields = [],
  initialCitations = [],
  calcExecution,
  modelsUsed = [],
  initialStatus = "PENDING_CHECK",
  initialStampText = "",
  isConcurrent = false,
  onApproveSuccess,
  onRejectSuccess,
}) => {
  const [fields, setFields] = useState<AuditedField[]>(initialFields);
  const [citations, setCitations] = useState<ClaimCitation[]>(initialCitations);
  const [status, setStatus] = useState<"DRAFT" | "PENDING_CHECK" | "APPROVED" | "REJECTED">(
    isConcurrent ? "APPROVED" : initialStatus
  );
  const [stampText, setStampText] = useState<string>(initialStampText);
  const [activeCropFieldId, setActiveCropFieldId] = useState<string | null>(null);

  // Edit & approve state
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editedNarrative, setEditedNarrative] = useState<string>("");
  const [originalNarrative] = useState<string>("");

  // Rejection modal state
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);
  const [rejectReason, setRejectReason] = useState<string>("");
  const [auditRecordLink, setAuditRecordLink] = useState<string | null>(null);

  // Precondition calculations
  const unverifiedFieldsCount = fields.filter((f) => !f.is_verified).length;
  const uncitedClaimsCount = citations.filter((c) => !c.is_cited).length;
  const isMakerCurrentUser = currentUser.id.toLowerCase() === maker.id.toLowerCase();
  const isCalcVerified = calcExecution?.status === "VERIFIED";

  const isBlocked =
    unverifiedFieldsCount > 0 ||
    uncitedClaimsCount > 0 ||
    isMakerCurrentUser ||
    !isCalcVerified ||
    status === "APPROVED" ||
    status === "REJECTED";

  // Precondition explanation banner message
  const getBlockingMessage = (): string => {
    if (status === "APPROVED") {
      return `This deliverable was approved by ${checker.name} (${checker.designation}). Screen is read-only.`;
    }
    if (status === "REJECTED") {
      return `This deliverable was rejected by ${checker.name}. Screen is read-only.`;
    }
    if (isMakerCurrentUser) {
      return `Cannot approve: You prepared this deliverable (${maker.name}). A different checker must approve it per maker-checker separation of duties.`;
    }
    const reasons: string[] = [];
    if (unverifiedFieldsCount > 0) {
      reasons.push(`${unverifiedFieldsCount} field(s) unverified`);
    }
    if (uncitedClaimsCount > 0) {
      reasons.push(`${uncitedClaimsCount} claim(s) without citation`);
    }
    if (!isCalcVerified) {
      reasons.push(`Calculation status is '${calcExecution?.status}' (expected VERIFIED)`);
    }
    return `Cannot approve: ${reasons.join(" · ")}`;
  };

  // Jump link handler to focus unverified item
  const handleJumpToUnverified = () => {
    const firstUnverified = fields.find((f) => !f.is_verified);
    if (firstUnverified) {
      setActiveCropFieldId(firstUnverified.id);
      const el = document.getElementById(`field-row-${firstUnverified.id}`);
      if (el && typeof el.scrollIntoView === "function") {
        el.scrollIntoView({ behavior: "smooth" });
      }
    } else {
      const firstUncited = citations.find((c) => !c.is_cited);
      if (firstUncited) {
        const el = document.getElementById(`citation-row-${firstUncited.id}`);
        if (el && typeof el.scrollIntoView === "function") {
          el.scrollIntoView({ behavior: "smooth" });
        }
      }
    }
  };

  // Human field verification (provenance backed)
  const handleConfirmVerifyField = (fieldId: string) => {
    setFields((prev) =>
      prev.map((f) => (f.id === fieldId ? { ...f, is_verified: true, requires_verification: false } : f))
    );
    setActiveCropFieldId(null);
  };

  // Citation verify helper
  const handleCiteClaim = (citationId: string) => {
    setCitations((prev) =>
      prev.map((c) => (c.id === citationId ? { ...c, is_cited: true } : c))
    );
  };

  // Core Approval Action
  const handleApprove = () => {
    if (isBlocked) return;

    const timestamp = new Date().toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    const dateStr = new Date().toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
    const stamp = `APPROVED BY: ${currentUser.name} (${currentUser.designation}) · ${orgConfig.terminology} · ${timestamp} · ${dateStr}`;

    const auditRecord = {
      audit_id: `audit-${Date.now()}`,
      deliverable_id: deliverableId,
      action: editedNarrative !== originalNarrative ? "EDITED_AND_APPROVED" : "APPROVED",
      maker: maker,
      checker: currentUser,
      identity_source: "os_user_session",
      timestamp: `${timestamp} · ${dateStr}`,
      stamp_text: stamp,
      word_diffs: editedNarrative !== originalNarrative ? [editedNarrative] : [],
    };

    setStatus("APPROVED");
    setStampText(stamp);
    setAuditRecordLink(`#audit-${auditRecord.audit_id}`);
    onApproveSuccess?.(auditRecord);
  };

  // Rejection submit
  const handleConfirmReject = () => {
    if (!rejectReason.trim()) return;

    const timestamp = new Date().toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });

    const auditRecord = {
      audit_id: `audit-${Date.now()}`,
      deliverable_id: deliverableId,
      action: "REJECTED",
      maker: maker,
      checker: currentUser,
      identity_source: "os_user_session",
      timestamp,
      reason: rejectReason.trim(),
    };

    setStatus("REJECTED");
    setShowRejectModal(false);
    onRejectSuccess?.(auditRecord);
  };

  return (
    <div
      data-testid="review-approve-panel"
      className="flex flex-col h-full w-full bg-[#0B0F14] text-[#E6EDF3] font-sans overflow-hidden select-none"
    >
      {/* Top Header & Status Bar */}
      <div className="h-11 bg-[#121821] border-b border-[#263241] px-4 flex items-center justify-between text-[12px] font-mono">
        <div className="flex items-center gap-3">
          <span className="text-[#9AA7B4] font-semibold">DELIVERABLE REVIEW</span>
          <span className="text-[#263241]">│</span>
          <span className="text-[#E6EDF3] font-semibold">{deliverableId}</span>
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#1A222E] border border-[#263241] text-[#4C8DF6]">
            {orgConfig.logoText}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {status === "APPROVED" ? (
            <div className="flex items-center gap-2 text-[#10B981] font-bold">
              <CheckCircle className="w-4 h-4" />
              <span>APPROVED & SIGNED</span>
              {auditRecordLink && (
                <a
                  href={auditRecordLink}
                  className="text-[#4C8DF6] hover:underline text-[11px] font-normal flex items-center gap-1 ml-2"
                >
                  View Audit Record <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          ) : status === "REJECTED" ? (
            <div className="flex items-center gap-2 text-[#EF4444] font-bold">
              <XCircle className="w-4 h-4" />
              <span>REJECTED</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-[#F59E0B] font-bold">
              <Lock className="w-4 h-4" />
              <span>MAKER-CHECKER GATE ACTIVE</span>
            </div>
          )}
        </div>
      </div>

      {/* BLOCKING Banner when preconditions fail or terminal status */}
      {(isBlocked || (status as string) === "APPROVED" || (status as string) === "REJECTED") && (
        <div
          data-testid="blocking-banner"
          className={`flex items-center justify-between px-4 py-2.5 border-b text-[12px] font-mono transition-colors ${
            (status as string) === "APPROVED"
              ? "bg-[#10B981]/10 border-[#10B981]/30 text-[#10B981]"
              : (status as string) === "REJECTED"
              ? "bg-[#EF4444]/10 border-[#EF4444]/30 text-[#EF4444]"
              : "bg-[#EF4444]/10 border-[#EF4444]/40 text-[#EF4444]"
          }`}
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span className="font-semibold">{getBlockingMessage()}</span>
          </div>

          {status !== "APPROVED" && status !== "REJECTED" && (unverifiedFieldsCount > 0 || uncitedClaimsCount > 0) && (
            <button
              data-testid="jump-unverified-link"
              onClick={handleJumpToUnverified}
              className="text-[#4C8DF6] hover:underline font-bold flex items-center gap-1 text-[11px] cursor-pointer ml-4"
            >
              Jump to unverified item <ChevronRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      )}

      {/* Main Viewport Split 50/50 */}
      <div className="flex flex-1 h-full w-full overflow-hidden">
        {/* Left Pane (50%): Deliverable White Page Paper Preview */}
        <div className="w-1/2 h-full bg-[#1A222E] p-6 overflow-y-auto flex flex-col items-center">
          <div
            data-testid="deliverable-paper-page"
            className="w-full max-w-2xl bg-white text-[#1F2328] rounded-[4px] border border-[#D0D7DE] p-8 shadow-lg font-sans text-[13px] leading-relaxed my-auto"
          >
            {/* Org Letterhead */}
            <div className="border-b-2 border-[#1F2328] pb-4 mb-6 text-center">
              <div className="text-[11px] font-mono uppercase tracking-widest text-[#57606A] font-bold">
                {orgConfig.logoText}
              </div>
              <div className="text-[18px] font-bold tracking-tight text-[#1F2328] uppercase mt-1">
                {orgConfig.orgName}
              </div>
              <div className="text-[12px] font-semibold text-[#57606A] mt-0.5">
                {orgConfig.divisionName}
              </div>
            </div>

            {/* Document Title & Metadata */}
            <div className="mb-6">
              <div className="text-[11px] font-mono text-[#57606A] uppercase mb-1">
                REF: {deliverableId} · DATE: 06 SEP 2026
              </div>
              <div className="text-[15px] font-bold text-[#1F2328] leading-snug">{title}</div>
              <div className="text-[12px] font-semibold text-[#57606A] mt-1">SUBJECT: {subject}</div>
            </div>

            {/* Document Body Narrative & Edit mode */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-mono font-bold text-[#57606A] uppercase">
                  1. Executive Summary & Assessment
                </span>
                {status !== "APPROVED" && status !== "REJECTED" && (
                  <button
                    data-testid="edit-narrative-btn"
                    onClick={() => setIsEditing(!isEditing)}
                    className="text-[#0B62D6] hover:underline text-[11px] font-mono flex items-center gap-1 cursor-pointer"
                  >
                    <Edit3 className="w-3 h-3" />
                    {isEditing ? "Done Editing" : "Edit & Approve"}
                  </button>
                )}
              </div>

              {isEditing ? (
                <textarea
                  data-testid="narrative-textarea"
                  value={editedNarrative}
                  onChange={(e) => setEditedNarrative(e.target.value)}
                  className="w-full h-28 p-2.5 bg-[#F6F8FA] border border-[#0B62D6] rounded text-[13px] font-sans text-[#1F2328] focus:outline-none"
                />
              ) : (
                <div className="p-3 bg-[#F6F8FA] border border-[#D0D7DE] rounded text-[13px] text-[#1F2328]">
                  {editedNarrative !== originalNarrative ? (
                    <div>
                      <span className="text-[#57606A] font-mono text-[11px] block mb-1">
                        [CHECKER EDITED CONTENT]:
                      </span>
                      <span>{editedNarrative}</span>
                    </div>
                  ) : (
                    <span>{editedNarrative}</span>
                  )}
                </div>
              )}
            </div>

            {/* Executed Derivation Table — only shown when a calc run is attached */}
            {calcExecution && (
              <div className="mb-6 border border-[#D0D7DE] rounded overflow-hidden">
                <div className="bg-[#EEF1F4] px-3 py-2 border-b border-[#D0D7DE] font-mono text-[11px] font-bold text-[#1F2328] flex justify-between">
                  <span>EXECUTED CALCULATION DERIVATION</span>
                  <span>RUN ID: {calcExecution.run_id}</span>
                </div>
                <div className="p-3 text-[12px] font-mono space-y-1.5 bg-[#F6F8FA]">
                  <div className="flex justify-between">
                    <span className="text-[#57606A]">Equipment Tag:</span>
                    <span className="font-bold text-[#1F2328]">{calcExecution.executed_derivation.equipment_tag}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#57606A]">Governing Standard:</span>
                    <span className="font-bold text-[#0B62D6]">{calcExecution.executed_derivation.governing_standard}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#57606A]">Actual Thickness (t_actual):</span>
                    <span className="font-bold text-[#1F2328]">{calcExecution.executed_derivation.t_actual_mm} mm</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#57606A]">Minimum Required (t_min):</span>
                    <span className="font-bold text-[#1F2328]">{calcExecution.executed_derivation.t_min_mm} mm</span>
                  </div>
                  <div className="flex justify-between border-t border-[#D0D7DE] pt-1 mt-1 font-bold text-[#10B981]">
                    <span>Calculated Safe Remaining Life:</span>
                    <span>{calcExecution.executed_derivation.remaining_life_years} YEARS</span>
                  </div>
                </div>
              </div>
            )}

            {/* Bottom Stamp or Non-Removable Draft Attestation Banner */}
            {status === "APPROVED" || stampText ? (
              <div className="p-4 bg-[#10B981]/10 border-2 border-[#10B981] rounded text-center font-mono text-[12px] font-bold text-[#10B981]">
                <div className="text-[14px] uppercase mb-1">{orgConfig.terminology}</div>
                <div>{stampText || `APPROVED BY: ${checker.name} (${checker.designation}) · ${orgConfig.terminology}`}</div>
                <div className="text-[10px] font-normal text-[#57606A] mt-1">
                  PREPARED BY: {maker.name} ({maker.designation}) · CHECKED BY: {checker.name} ({checker.designation})
                </div>
              </div>
            ) : (
              <div className="p-3 bg-[#EEF1F4] border border-dashed border-[#57606A] rounded text-center font-mono text-[11px] text-[#57606A] uppercase font-bold">
                DRAFT — requires approval by competent authority
              </div>
            )}
          </div>
        </div>

        {/* Right Pane (50%): Evidence Panel (Citations, Extracted Fields, Provenance) */}
        <div className="w-1/2 h-full bg-[#0B0F14] border-l border-[#263241] flex flex-col overflow-hidden">
          <div className="p-3 border-b border-[#263241] bg-[#121821] font-mono text-[12px] font-semibold text-[#9AA7B4] flex items-center justify-between">
            <span>EVIDENCE & PROVENANCE PANEL</span>
            <span className="text-[11px] text-[#4C8DF6]">
              {unverifiedFieldsCount} unverified · {uncitedClaimsCount} uncited
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-6">
            {/* Section 1: Extracted Fields & Confidence */}
            <div>
              <div className="font-mono text-[12px] font-bold text-[#E6EDF3] mb-2 uppercase flex justify-between">
                <span>1. Extracted Inspection Fields ({fields.length})</span>
                <span className="text-[#9AA7B4] text-[11px] font-normal">Machine Extraction</span>
              </div>

              <div className="space-y-2">
                {fields.map((field) => (
                  <div key={field.id} id={`field-row-${field.id}`}>
                    <div className="p-2.5 bg-[#121821] border border-[#263241] rounded flex items-center justify-between text-[12px]">
                      <div className="font-mono">
                        <span className="text-[#9AA7B4]">{field.field_name}: </span>
                        <span className="text-[#E6EDF3] font-bold select-all">
                          {field.value} {field.unit || ""}
                        </span>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="font-mono text-[11px]">
                          <span className="text-[#9AA7B4]">conf: </span>
                          <span
                            className={`font-semibold ${
                              field.confidence < 0.8 ? "text-[#F59E0B]" : "text-[#10B981]"
                            }`}
                          >
                            {field.confidence.toFixed(2)}
                          </span>
                        </div>

                        {field.is_verified ? (
                          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/40">
                            VERIFIED
                          </span>
                        ) : (
                          <button
                            data-testid={`verify-field-btn-${field.id}`}
                            onClick={() => setActiveCropFieldId(field.id)}
                            className="px-2.5 py-1 rounded text-[11px] font-mono font-bold bg-[#F59E0B] hover:bg-[#D98206] text-[#0B0F14] cursor-pointer"
                          >
                            Verify
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Inline Crop Preview when verify button clicked */}
                    {activeCropFieldId === field.id && (
                      <InlineCropPreview
                        fieldId={field.id}
                        fieldName={field.field_name}
                        value={field.value}
                        unit={field.unit}
                        confidence={field.confidence}
                        page={field.page}
                        bbox={field.bbox}
                        imagePath={field.imagePath}
                        onConfirmVerify={handleConfirmVerifyField}
                        onCancel={() => setActiveCropFieldId(null)}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Section 2: Citations List */}
            <div>
              <div className="font-mono text-[12px] font-bold text-[#E6EDF3] mb-2 uppercase flex justify-between">
                <span>2. Cited Standards & Knowledge Base</span>
                <span className="text-[#9AA7B4] text-[11px] font-normal">KB Grounding</span>
              </div>

              <div className="space-y-2">
                {citations.map((cite) => (
                  <div
                    key={cite.id}
                    id={`citation-row-${cite.id}`}
                    className={`p-2.5 bg-[#121821] border rounded text-[12px] ${
                      cite.is_cited ? "border-[#263241]" : "border-[#EF4444]"
                    }`}
                  >
                    <div className="flex items-center justify-between font-mono text-[11px] mb-1">
                      <span className="text-[#4C8DF6] font-bold">{cite.doc_id}</span>
                      <span className="text-[#9AA7B4]">{cite.clause_or_section}</span>
                    </div>

                    <div className="text-[#E6EDF3] text-[12px] mb-2">{cite.claim_text}</div>

                    <div className="flex justify-end">
                      {cite.is_cited ? (
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-[#10B981]/20 text-[#10B981]">
                          CITED IN KB
                        </span>
                      ) : (
                        <button
                          onClick={() => handleCiteClaim(cite.id)}
                          className="px-2.5 py-1 rounded text-[11px] font-mono font-bold bg-[#EF4444] hover:bg-[#DC2626] text-[#FFFFFF] cursor-pointer"
                        >
                          Confirm Citation Link
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Section 3: System Provenance */}
            <div>
              <div className="font-mono text-[12px] font-bold text-[#E6EDF3] mb-2 uppercase">
                3. System Provenance Attestation
              </div>

              <div className="p-3 bg-[#121821] border border-[#263241] rounded font-mono text-[11px] space-y-2 text-[#9AA7B4]">
                <div className="flex justify-between">
                  <span>Models Used:</span>
                  <span className="text-[#E6EDF3]">{modelsUsed.length > 0 ? modelsUsed.join(" · ") : "(none recorded)"}</span>
                </div>
                {calcExecution && (
                  <div className="flex justify-between">
                    <span>Calc Run ID:</span>
                    <span className="text-[#E6EDF3]">{calcExecution.run_id}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>Identity Source:</span>
                  <span className="text-[#4C8DF6]">os_user_session (local)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Action Bar (Maker & Checker chips, Reject, Edit, Approve with 24px gap) */}
      <div className="h-14 bg-[#121821] border-t border-[#263241] px-6 flex items-center justify-between select-none">
        {/* Maker and Checker Identity Chips */}
        <div className="flex items-center gap-4 font-mono text-[12px]">
          <div className="flex items-center gap-1.5 px-3 py-1 bg-[#1A222E] border border-[#263241] rounded">
            <span className="text-[#9AA7B4]">MAKER:</span>
            <span className="text-[#E6EDF3] font-semibold">{maker.name}</span>
            <span className="text-[#6B7A8A]">({maker.designation})</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1 bg-[#1A222E] border border-[#263241] rounded">
            <span className="text-[#9AA7B4]">CHECKER:</span>
            <span className="text-[#E6EDF3] font-semibold">{checker.name}</span>
            <span className="text-[#6B7A8A]">({checker.designation})</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center">
          <button
            data-testid="reject-btn"
            disabled={status === "APPROVED" || status === "REJECTED"}
            onClick={() => setShowRejectModal(true)}
            className="px-3.5 py-2 bg-[#1A222E] hover:bg-[#EF4444]/20 border border-[#263241] hover:border-[#EF4444] text-[#EF4444] font-mono font-semibold rounded-[4px] text-[12px] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Reject with reason
          </button>

          <button
            data-testid="edit-approve-btn"
            disabled={status === "APPROVED" || status === "REJECTED"}
            onClick={() => setIsEditing(!isEditing)}
            className="ml-2 px-3.5 py-2 bg-[#1A222E] hover:bg-[#263241] border border-[#263241] text-[#4C8DF6] font-mono font-semibold rounded-[4px] text-[12px] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Edit & approve
          </button>

          {/* 24px GAP BEFORE APPROVE (mr-6 / gap-6 equivalent -> margin-left: 24px) */}
          <button
            data-testid="approve-btn"
            disabled={isBlocked}
            onClick={handleApprove}
            style={{ marginLeft: "24px" }}
            className={`px-5 py-2 font-mono font-bold rounded-[4px] text-[12px] transition-colors ${
              isBlocked
                ? "bg-[#263241] text-[#6B7A8A] border border-[#263241] cursor-not-allowed"
                : "bg-[#10B981] hover:bg-[#0D9668] text-[#0B0F14] cursor-pointer shadow-md"
            }`}
          >
            Approve
          </button>
        </div>
      </div>

      {/* Rejection Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-[#0B0F14]/80 flex items-center justify-center z-50 p-4 font-sans">
          <div
            data-testid="rejection-modal"
            className="bg-[#121821] border border-[#263241] rounded-[4px] w-full max-w-md p-5 text-[#E6EDF3] shadow-2xl"
          >
            <div className="font-mono text-[14px] font-bold text-[#EF4444] mb-2 uppercase flex items-center justify-between">
              <span>REJECT DELIVERABLE</span>
              <button onClick={() => setShowRejectModal(false)} className="text-[#9AA7B4] hover:text-[#E6EDF3]">
                ✕
              </button>
            </div>

            <p className="text-[12px] text-[#9AA7B4] mb-3">
              Rejection enters the official audit trail. Please state the mandatory technical reason for returning this deliverable to the maker.
            </p>

            <textarea
              data-testid="rejection-reason-input"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g., Corrosion rate calculation formula needs validation against API 570 Section 7.1..."
              className="w-full h-24 p-2.5 bg-[#0B0F14] border border-[#263241] rounded text-[12px] font-mono text-[#E6EDF3] focus:outline-none focus:border-[#EF4444] mb-4"
            />

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowRejectModal(false)}
                className="px-3 py-1.5 bg-[#1A222E] hover:bg-[#263241] text-[#9AA7B4] rounded font-mono text-[12px]"
              >
                Cancel
              </button>
              <button
                data-testid="submit-rejection-btn"
                disabled={!rejectReason.trim()}
                onClick={handleConfirmReject}
                className="px-4 py-1.5 bg-[#EF4444] hover:bg-[#DC2626] text-[#FFFFFF] font-mono font-bold rounded text-[12px] disabled:opacity-40"
              >
                Submit Rejection to Audit Record
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
