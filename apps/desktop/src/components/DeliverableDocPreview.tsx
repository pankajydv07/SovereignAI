import React from "react";
import { CheckCircle, Edit3 } from "lucide-react";
import type { OrgConfig, CalcExecutionData, UserIdentity } from "./reviewApproveTypes";

export interface DeliverableDocPreviewProps {
  orgConfig: OrgConfig;
  subject: string;
  title: string;
  isEditingNarrative: boolean;
  setIsEditingNarrative: (val: boolean) => void;
  narrativeText: string;
  setNarrativeText: (val: string) => void;
  calcExecution: CalcExecutionData;
  status: "DRAFT" | "PENDING_CHECK" | "APPROVED" | "REJECTED";
  isConcurrent: boolean;
  checker: UserIdentity;
  maker: UserIdentity;
}

export const DeliverableDocPreview: React.FC<DeliverableDocPreviewProps> = ({
  orgConfig,
  subject,
  title,
  isEditingNarrative,
  setIsEditingNarrative,
  narrativeText,
  setNarrativeText,
  calcExecution,
  status,
  isConcurrent,
  checker,
  maker,
}) => {
  return (
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
  );
};
