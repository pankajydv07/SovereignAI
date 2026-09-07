import React from "react";
import { CheckCircle } from "lucide-react";
import { InlineCropPreview } from "./InlineCropPreview";
import type { AuditedField, ClaimCitation } from "./reviewApproveTypes";

export interface ReviewProvenanceSidebarProps {
  fields: AuditedField[];
  citations: ClaimCitation[];
  modelsUsed: string[];
  activeCropFieldId: string | null;
  setActiveCropFieldId: (id: string | null) => void;
  actionLoading: boolean;
  isConcurrent: boolean;
  status: "DRAFT" | "PENDING_CHECK" | "APPROVED" | "REJECTED";
  hasBlockers: boolean;
  onVerifyField: (fieldId: string) => Promise<void>;
  onOpenRejectModal: () => void;
  onApprove: () => Promise<void>;
}

export const ReviewProvenanceSidebar: React.FC<ReviewProvenanceSidebarProps> = ({
  fields,
  citations,
  modelsUsed,
  activeCropFieldId,
  setActiveCropFieldId,
  actionLoading,
  isConcurrent,
  status,
  hasBlockers,
  onVerifyField,
  onOpenRejectModal,
  onApprove,
}) => {
  return (
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
                  <span className="text-[#9AA7B4]">
                    Confidence: {field.confidence !== null ? field.confidence.toFixed(2) : "Uncalibrated (Vision)"}
                  </span>
                  {field.is_verified ? (
                    <span className="text-[#10B981] font-bold flex items-center gap-1">
                      <CheckCircle className="w-3 h-3" /> VERIFIED
                    </span>
                  ) : (
                    <button
                      data-testid={`verify-field-btn-${field.id}`}
                      disabled={actionLoading}
                      onClick={() => setActiveCropFieldId(field.id)}
                      className="text-[#F59E0B] hover:text-[#E6EDF3] bg-[#F59E0B]/20 hover:bg-[#F59E0B]/40 px-2 py-0.5 rounded-[4px] cursor-pointer disabled:opacity-40"
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
                    onConfirmVerify={onVerifyField}
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
          disabled={isConcurrent || status === "APPROVED" || actionLoading}
          onClick={onOpenRejectModal}
          className="flex-1 py-2 bg-[#EF4444]/20 hover:bg-[#EF4444]/30 text-[#EF4444] border border-[#EF4444]/40 font-mono font-bold rounded-[4px] text-[12px] disabled:opacity-40 cursor-pointer"
        >
          Reject / Return
        </button>
        <button
          data-testid="approve-btn"
          disabled={isConcurrent || hasBlockers || status === "APPROVED" || actionLoading}
          onClick={onApprove}
          className="flex-1 py-2 bg-[#10B981] hover:bg-[#0D9668] text-[#0B0F14] font-mono font-bold rounded-[4px] text-[12px] disabled:opacity-40 cursor-pointer"
        >
          Sign & Approve
        </button>
      </div>
    </div>
  );
};
