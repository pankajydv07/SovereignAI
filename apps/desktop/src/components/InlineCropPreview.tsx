import React from "react";
import { Check, X, Eye } from "lucide-react";

export interface InlineCropPreviewProps {
  fieldId: string;
  fieldName: string;
  value: string;
  unit?: string;
  confidence: number | null;
  page: number;
  bbox?: [number, number, number, number]; // [ymin, xmin, ymax, xmax] normalized 0-1000
  imagePath: string;
  onConfirmVerify: (fieldId: string) => void;
  onCancel: () => void;
}

export const InlineCropPreview: React.FC<InlineCropPreviewProps> = ({
  fieldId,
  fieldName,
  value,
  unit,
  confidence,
  page,
  bbox,
  imagePath,
  onConfirmVerify,
  onCancel,
}) => {
  return (
    <div
      data-testid="inline-crop-preview"
      className="bg-[#121821] border border-[#F59E0B] rounded-[4px] p-3 my-2 text-[12px] font-sans"
    >
      <div className="flex items-center justify-between border-b border-[#263241] pb-1.5 mb-2 font-mono text-[11px]">
        <div className="flex items-center gap-1.5 text-[#F59E0B] font-semibold">
          <Eye className="w-3.5 h-3.5" />
          <span>PROVENANCE SCAN CROP — PAGE {page}</span>
        </div>
        <button
          onClick={onCancel}
          className="text-[#9AA7B4] hover:text-[#E6EDF3] p-0.5 rounded cursor-pointer"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Source Scan Bounding Box Crop Simulation */}
      <div className="relative bg-[#0B0F14] border border-[#263241] rounded-[4px] p-3 mb-2 flex items-center justify-center overflow-hidden h-24">
        <div className="absolute inset-0 bg-[#1A222E]/50 flex items-center justify-center text-[#9AA7B4] text-[11px] font-mono select-none">
          [SCAN BBOX CROP: ymin={bbox ? bbox[0] : 120}, xmin={bbox ? bbox[1] : 340} · {imagePath}]
        </div>
        <div className="relative z-10 bg-[#F59E0B]/10 border-2 border-[#F59E0B] px-4 py-1.5 rounded text-[#E6EDF3] font-mono text-[14px] font-bold shadow-md">
          {value} {unit || ""}
        </div>
      </div>

      <div className="flex items-center justify-between text-[11px] font-mono mb-2">
        <div>
          <span className="text-[#9AA7B4]">Field: </span>
          <span className="text-[#E6EDF3] font-semibold">{fieldName}</span>
        </div>
        <div>
          <span className="text-[#9AA7B4]">Extraction Confidence: </span>
          <span
            className={`font-semibold ${
              confidence === null || confidence < 0.8 ? "text-[#F59E0B]" : "text-[#10B981]"
            }`}
          >
            {confidence !== null ? confidence.toFixed(2) : "Uncalibrated (Vision)"}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 pt-1 border-t border-[#263241]">
        <button
          onClick={onCancel}
          className="px-2.5 py-1 bg-[#1A222E] hover:bg-[#263241] text-[#9AA7B4] hover:text-[#E6EDF3] rounded-[4px] font-mono text-[11px] cursor-pointer"
        >
          Cancel
        </button>
        <button
          data-testid="confirm-verify-btn"
          onClick={() => onConfirmVerify(fieldId)}
          className="px-3 py-1 bg-[#10B981] hover:bg-[#0D9668] text-[#0B0F14] font-mono font-bold rounded-[4px] text-[11px] flex items-center gap-1 cursor-pointer"
        >
          <Check className="w-3.5 h-3.5" />
          Confirm Match & Verify
        </button>
      </div>
    </div>
  );
};
