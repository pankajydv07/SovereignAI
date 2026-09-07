export interface AuditedField {
  id: string;
  field_name: string;
  value: string;
  unit?: string;
  confidence: number | null;
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

export const ROSTER_USERS: UserIdentity[] = [
  { id: "user_kulkarni", name: "P. V. Kulkarni", designation: "Chief Manager - Mechanical" },
  { id: "user_sharma", name: "A. Sharma", designation: "Senior Inspection Engineer" },
];

export const DEFAULT_ORG_CONFIG: OrgConfig = {
  orgName: "MANGALORE REFINERY AND PETROCHEMICALS LIMITED",
  divisionName: "Inspection & Engineering Division",
  logoText: "MRPL / ONGC GROUP",
  terminology: "APPROVED",
};

export const DEFAULT_CALC_EXECUTION: CalcExecutionData = {
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
};

export const DEFAULT_INITIAL_FIELDS: AuditedField[] = [
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
];

export const DEFAULT_INITIAL_CITATIONS: ClaimCitation[] = [
  {
    id: "c1",
    doc_id: "KB-API-570",
    title: "API 570 Piping Inspection Code",
    clause_or_section: "Section 7.1.2",
    claim_text: "Formula Remaining Life = (t_actual - t_min) / Corrosion_Rate",
    is_cited: true,
  },
];
