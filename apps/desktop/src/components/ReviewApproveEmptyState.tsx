import React from "react";
import { FileText, RefreshCw } from "lucide-react";

export interface ReviewApproveEmptyStateProps {
  loading: boolean;
  onRefresh: () => void;
}

export const ReviewApproveEmptyState: React.FC<ReviewApproveEmptyStateProps> = ({
  loading,
  onRefresh,
}) => {
  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-[#0B0F14] text-[#E6EDF3] p-8">
      <div className="max-w-md w-full bg-[#121821] border border-[#263241] rounded-[4px] p-6 text-center">
        <FileText className="w-8 h-8 text-[#4C8DF6] mx-auto mb-3" />
        <h2 className="text-[14px] font-bold mb-1">Maker-Checker Review & Approve</h2>
        <p className="text-[12px] text-[#9AA7B4] mb-4">
          No deliverables pending review. Deliverables generated during analysis sessions appear here for dual-signature maker-checker verification.
        </p>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="px-3 py-1.5 bg-[#1A222E] hover:bg-[#263241] text-[#E6EDF3] border border-[#263241] rounded-[4px] text-[12px] font-mono flex items-center justify-center gap-1.5 mx-auto cursor-pointer disabled:opacity-40"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh Deliverables
        </button>
      </div>
    </div>
  );
};
