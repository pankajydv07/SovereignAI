/**
 * ProvenanceViewer — Signature SWARAJ 50/50 Synchronized Provenance Inspection Component.
 *
 * Implements bidirectional split view: field click zooms/pulses canvas; bbox click flashes table row.
 * Handles j/k keyboard navigation, all 5 component states (Progressive Arrival, Normal, Empty, Image Load Error, Unreadable Warning).
 * Dispatches audited field_verified and field_corrected protocol events to the core.
 */

import React, { useEffect, useState } from "react";
import { PageCanvas } from "./PageCanvas";
import { AuditedFieldItem, FieldTable } from "./FieldTable";

export interface ProvenanceViewerProps {
  imagePath: string;
  totalPages: number;
  fields: AuditedFieldItem[];
  isIngesting?: boolean;
  ingestProgressPage?: number;
  imageLoadError?: boolean;
  unreadableWarning?: string | null;
  onAuditFieldVerified?: (event: {
    fieldId: string;
    docPath: string;
    oldValue: string;
    newValue: string;
    operatorId: string;
    timestamp: string;
  }) => void;
}

export const ProvenanceViewer: React.FC<ProvenanceViewerProps> = ({
  imagePath,
  totalPages,
  fields: initialFields,
  isIngesting = false,
  ingestProgressPage = 1,
  imageLoadError = false,
  unreadableWarning = null,
  onAuditFieldVerified,
}) => {
  const [fields, setFields] = useState<AuditedFieldItem[]>(initialFields);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(
    initialFields.length > 0 ? initialFields[0].id : null
  );
  const [hoveredFieldId, setHoveredFieldId] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Keep internal fields state updated when props change
  useEffect(() => {
    setFields(initialFields);
    if (!selectedFieldId && initialFields.length > 0) {
      setSelectedFieldId(initialFields[0].id);
    }
  }, [initialFields]);

  // Synchronize active page when selected field changes
  useEffect(() => {
    if (selectedFieldId) {
      const field = fields.find((f) => f.id === selectedFieldId);
      if (field && field.page !== currentPage) {
        setCurrentPage(field.page);
      }
    }
  }, [selectedFieldId]);

  // Keyboard navigation: j / k for next / previous field
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (fields.length === 0) return;
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        const currentIndex = fields.findIndex((f) => f.id === selectedFieldId);
        const nextIndex = (currentIndex + 1) % fields.length;
        setSelectedFieldId(fields[nextIndex].id);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        const currentIndex = fields.findIndex((f) => f.id === selectedFieldId);
        const prevIndex = (currentIndex - 1 + fields.length) % fields.length;
        setSelectedFieldId(fields[prevIndex].id);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [fields, selectedFieldId]);

  // Human Verification & Inline Edit Action
  const handleVerifyField = (id: string, updatedValue?: string) => {
    const timestamp = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
    const operatorId = "A. Sharma";

    setFields((prev) =>
      prev.map((f) => {
        if (f.id !== id) return f;

        const oldValue = f.value;
        const newValue = updatedValue || f.value;

        // Preserves immutable machine confidence
        const updatedField: AuditedFieldItem = {
          ...f,
          value: newValue,
          is_verified: true,
          requires_verification: false,
          verification: {
            verifiedBy: operatorId,
            verifiedAt: timestamp,
            originalValue: oldValue,
            correctedValue: updatedValue && updatedValue !== oldValue ? updatedValue : null,
          },
        };

        // Dispatch audited protocol event
        onAuditFieldVerified?.({
          fieldId: id,
          docPath: imagePath,
          oldValue,
          newValue,
          operatorId,
          timestamp,
        });

        return updatedField;
      })
    );
  };

  // State 3: Empty State (Zero fields extracted)
  if (!isIngesting && fields.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 bg-[#0B0F14] text-[#E6EDF3] font-sans">
        <div className="max-w-md p-6 bg-[#121821] border border-[#263241] rounded-[4px] text-center">
          <div className="font-mono text-[14px] font-semibold text-[#9AA7B4] mb-2">
            ZERO FIELDS EXTRACTED
          </div>
          <p className="text-[12px] text-[#6B7A8A] mb-4">
            No structured inspection fields were detected on document: <br />
            <span className="font-mono text-[#E6EDF3]">{imagePath}</span>
          </p>
          <button className="px-3 py-1.5 bg-[#1A222E] border border-[#263241] rounded-[4px] font-mono text-[12px] text-[#4C8DF6]">
            Re-run Document Ingestion
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full bg-[#0B0F14] text-[#E6EDF3] font-sans overflow-hidden">
      {/* State 1: Ingesting Banner */}
      {isIngesting && (
        <div className="flex items-center justify-between px-4 py-2 bg-[#1A222E] border-b border-[#263241] text-[12px] font-mono">
          <div className="flex items-center gap-2 text-[#4C8DF6]">
            <span className="animate-spin">⏳</span>
            <span>INGESTING DOCUMENT… Processing page {ingestProgressPage} of {totalPages}</span>
          </div>
          <span className="text-[#9AA7B4]">{fields.length} fields arrived</span>
        </div>
      )}

      {/* State 5: Unreadable Page Warning Banner */}
      {unreadableWarning && (
        <div className="flex items-center justify-between px-4 py-2 bg-[#F59E0B]/10 border-b border-[#F59E0B]/30 text-[#F59E0B] text-[12px] font-mono">
          <span>⚠ WARNING: {unreadableWarning}</span>
          <span className="text-[11px] text-[#9AA7B4]">Manual verification required</span>
        </div>
      )}

      {/* 50/50 Split View */}
      <div className="flex flex-1 h-full w-full overflow-hidden">
        {/* Left Pane (50%): Page Canvas */}
        <div className="w-1/2 h-full overflow-hidden">
          <PageCanvas
            imagePath={imagePath}
            currentPage={currentPage}
            totalPages={totalPages}
            fields={fields}
            selectedFieldId={selectedFieldId}
            hoveredFieldId={hoveredFieldId}
            onSelectField={setSelectedFieldId}
            onHoverField={setHoveredFieldId}
            onPageChange={setCurrentPage}
            imageLoadError={imageLoadError}
          />
        </div>

        {/* Right Pane (50%): Field Table */}
        <div className="w-1/2 h-full overflow-hidden">
          <FieldTable
            fields={fields}
            selectedFieldId={selectedFieldId}
            hoveredFieldId={hoveredFieldId}
            onSelectField={setSelectedFieldId}
            onHoverField={setHoveredFieldId}
            onVerifyField={handleVerifyField}
          />
        </div>
      </div>
    </div>
  );
};
