import type {
  APIResponse,
  HealthCheckResponse,
  SystemOverview,
  ReconciliationRunSummary,
  ReconciliationResultResponse,
  ExceptionRecordResponse,
  AIInvestigationResponse,
  ResolutionSummaryResponse,
  ReviewQueueItem,
  ResolutionResponse,
  ReviewQueueDetail,
  ResolutionEventResponse,
  CSVPayloadRequest,
  ValidationSummary,
  IngestionSummary,
  DataGenerationRequest,
  DataGenerationSummary,
  ReconciliationRunRequest,
  BatchAIInvestigationResponse,
  BatchResolutionResponse,
} from "../types";

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : "http://localhost:8000";

async function fetchFromApi<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function postToApi<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API Error: ${response.status} — ${text}`);
  }
  return response.json();
}

export const api = {
  // -------------------------------------------------------------------------
  // Health
  // -------------------------------------------------------------------------
  getHealth: async (): Promise<HealthCheckResponse> =>
    fetchFromApi<HealthCheckResponse>("/health"),

  // -------------------------------------------------------------------------
  // Data Management
  // -------------------------------------------------------------------------
  getDataSummary: async (): Promise<APIResponse<SystemOverview>> =>
    fetchFromApi<APIResponse<SystemOverview>>("/api/v1/data/summary"),

  validateCSV: async (payload: CSVPayloadRequest): Promise<APIResponse<ValidationSummary>> =>
    postToApi<APIResponse<ValidationSummary>>("/api/v1/data/validate", payload),

  uploadCSV: async (payload: CSVPayloadRequest): Promise<APIResponse<IngestionSummary>> =>
    postToApi<APIResponse<IngestionSummary>>("/api/v1/data/upload", payload),

  generateDemoData: async (payload: DataGenerationRequest = {}): Promise<APIResponse<DataGenerationSummary>> =>
    postToApi<APIResponse<DataGenerationSummary>>("/api/v1/data/generate", payload),

  ingestData: async (): Promise<APIResponse<IngestionSummary>> =>
    postToApi<APIResponse<IngestionSummary>>("/api/v1/data/ingest"),

  resetDatabase: async (): Promise<APIResponse<{ status: string }>> =>
    postToApi<APIResponse<{ status: string }>>("/api/v1/data/reset"),

  // -------------------------------------------------------------------------
  // Reconciliation
  // -------------------------------------------------------------------------
  runReconciliation: async (payload: ReconciliationRunRequest = {}): Promise<APIResponse<ReconciliationRunSummary>> =>
    postToApi<APIResponse<ReconciliationRunSummary>>("/api/v1/reconciliation/run", payload),

  getReconciliationSummary: async (): Promise<APIResponse<ReconciliationRunSummary | null>> =>
    fetchFromApi<APIResponse<ReconciliationRunSummary | null>>("/api/v1/reconciliation/summary"),

  getReconciliationResults: async (
    runId?: string,
    status?: string,
    exceptionType?: string,
    orderId?: string
  ): Promise<APIResponse<ReconciliationResultResponse[]>> => {
    const params = new URLSearchParams();
    if (runId) params.append("run_id", runId);
    if (status) params.append("status", status);
    if (exceptionType) params.append("exception_type", exceptionType);
    if (orderId) params.append("order_id", orderId);
    const q = params.toString() ? `?${params.toString()}` : "";
    return fetchFromApi<APIResponse<ReconciliationResultResponse[]>>(`/api/v1/reconciliation/results${q}`);
  },

  getReconciliationResultByOrder: async (
    orderId: string,
    runId?: string
  ): Promise<APIResponse<ReconciliationResultResponse>> => {
    const params = new URLSearchParams();
    if (runId) params.append("run_id", runId);
    const q = params.toString() ? `?${params.toString()}` : "";
    return fetchFromApi<APIResponse<ReconciliationResultResponse>>(`/api/v1/reconciliation/results/${orderId}${q}`);
  },

  getExceptions: async (
    runId?: string,
    exceptionType?: string,
    status?: string
  ): Promise<APIResponse<ExceptionRecordResponse[]>> => {
    const params = new URLSearchParams();
    if (runId) params.append("run_id", runId);
    if (exceptionType) params.append("exception_type", exceptionType);
    if (status) params.append("status", status);
    const q = params.toString() ? `?${params.toString()}` : "";
    return fetchFromApi<APIResponse<ExceptionRecordResponse[]>>(`/api/v1/reconciliation/exceptions${q}`);
  },

  // -------------------------------------------------------------------------
  // AI Investigations
  // -------------------------------------------------------------------------
  runBatchAIInvestigation: async (payload: { reconciliation_run_id: string; max_cases: number }): Promise<APIResponse<BatchAIInvestigationResponse>> =>
    postToApi<APIResponse<BatchAIInvestigationResponse>>("/api/v1/ai/investigate", payload),

  investigateOrderException: async (orderId: string): Promise<APIResponse<AIInvestigationResponse>> =>
    postToApi<APIResponse<AIInvestigationResponse>>(`/api/v1/ai/investigate/${orderId}`),

  getAIInvestigations: async (
    investigationStatus?: string,
    exceptionType?: string,
    confidenceLevel?: string,
    requiresHumanReview?: boolean
  ): Promise<APIResponse<AIInvestigationResponse[]>> => {
    const params = new URLSearchParams();
    if (investigationStatus) params.append("investigation_status", investigationStatus);
    if (exceptionType) params.append("exception_type", exceptionType);
    if (confidenceLevel) params.append("confidence_level", confidenceLevel);
    if (requiresHumanReview !== undefined) params.append("requires_human_review", String(requiresHumanReview));
    const q = params.toString() ? `?${params.toString()}` : "";
    return fetchFromApi<APIResponse<AIInvestigationResponse[]>>(`/api/v1/ai/investigations${q}`);
  },

  getAIInvestigationById: async (
    investigationId: string
  ): Promise<APIResponse<AIInvestigationResponse>> =>
    fetchFromApi<APIResponse<AIInvestigationResponse>>(`/api/v1/ai/investigations/${investigationId}`),

  // -------------------------------------------------------------------------
  // Resolution
  // -------------------------------------------------------------------------
  runBatchResolution: async (payload: { reconciliation_run_id: string; max_cases: number }): Promise<APIResponse<BatchResolutionResponse>> =>
    postToApi<APIResponse<BatchResolutionResponse>>("/api/v1/resolution/run", payload),

  runResolutionForOrder: async (orderId: string): Promise<APIResponse<ResolutionResponse>> =>
    postToApi<APIResponse<ResolutionResponse>>(`/api/v1/resolution/run/${orderId}`),

  getResolutionSummary: async (): Promise<APIResponse<ResolutionSummaryResponse>> =>
    fetchFromApi<APIResponse<ResolutionSummaryResponse>>("/api/v1/resolution/summary"),

  // -------------------------------------------------------------------------
  // Review Queue
  // -------------------------------------------------------------------------
  getReviewQueue: async (
    resolutionStatus?: string,
    exceptionType?: string,
    confidenceLevel?: string,
    reconciliationRunId?: string
  ): Promise<APIResponse<ReviewQueueItem[]>> => {
    const params = new URLSearchParams();
    if (resolutionStatus) params.append("resolution_status", resolutionStatus);
    if (exceptionType) params.append("exception_type", exceptionType);
    if (confidenceLevel) params.append("confidence_level", confidenceLevel);
    if (reconciliationRunId) params.append("reconciliation_run_id", reconciliationRunId);
    const q = params.toString() ? `?${params.toString()}` : "";
    return fetchFromApi<APIResponse<ReviewQueueItem[]>>(`/api/v1/review/queue${q}`);
  },

  getReviewQueueDetail: async (
    resolutionId: string
  ): Promise<APIResponse<ReviewQueueDetail>> =>
    fetchFromApi<APIResponse<ReviewQueueDetail>>(`/api/v1/review/queue/${resolutionId}`),

  approveCase: async (
    resolutionId: string,
    notes: string
  ): Promise<APIResponse<ResolutionResponse>> =>
    postToApi<APIResponse<ResolutionResponse>>(`/api/v1/review/${resolutionId}/approve`, { notes }),

  rejectCase: async (
    resolutionId: string,
    notes: string
  ): Promise<APIResponse<ResolutionResponse>> =>
    postToApi<APIResponse<ResolutionResponse>>(`/api/v1/review/${resolutionId}/reject`, { notes }),

  unresolveCase: async (
    resolutionId: string,
    reason: string
  ): Promise<APIResponse<ResolutionResponse>> =>
    postToApi<APIResponse<ResolutionResponse>>(`/api/v1/review/${resolutionId}/unresolve`, { reason }),

  // -------------------------------------------------------------------------
  // Audit Trail
  // -------------------------------------------------------------------------
  getAuditEvents: async (
    resolutionId?: string,
    actorType?: string,
    newStatus?: string,
    limit?: number
  ): Promise<APIResponse<ResolutionEventResponse[]>> => {
    const params = new URLSearchParams();
    if (resolutionId) params.append("resolution_id", resolutionId);
    if (actorType) params.append("actor_type", actorType);
    if (newStatus) params.append("new_status", newStatus);
    if (limit !== undefined) params.append("limit", String(limit));
    const q = params.toString() ? `?${params.toString()}` : "";
    return fetchFromApi<APIResponse<ResolutionEventResponse[]>>(`/api/v1/audit/events${q}`);
  },

  getAuditEventsForResolution: async (
    resolutionId: string
  ): Promise<APIResponse<ResolutionEventResponse[]>> =>
    fetchFromApi<APIResponse<ResolutionEventResponse[]>>(
      `/api/v1/audit/events/resolution/${resolutionId}`
    ),
};
