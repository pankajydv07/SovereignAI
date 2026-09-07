import React from "react";

export interface RejectDeliverableModalProps {
  isOpen: boolean;
  rejectionReason: string;
  setRejectionReason: (val: string) => void;
  actionLoading: boolean;
  onClose: () => void;
  onConfirmReject: () => Promise<void>;
}

export const RejectDeliverableModal: React.FC<RejectDeliverableModalProps> = ({
  isOpen,
  rejectionReason,
  setRejectionReason,
  actionLoading,
  onClose,
  onConfirmReject,
}) => {
  if (!isOpen) return null;

  return (
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
            onClick={onClose}
            className="px-3 py-1.5 bg-[#1A222E] text-[#9AA7B4] hover:text-[#E6EDF3] rounded-[4px] cursor-pointer"
          >
            Cancel
          </button>
          <button
            data-testid="submit-rejection-btn"
            disabled={!rejectionReason.trim() || actionLoading}
            onClick={onConfirmReject}
            className="px-4 py-1.5 bg-[#EF4444] text-white font-bold rounded-[4px] disabled:opacity-40 cursor-pointer"
          >
            Confirm Rejection
          </button>
        </div>
      </div>
    </div>
  );
};
