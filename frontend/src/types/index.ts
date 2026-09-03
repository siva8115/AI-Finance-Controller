export interface APIResponse<T> {
  success: boolean;
  message: string;
  data: T;
  errors?: string[];
}

export interface HealthCheckResponse {
  status: string;
  project_name: string;
  version: string;
  database_connected: boolean;
}

export interface SystemOverview {
  total_orders_in_db: number;
  total_payments_in_db: number;
  total_settlements_in_db: number;
  total_reconciliation_runs: number;
  total_open_exceptions: number;
  dataset_source?: "DEMO" | "UPLOADED" | "EMPTY" | string;
}

export interface CSVPayloadRequest {
  orders_csv?: string;
  payments_csv?: string;
  settlements_csv?: string;
}

export interface ValidationMessage {
  level: "VALID" | "WARNING" | "ERROR" | string;
  message: string;
  file_type: "ORDERS" | "PAYMENTS" | "SETTLEMENTS" | "CROSS_REFERENCE" | string;
}

export interface ValidationSummary {
  orders_count: number;
  payments_count: number;
  settlements_count: number;
  total_valid_records: number;
  potential_issues_count: number;
  file_statuses: Record<string, string>;
  messages: ValidationMessage[];
  is_reconcilable: boolean;
}

export interface IngestionSummary {
  orders_ingested: number;
  payments_ingested: number;
  settlements_ingested: number;
  total_records: number;
  status: string;
}

export interface DataGenerationRequest {
  num_orders?: number;
  anomaly_rate?: number;
  seed?: number;
}

export interface DataGenerationSummary {
  num_orders: number;
  num_payments: number;
  num_settlements: number;
  num_anomalies: number;
  anomaly_breakdown: Record<string, number>;
  files_generated: string[];
}

export interface ReconciliationRunRequest {
  settlement_window_days?: number;
  monetary_tolerance?: number;
}

export interface BatchAIInvestigationResponse {
  total_exceptions: number;
  investigated_cases: number;
  successful_investigations: number;
  failed_investigations: number;
  human_review_required: number;
}

export interface BatchResolutionResponse {
  total_eligible: number;
  resolved_cases: number;
  auto_resolved: number;
  human_review_required: number;
  review_recommended: number;
  ai_failed: number;
}

export interface ReconciliationRunSummary {
  run_id: string;
  status: string;
  total_records: number;
  matched: number;
  exceptions: number;
  processing_time_seconds: number;
  started_at?: string;
  completed_at?: string;
}

export interface ReconciliationResultResponse {
  id: number;
  run_id: string;
  order_id: string;
  payment_ids: string[];
  settlement_ids: string[];
  reconciliation_status: string;
  exception_types: string[];
  order_amount?: number;
  payment_amount?: number;
  settlement_gross_amount?: number;
  settlement_net_amount?: number;
  payment_fee?: number;
  settlement_fee?: number;
  amount_difference?: number;
  settlement_difference?: number;
  match_method: string;
  explanation?: string;
  recommended_action?: string;
  checked_at?: string;
}

export interface ExceptionRecordResponse {
  id: number;
  run_id: string;
  order_id?: string;
  payment_id?: string;
  settlement_id?: string;
  exception_type: string;
  severity: string;
  status: string;
  expected_value?: string;
  actual_value?: string;
  difference?: number;
  ai_investigated: boolean;
  ai_confidence?: number;
  ai_root_cause?: string;
  ai_recommendation?: string;
  details?: string;
}

export interface AIInvestigationResponse {
  investigation_id: string;
  order_id: string;
  exception_type: string;
  summary: string;
  likely_cause: string;
  recommended_action: string;
  evidence_facts: string[];
  possible_causes: string[];
  evidence_gaps: string[];
  ai_classification?: string;
  ai_classification_matches_deterministic: boolean;
  ai_confidence?: number;
  effective_confidence?: number;
  confidence?: number;
  confidence_level: string;
  investigation_status: string;
  requires_human_review: boolean;
  safety_flags: string[];
  evidence_level?: string;
  evidence_records_count?: number;
  ai_attempts?: number;
  escalation_history?: Record<string, unknown>[];
  created_at?: string;
}

export interface ResolutionSummaryResponse {
  total_exceptions: number;
  investigated: number;
  auto_resolved: number;
  review_recommended: number;
  human_review_required: number;
  approved_by_human: number;
  rejected_by_human: number;
  unresolved: number;
  ai_failed: number;
  auto_resolution_rate: number;
  human_review_rate: number;
  unresolved_rate: number;
}

// Review Queue types — matching backend ReviewQueueItem schema
export interface ReviewQueueItem {
  resolution_id: string;
  order_id: string;
  deterministic_exception_type: string;
  resolution_status: string;
  confidence?: number;
  effective_confidence?: number;
  confidence_level?: string;
  safety_flags: string[];
  priority: number;
  priority_reason?: string;
  human_review_required: boolean;
  ai_investigation_id?: string;
  created_at?: string;
}

// Full resolution detail — matching backend ResolutionResponse schema
export interface ResolutionResponse {
  resolution_id: string;
  reconciliation_run_id: string;
  order_id: string;
  exception_id: number;
  ai_investigation_id?: string;
  deterministic_exception_type: string;
  ai_classification?: string;
  resolution_status: string;
  resolution_reason?: string;
  confidence?: number;
  effective_confidence?: number;
  confidence_level?: string;
  safety_flags: string[];
  human_review_required: boolean;
  resolved_by?: string;
  resolution_notes?: string;
  priority: number;
  priority_reason?: string;
  created_at?: string;
  updated_at?: string;
}

// Review queue detail response (dict from backend)
export interface ReviewQueueDetail {
  order?: Record<string, unknown>;
  payments?: Record<string, unknown>[];
  settlements?: Record<string, unknown>[];
  exception?: Record<string, unknown>;
  ai_investigation?: Record<string, unknown>;
  confidence?: number;
  safety_flags?: string[];
  evidence_facts?: string[];
  possible_causes?: string[];
  evidence_gaps?: string[];
  recommended_action?: string;
  current_resolution_status?: string;
}

// Audit Trail — immutable resolution event record
export interface ResolutionEventResponse {
  event_id: string;
  resolution_id: string;
  previous_status?: string;
  new_status: string;
  actor_type: string;   // SYSTEM | HUMAN
  actor_id?: string;
  reason?: string;
  created_at?: string;
}
