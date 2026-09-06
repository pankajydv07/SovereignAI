/**
 * FieldTable — Provenance Viewer Field List & Maker-Checker Verification Component.
 *
 * Right pane of ProvenanceViewer. Displays extracted fields with monospaced machine values and confidences.
 * Preserves immutable machine confidence measurement on verification and inline edit.
 * Dispatches audited field_verified and field_corrected events to the core.
 */

import React, { useEffect, useRef, useState } from "react";
import { CanvasOverlayField } from "./PageCanvas";

export interface VerificationData {
  verifiedBy: string;
  verifiedAt: string;
  originalValue: string;
  correctedValue: string | null;
}

export interface AuditedFieldItem extends CanvasOverlayField {
  unit?: string | null;
  extractor: string;
  verification?: VerificationData | null;
}

interface FieldTableProps {
  fields: AuditedFieldItem[];
  selectedFieldId: string | null;
  hoveredFieldId: string | null;
  onSelectField: (id: string) => void;
  onHoverField: (id: string | null) => void;
  onVerifyField: (id: string, updatedValue?: string) => void;
  operatorId?: string;
}

export const FieldTable: React.FC<FieldTableProps> = ({
  fields,
  selectedFieldId,
  hoveredFieldId,
  onSelectField,
  onHoverField,
  onVerifyField,
  operatorId = "A. Sharma",
}) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");
  const rowRefs = useRef<{ [key: string]: HTMLTableRowElement | null }>({});

  // Auto-scroll selected row into view
  useEffect(() => {
    if (selectedFieldId && rowRefs.current[selectedFieldId]) {
      const el = rowRefs.current[selectedFieldId];
      if (typeof el?.scrollIntoView === "function") {
        el.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        });
      }
    }
  }, [selectedFieldId]);

  const handleStartEdit = (field: AuditedFieldItem) => {
    setEditingId(field.id);
    setEditValue(field.value);
  };

  const handleSaveEdit = (field: AuditedFieldItem) => {
    onVerifyField(field.id, editValue);
    setEditingId(null);
  };

  return (
    <div className="flex flex-col h-full bg-[#121821] text-[#E6EDF3] text-[13px] font-sans border-l border-[#263241]">
      {/* Field Table Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[#263241] bg-[#1A222E]">
        <span className="font-mono text-[11px] text-[#9AA7B4] tracking-wider uppercase">
          EXTRACTED FIELDS ({fields.length})
        </span>
        <span className="font-mono text-[11px] text-[#6B7A8A]">
          OPERATOR: {operatorId}
        </span>
      </div>

      {/* Table Content */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-[#263241] text-[#9AA7B4] font-mono text-[11px] bg-[#121821] sticky top-0 z-10">
              <th className="py-2 px-3">FIELD NAME</th>
              <th className="py-2 px-3">VALUE / UNIT</th>
              <th className="py-2 px-3">CONFIDENCE</th>
              <th className="py-2 px-3">STATUS & VERIFICATION</th>
              <th className="py-2 px-3 text-right">ACTION</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#263241]/60">
            {fields.map((field) => {
              const isSelected = field.id === selectedFieldId;
              const isHovered = field.id === hoveredFieldId;
              const isEditing = editingId === field.id;

              const displayConf = field.confidence !== null ? field.confidence.toFixed(2) : "UNCONFIRMED";
              const confClass =
                field.confidence === null || field.confidence < 0.85
                  ? "text-[#F59E0B]"
                  : "text-[#10B981]";

              return (
                <tr
                  key={field.id}
                  ref={(el) => (rowRefs.current[field.id] = el)}
                  onClick={() => onSelectField(field.id)}
                  onMouseEnter={() => onHoverField(field.id)}
                  onMouseLeave={() => onHoverField(null)}
                  className={`cursor-pointer transition-colors duration-150 ${
                    isSelected
                      ? "bg-[#1A222E] border-l-2 border-l-[#4C8DF6]"
                      : isHovered
                      ? "bg-[#1A222E]/50"
                      : "hover:bg-[#1A222E]/30"
                  }`}
                >
                  {/* Field Name */}
                  <td className="py-2.5 px-3 font-mono text-[12px] font-semibold text-[#E6EDF3]">
                    {field.field_name}
                    <div className="text-[10px] text-[#6B7A8A]">P.{field.page} · {field.extractor}</div>
                  </td>

                  {/* Field Value & Unit */}
                  <td className="py-2.5 px-3 font-mono text-[13px]">
                    {isEditing ? (
                      <div className="flex items-center gap-1">
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="px-2 py-0.5 bg-[#0B0F14] border border-[#4C8DF6] rounded-[4px] text-white font-mono text-[12px] focus:outline-none"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveEdit(field)}
                          className="px-2 py-0.5 bg-[#10B981] text-black text-[11px] font-mono rounded-[4px]"
                        >
                          Save
                        </button>
                      </div>
                    ) : (
                      <span className="text-[#E6EDF3] font-medium">
                        {field.verification?.correctedValue || field.value}{" "}
                        {field.unit && <span className="text-[#9AA7B4] font-normal">{field.unit}</span>}
                      </span>
                    )}
                  </td>

                  {/* Immutable Machine Confidence */}
                  <td className="py-2.5 px-3 font-mono text-[12px]">
                    <span className={confClass}>{displayConf}</span>
                  </td>

                  {/* Status & Verification Metadata */}
                  <td className="py-2.5 px-3 text-[11px]">
                    {field.is_verified && field.verification ? (
                      <div className="text-[#10B981] font-mono">
                        ✓ verified by {field.verification.verifiedBy} {field.verification.verifiedAt}
                      </div>
                    ) : field.requires_verification ? (
                      <div className="text-[#F59E0B] font-mono flex items-center gap-1">
                        <span>⚠ Needs Review</span>
                      </div>
                    ) : (
                      <div className="text-[#9AA7B4] font-mono">Extracted</div>
                    )}
                  </td>

                  {/* Verification Action */}
                  <td className="py-2.5 px-3 text-right">
                    {!field.is_verified ? (
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStartEdit(field);
                          }}
                          className="px-2 py-1 bg-[#1A222E] border border-[#263241] rounded-[4px] text-[11px] font-mono hover:bg-[#263241] text-[#9AA7B4]"
                        >
                          Edit
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onVerifyField(field.id);
                          }}
                          className="px-2.5 py-1 bg-[#10B981]/20 border border-[#10B981] text-[#10B981] rounded-[4px] text-[11px] font-mono hover:bg-[#10B981]/30 transition-colors"
                        >
                          Verify
                        </button>
                      </div>
                    ) : (
                      <span className="text-[11px] font-mono text-[#10B981]">SOVEREIGN</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
