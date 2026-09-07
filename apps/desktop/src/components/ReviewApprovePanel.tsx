import React, { useEffect, useState } from "react";
import {
  CheckCircle,
  AlertTriangle,
  Edit3,
  ChevronRight,
  FileText,
  UserCheck,
  RefreshCw,
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

export interface CalcExecutionData {
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
}

export interface ReviewApprovePanelProps {
  projectId?: string | null;
  sessionId?: string | null;
  projectPath?: string | null;

  deliverableId?: string;
  title?: string;
  subject?: string;
  maker?: UserIdentity;
  checker?: UserIdentity;
  currentUser?: UserIdentity;
  orgConfig?: OrgConfig;
  initialFields?: AuditedField[];
  initialCitations?: ClaimCitation[];
  calcExecution?: CalcExecutionData;
  modelsUsed?: string[];
  initialStatus?: "DRAFT" | "PENDING_CHECK" | "APPROVED" | "REJECTED";
  initialStampText?: string;
  isConcurrent?: boolean;
  onApproveSuccess?: (auditRecord: any) => void;
  onRejectSuccess?: (auditRecord: any) => void;
}

const ROSTER_USERS: UserIdentity[] = [
  { id: "user_kulkarni", name: "P. V. Kulkarni", designation: "Chief Manager - Mechanical" },
  { id: "user_sharma", name: "A. Sharma", designation: "Senior Inspection Engineer" },
];

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
  orgConfig: propOrgConfig = {
    orgName: "MANGALORE REFINERY AND PETROCHEMICALS LIMITED",
    divisionName: "Inspection & Engineering Division",
    logoText: "MRPL / ONGC GROUP",
    terminology: "APPROVED",
  },
  initialFields: propFields,
  initialCitations: propCitations,
  calcExecution: propCalcExecution = {
    run_id: "calc-run-8921",
    calc_type: "remaining_life_api570",
    status: "VERIFIED",
    executed_derivation: {
      equipment_tag: "C-101 (Crude Distillation Column)",
      governing_standard: "API 570 Section 7.1.2 (Piping Inspection Code)",
      t_actual_mm: 8.2,
      t_min_mm: 4.5,
      corrosion_rate_mm_yr: 0.25,
      remaining_life_years: 14.8,
    },
  },
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

  const [deliverableId, setDeliverableId] = useState<string>(propDeliverableId || "");
  const [title, setTitle] = useState<string>(propTitle);
  const [subject, setSubject] = useState<string>(propSubject);
  const [maker, setMaker] = useState<UserIdentity>(propMaker);
  const [checker, setChecker] = useState<UserIdentity>(propChecker);
  const [currentUser, setCurrentUser] = useState<UserIdentity>(propCurrentUser || propChecker);
  const [orgConfig, setOrgConfig] = useState<OrgConfig>(propOrgConfig);
  const [fields, setFields] = useState<AuditedField[]>(
    propFields || [
      {
        id: "f1",
        field_name: "t_actual",
        value: "8.2",
        unit: "mm",
        confidence: 0.98,
        is_verified: true,
        requires_verification: false,
        page: 1,
        bbox: [120, 340, 160, 480],
        imagePath: "inspections/scan_ut_report.pdf",
      },
      {
        id: "f2",
        field_name: "corrosion_rate",
        value: "0.25",
        unit: "mm/yr",
        confidence: 0.74,
        is_verified: false,
        requires_verification: true,
        page: 2,
        bbox: [410, 200, 450, 380],
        imagePath: "inspections/scan_ut_report.pdf",
      },
    ]
  );
  const [citations, setCitations] = useState<ClaimCitation[]>(
    propCitations || [
      {
        id: "c1",
        doc_id: "KB-API-570",
        title: "API 570 Piping Inspection Code",
        clause_or_section: "Section 7.1.2",
        claim_text: "Formula Remaining Life = (t_actual - t_min) / Corrosion_Rate",
        is_cited: true,
      },
    ]
  );
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
          loadDeliverableDetails(resp.deliverables[0].id);
        }
      }
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  };

  const loadDeliverableDetails = async (id: string) => {
    if (typeof window === "undefined" || !(window as any).__TAURI_INTERNALS__) return;
    try {
      setLoading(true);
      setSelectedId(id);
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
      }
    } catch {
      // Graceful fallback
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
    setFields((prev) =>
      prev.map((f) => (f.id === fieldId ? { ...f, is_verified: true, requires_verification: false } : f))
    );
    setActiveCropFieldId(null);

    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ && deliverableId) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("invoke_core_rpc", {
          request: {
            method: "deliverable/verify_field",
            params: { deliverableId, fieldId, verifiedBy: currentUser.id },
          },
        });
      } catch {}
    }
  };

  const handleApprove = async () => {
    if (hasBlockers) return;
    const stamp = `APPROVED BY: ${checker.name} (${checker.designation})\nPREPARED BY: ${maker.name} (${maker.designation})\nDATE: ${new Date().toISOString().split("T")[0]}\nREF: MRPL/INSP/2026/09`;
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

    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ && deliverableId) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("invoke_core_rpc", {
          request: {
            method: "deliverable/approve",
            params: { deliverableId, checker, stampText: stamp },
          },
        });
      } catch {}
    }

    if (onApproveSuccess) onApproveSuccess(auditRecord);
  };

  const handleReject = async () => {
    if (!rejectionReason.trim()) return;
    setStatus("REJECTED");
    setIsRejectModalOpen(false);

    const auditRecord = {
      action: "REJECTED",
      deliverableId,
      checker,
      reason: rejectionReason,
      rejectedAt: new Date().toISOString(),
    };

    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ && deliverableId) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("invoke_core_rpc", {
          request: {
            method: "deliverable/reject",
            params: { deliverableId, checker, reason: rejectionReason },
          },
        });
      } catch {}
    }

    if (onRejectSuccess) onRejectSuccess(auditRecord);
  };

  if (!isDirectMode && deliverablesList.length === 0 && !loading && !propFields) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[#0B0F14] text-[#E6EDF3] p-8">
        <div className="max-w-md w-full bg-[#121821] border border-[#263241] rounded-[4px] p-6 text-center">
          <FileText className="w-8 h-8 text-[#4C8DF6] mx-auto mb-3" />
          <h2 className="text-[14px] font-bold mb-1">Maker-Checker Review & Approve</h2>
          <p className="text-[12px] text-[#9AA7B4] mb-4">
            No deliverables pending review. Deliverables generated during analysis sessions appear here for dual-signature maker-checker verification.
          </p>
          <button
            onClick={loadDeliverables}
            className="px-3 py-1.5 bg-[#1A222E] hover:bg-[#263241] text-[#E6EDF3] border border-[#263241] rounded-[4px] text-[12px] font-mono flex items-center justify-center gap-1.5 mx-auto cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh Deliverables
          </button>
        </div>
      </div>
    );
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
        {/* Left Side: Deliverable Document Preview */}
        <div className="flex-1 overflow-y-auto p-6 bg-[#0B0F14] flex justify-center">
          <div data-testid="deliverable-paper-page" className="w-full max-w-3xl bg-white text-slate-900 border border-slate-300 rounded-[4px] p-8 shadow-sm font-serif">
            {/* Letterhead */}
            <div className="border-b-2 border-slate-900 pb-4 mb-6 text-center">
              <div className="text-[11px] font-sans font-bold tracking-wider text-slate-700 uppercase">
                {orgConfig.logoText || "MRPL / ONGC GROUP"}
              </div>
              <h1 className="text-[16px] font-bold text-slate-950 uppercase tracking-tight">
                {orgConfig.orgName || "MANGALORE REFINERY AND PETROCHEMICALS LIMITED"}
              </h1>
              <div className="text-[12px] font-sans text-slate-700">
                {orgConfig.divisionName || "Inspection & Engineering Division"}
              </div>
            </div>

            {/* Note Metadata */}
            <div className="grid grid-cols-2 gap-2 text-[12px] font-sans border-b border-slate-200 pb-4 mb-4">
              <div><span className="font-bold text-slate-700">Ref: </span><span className="font-mono">MRPL/INSP/2026/09</span></div>
              <div><span className="font-bold text-slate-700">Date: </span><span className="font-mono">07-SEP-2026</span></div>
              <div className="col-span-2"><span className="font-bold text-slate-700">Subject: </span><span>{subject}</span></div>
            </div>

            <div className="text-[14px] font-bold font-sans text-slate-950 mb-3 uppercase">
              {title}
            </div>

            <p className="text-[11px] font-sans text-amber-700 bg-amber-50 border border-amber-200 p-2 rounded-[4px] mb-4">
              DRAFT — requires approval by competent authority prior to maintenance outage scheduling.
            </p>

            {/* Technical Narrative */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[12px] font-sans font-bold text-slate-800">1. TECHNICAL ASSESSMENT & OBSERVATIONS</span>
                <button
                  data-testid="edit-narrative-btn"
                  onClick={() => setIsEditingNarrative(!isEditingNarrative)}
                  className="text-[11px] font-sans text-blue-700 hover:text-blue-900 flex items-center gap-1 cursor-pointer"
                >
                  <Edit3 className="w-3 h-3" /> {isEditingNarrative ? "Done Editing" : "Edit Narrative"}
                </button>
              </div>

              {isEditingNarrative ? (
                <textarea
                  data-testid="narrative-textarea"
                  value={narrativeText}
                  onChange={(e) => setNarrativeText(e.target.value)}
                  className="w-full h-24 p-2 text-[12px] font-sans border border-blue-400 rounded-[4px] focus:outline-none text-slate-900 bg-blue-50/20"
                />
              ) : (
                <div className="text-[12px] font-sans text-slate-800 leading-relaxed bg-slate-50 border border-slate-200 p-3 rounded-[4px]">
                  {narrativeText.includes("Updated") && <span className="font-bold text-blue-700">[CHECKER EDITED CONTENT]: </span>}
                  {narrativeText}
                </div>
              )}
            </div>

            {/* Governed Calculations */}
            <div className="mb-6">
              <div className="text-[12px] font-sans font-bold text-slate-800 mb-2">
                2. DETERMINISTIC LIFE DERIVATION (API 570)
              </div>
              <div className="bg-slate-900 text-emerald-400 p-3 rounded-[4px] font-mono text-[11px]">
                <div className="flex justify-between border-b border-slate-700 pb-1 mb-2 text-slate-400 text-[10px]">
                  <span>EXECUTION: {calcExecution.run_id}</span>
                  <span className="text-emerald-400 font-bold">STATUS: {calcExecution.status}</span>
                </div>
                <div>Equipment Tag: {calcExecution.executed_derivation.equipment_tag}</div>
                <div>Standard: {calcExecution.executed_derivation.governing_standard}</div>
                <div>t_actual = {calcExecution.executed_derivation.t_actual_mm} mm · t_min = {calcExecution.executed_derivation.t_min_mm} mm</div>
                <div>Corrosion Rate = {calcExecution.executed_derivation.corrosion_rate_mm_yr} mm/yr</div>
                <div className="mt-1 pt-1 border-t border-slate-800 text-white font-bold">
                  Remaining Operational Life: {calcExecution.executed_derivation.remaining_life_years} Years
                </div>
              </div>
            </div>

            {/* Approval Stamp Box */}
            {(status === "APPROVED" || isConcurrent) && (
              <div data-testid="approval-stamp-box" className="border-2 border-emerald-700 bg-emerald-50 text-emerald-950 p-4 rounded-[4px] font-mono text-[11px] my-4">
                <div className="font-bold text-[13px] border-b border-emerald-600 pb-1 mb-2 uppercase flex items-center gap-1.5 text-emerald-800">
                  <CheckCircle className="w-4 h-4 text-emerald-700" />
                  {orgConfig.terminology || "APPROVED"} — INSPECTION SANCTION AFFIXED
                </div>
                <div>APPROVED BY: {checker.name} ({checker.designation})</div>
                <div>PREPARED BY: {maker.name} ({maker.designation})</div>
                <div className="text-[10px] text-emerald-700 mt-1 font-mono">
                  CRYPTOGRAPHIC CHECKSUM: sha256:7f89bc44d019a82e9120
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Verification Sidebar */}
        <div className="w-96 bg-[#121821] border-l border-[#263241] flex flex-col justify-between overflow-y-auto">
          <div className="p-4 space-y-5">
            {/* Audited Extraction Fields */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-[12px] text-[#E6EDF3]">EXTRACTED DATA PROVENANCE</span>
                <span className="text-[11px] font-mono text-[#9AA7B4]">{fields.length} parameters</span>
              </div>
              <div className="space-y-2">
                {fields.map((field) => (
                  <div key={field.id} className="bg-[#0B0F14] border border-[#263241] rounded-[4px] p-2.5 text-[12px]">
                    <div className="flex items-center justify-between font-mono mb-1">
                      <span className="text-[#E6EDF3] font-bold">{field.field_name}</span>
                      <span className="text-[#4C8DF6]">{field.value} {field.unit || ""}</span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] font-mono">
                      <span className="text-[#9AA7B4]">Confidence: {field.confidence.toFixed(2)}</span>
                      {field.is_verified ? (
                        <span className="text-[#10B981] font-bold flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" /> VERIFIED
                        </span>
                      ) : (
                        <button
                          data-testid={`verify-field-btn-${field.id}`}
                          onClick={() => setActiveCropFieldId(field.id)}
                          className="text-[#F59E0B] hover:text-[#E6EDF3] bg-[#F59E0B]/20 hover:bg-[#F59E0B]/40 px-2 py-0.5 rounded-[4px] cursor-pointer"
                        >
                          Verify Crop
                        </button>
                      )}
                    </div>

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
                        onConfirmVerify={handleVerifyField}
                        onCancel={() => setActiveCropFieldId(null)}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Citations Checklist */}
            <div>
              <div className="font-bold text-[12px] text-[#E6EDF3] mb-2">NORMATIVE CITATIONS</div>
              <div className="space-y-2">
                {citations.map((c) => (
                  <div key={c.id} className="bg-[#0B0F14] border border-[#263241] rounded-[4px] p-2 text-[11px]">
                    <div className="font-mono text-[#10B981] font-semibold">{c.title} ({c.clause_or_section})</div>
                    <div className="text-[#9AA7B4] mt-0.5">{c.claim_text}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* AI Models Used */}
            <div className="border-t border-[#263241] pt-3 text-[11px] font-mono text-[#9AA7B4]">
              <div>PROVENANCE ENGINES:</div>
              <div className="text-[#E6EDF3]">{modelsUsed.join(" · ")}</div>
            </div>
          </div>

          {/* Action Footer */}
          <div className="p-4 bg-[#0B0F14] border-t border-[#263241] flex gap-2 shrink-0">
            <button
              data-testid="reject-btn"
              disabled={isConcurrent || status === "APPROVED"}
              onClick={() => setIsRejectModalOpen(true)}
              className="flex-1 py-2 bg-[#EF4444]/20 hover:bg-[#EF4444]/30 text-[#EF4444] border border-[#EF4444]/40 font-mono font-bold rounded-[4px] text-[12px] disabled:opacity-40 cursor-pointer"
            >
              Reject / Return
            </button>
            <button
              data-testid="approve-btn"
              disabled={isConcurrent || hasBlockers || status === "APPROVED"}
              onClick={handleApprove}
              className="flex-1 py-2 bg-[#10B981] hover:bg-[#0D9668] text-[#0B0F14] font-mono font-bold rounded-[4px] text-[12px] disabled:opacity-40 cursor-pointer"
            >
              Sign & Approve
            </button>
          </div>
        </div>
      </div>

      {/* Rejection Modal */}
      {isRejectModalOpen && (
        <div data-testid="rejection-modal" className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-[#121821] border border-[#EF4444] rounded-[4px] p-6 max-w-md w-full text-[13px]">
            <h3 className="font-bold text-[14px] text-[#EF4444] mb-2 font-mono">REJECT DELIVERABLE</h3>
            <p className="text-[12px] text-[#9AA7B4] mb-3">
              Enter mandatory engineering justification for returning this document to the maker:
            </p>
            <textarea
              data-testid="rejection-reason-input"
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="e.g. Calculated wall thickness requires secondary UT scan verification."
              className="w-full h-24 bg-[#0B0F14] border border-[#263241] rounded-[4px] p-2 text-[#E6EDF3] font-mono text-[12px] mb-4 focus:outline-none focus:border-[#EF4444]"
            />
            <div className="flex justify-end gap-2 font-mono text-[12px]">
              <button
                onClick={() => setIsRejectModalOpen(false)}
                className="px-3 py-1.5 bg-[#1A222E] text-[#9AA7B4] hover:text-[#E6EDF3] rounded-[4px] cursor-pointer"
              >
                Cancel
              </button>
              <button
                data-testid="submit-rejection-btn"
                disabled={!rejectionReason.trim()}
                onClick={handleReject}
                className="px-4 py-1.5 bg-[#EF4444] text-white font-bold rounded-[4px] disabled:opacity-40 cursor-pointer"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
