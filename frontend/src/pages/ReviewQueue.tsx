import React, { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import type { ReviewQueueItem, ResolutionResponse } from "../types";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function fmtPct(val?: number): string {
  if (val === undefined || val === null) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

function fmtTime(iso?: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "AUTO_RESOLVED": return "resolved";
    case "APPROVED_BY_HUMAN": return "resolved";
    case "REJECTED_BY_HUMAN": return "severity-high";
    case "AI_FAILED": return "severity-high";
    case "UNRESOLVED": return "severity-medium";
    default: return "detected";
  }
}

function formatStatusLabel(status: string): string {
  if (status === "AI_FAILED") return "ROUTING TO HUMAN REVIEW";
  return status;
}

// ─────────────────────────────────────────────────────────────────────────────
// Decision Confirmation Modal Component
// ─────────────────────────────────────────────────────────────────────────────

type ActionType = "approve" | "reject" | "unresolve";

const ConfirmModal: React.FC<{
  action: ActionType;
  resolutionId: string;
  onConfirm: (notes: string) => Promise<void>;
  onCancel: () => void;
}> = ({ action, resolutionId, onConfirm, onCancel }) => {
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const actionLabels: Record<ActionType, { title: string; verb: string; color: string; placeholder: string }> = {
    approve: { title: "Approve Resolution", verb: "Approve", color: "var(--success-text)", placeholder: "e.g., Verified against Stripe settlement report. ₹300 is a valid processing fee." },
    reject: { title: "Reject Resolution", verb: "Reject", color: "var(--danger-text)", placeholder: "Reason for rejection (e.g., Unresolved rate dispute with gateway)..." },
    unresolve: { title: "Request Review / Reopen Case", verb: "Reopen", color: "var(--warning-text)", placeholder: "Reason for requesting further investigation..." },
  };

  const { title, verb, color, placeholder } = actionLabels[action];

  const handleSubmit = async () => {
    if (!notes.trim()) {
      setSubmitError("A note or reason is required.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await onConfirm(notes.trim());
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : "Operation failed.");
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, width: "100%", height: "100%",
      backgroundColor: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)", display: "flex",
      alignItems: "center", justifyContent: "center", zIndex: 400,
    }}>
      <div className="card" style={{
        width: "460px", maxWidth: "100vw",
        background: "var(--bg-surface)", border: "1px solid var(--border-color)",
        borderRadius: "12px", boxShadow: "var(--shadow-lg)",
      }}>
        <h3 style={{ margin: "0 0 var(--spacing-md)", fontSize: "16px", color }}>{title}</h3>
        <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "var(--spacing-md)" }}>
          Resolution ID: <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{resolutionId}</span>
        </p>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={placeholder}
          rows={4}
          style={{
            width: "100%", background: "var(--bg-primary)", border: "1px solid var(--border-color)",
            color: "var(--text-primary)", padding: "10px 12px", borderRadius: "6px",
            fontSize: "13px", resize: "vertical", fontFamily: "var(--font-sans)",
            boxSizing: "border-box",
          }}
        />
        {submitError && (
          <div style={{ color: "var(--danger-text)", fontSize: "12px", marginTop: "8px" }}>{submitError}</div>
        )}
        <div style={{ display: "flex", gap: "var(--spacing-sm)", justifyContent: "flex-end", marginTop: "var(--spacing-md)" }}>
          <button className="btn-action" onClick={onCancel} disabled={submitting} style={{ padding: "6px 14px" }}>
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{
              background: color, border: "none", color: "hsl(222,47%,11%)",
              padding: "6px 16px", borderRadius: "6px", fontWeight: 700,
              cursor: submitting ? "not-allowed" : "pointer", fontSize: "13px",
            }}
          >
            {submitting ? "Submitting…" : verb}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Case Detail Panel Component
// ─────────────────────────────────────────────────────────────────────────────

const CasePanel: React.FC<{
  item: ReviewQueueItem;
  investigations: Record<string, string>;
  onAction: (action: ActionType) => void;
  onClose: () => void;
}> = ({ item, onAction, onClose }) => {
  const flags = Array.isArray(item.safety_flags) ? item.safety_flags : [];
  const eff = item.effective_confidence ?? item.confidence;

  const canApprove = ["HUMAN_REVIEW_REQUIRED", "REVIEW_RECOMMENDED", "UNRESOLVED"].includes(item.resolution_status);
  const canReject  = ["HUMAN_REVIEW_REQUIRED", "REVIEW_RECOMMENDED", "UNRESOLVED"].includes(item.resolution_status);
  const canUnresolve = ["APPROVED_BY_HUMAN", "AUTO_RESOLVED", "REJECTED_BY_HUMAN"].includes(item.resolution_status);

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, width: "100%", height: "100%",
      backgroundColor: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)", display: "flex",
      alignItems: "flex-start", justifyContent: "flex-end", zIndex: 200,
    }}>
      <div style={{
        width: "520px", maxWidth: "100vw", height: "100vh", overflowY: "auto",
        backgroundColor: "var(--bg-surface)", borderLeft: "1px solid var(--border-color)",
        boxShadow: "var(--shadow-lg)",
      }}>
        {/* Header */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "var(--spacing-lg)", borderBottom: "1px solid var(--border-color)",
          position: "sticky", top: 0, background: "var(--bg-surface)", zIndex: 1,
        }}>
          <div>
            <div style={{ fontSize: "14px", fontWeight: 700 }}>Review Case</div>
            <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--text-secondary)", marginTop: "2px" }}>
              {item.resolution_id}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "transparent", border: "none",
            color: "var(--text-secondary)", fontSize: "22px", cursor: "pointer",
          }}>&times;</button>
        </div>

        <div style={{ padding: "var(--spacing-lg)", display: "flex", flexDirection: "column", gap: "var(--spacing-lg)" }}>

          {/* Case overview */}
          <section>
            <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
              Case Overview
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--spacing-md)", backgroundColor: "var(--bg-primary)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
              {([
                ["Order ID", <span key="ord" className="font-mono">{item.order_id}</span>],
                ["Exception Type", <span key="exc" className="font-mono" style={{ fontSize: "11px" }}>{item.deterministic_exception_type}</span>],
                ["Resolution Status", <span key="st" className={`badge ${statusBadgeClass(item.resolution_status)}`}>{formatStatusLabel(item.resolution_status)}</span>],
                ["Priority Score", <span key="pr" className="font-mono" style={{ fontWeight: 700 }}>{item.priority}</span>],
                ["Priority Reason", item.priority_reason || "—"],
              ] as [string, React.ReactNode][]).map(([label, val]) => (
                <div key={String(label)}>
                  <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>{label}</div>
                  <div style={{ fontSize: "13px", fontWeight: 500, marginTop: "2px" }}>{val}</div>
                </div>
              ))}
            </div>
          </section>

          {/* AI confidence */}
          <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
            <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
              AI Investigation Summary
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--spacing-md)" }}>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                  Effective Confidence <span style={{ color: "var(--info-text)", fontSize: "10px" }}>(safety-controlled)</span>
                </div>
                <div className="font-mono" style={{ fontSize: "18px", fontWeight: 800, color: "var(--info-text)", marginTop: "2px" }}>
                  {fmtPct(eff)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Confidence Level</div>
                <div style={{ fontSize: "13px", fontWeight: 600, marginTop: "2px" }}>{item.confidence_level || "—"}</div>
              </div>
            </div>
          </section>

          {/* Safety flags */}
          <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
            <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
              Safety Checks
            </h4>
            {flags.length === 0 ? (
              <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>No safety flags detected.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {flags.map((flag) => (
                  <div key={flag} style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    background: "var(--danger-bg)", border: "1px solid var(--danger-border)",
                    borderRadius: "6px", padding: "6px 10px",
                  }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--danger-text)" }}>{flag}</span>
                    <span className="badge severity-high" style={{ fontSize: "10px" }}>TRIGGERED</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Safety notice */}
          <div style={{
            background: "var(--bg-primary)", borderRadius: "8px", padding: "var(--spacing-md)",
            fontSize: "11.5px", color: "var(--text-secondary)", lineHeight: "1.6", border: "1px solid var(--border-subtle)",
          }}>
            AI recommendations are advisory. Deterministic reconciliation remains authoritative.
            Financial records are immutable during investigation and resolution.
          </div>

          {/* Action Buttons */}
          <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
            <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-md)", fontWeight: 700 }}>
              Human Decision
            </h4>
            <div style={{ display: "flex", gap: "var(--spacing-sm)", flexWrap: "wrap" }}>
              {canApprove && (
                <button
                  onClick={() => onAction("approve")}
                  style={{
                    background: "var(--success)", border: "none",
                    color: "hsl(222,47%,11%)", padding: "8px 18px",
                    borderRadius: "6px", fontWeight: 700, cursor: "pointer", fontSize: "13px",
                  }}
                >
                  Approve
                </button>
              )}
              {canReject && (
                <button
                  onClick={() => onAction("reject")}
                  style={{
                    background: "var(--danger)", border: "none",
                    color: "var(--text-primary)", padding: "8px 18px",
                    borderRadius: "6px", fontWeight: 700, cursor: "pointer", fontSize: "13px",
                  }}
                >
                  Reject
                </button>
              )}
              {canUnresolve && (
                <button
                  onClick={() => onAction("unresolve")}
                  style={{
                    background: "var(--bg-primary)", border: "1px solid var(--border-color)",
                    color: "var(--warning-text)", padding: "8px 18px",
                    borderRadius: "6px", fontWeight: 600, cursor: "pointer", fontSize: "13px",
                  }}
                >
                  Reopen
                </button>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Success Toast Component
// ─────────────────────────────────────────────────────────────────────────────

const SuccessToast: React.FC<{ message: string; onDismiss: () => void }> = ({ message, onDismiss }) => {
  useEffect(() => {
    const t = setTimeout(onDismiss, 4000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  return (
    <div style={{
      position: "fixed", bottom: "24px", right: "24px", zIndex: 500,
      background: "var(--success)", color: "hsl(222,47%,11%)",
      padding: "12px 20px", borderRadius: "8px", fontWeight: 700,
      fontSize: "13px", boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
      display: "flex", alignItems: "center", gap: "10px",
    }}>
      {message}
      <button onClick={onDismiss} style={{ background: "transparent", border: "none", cursor: "pointer", fontSize: "16px", color: "inherit" }}>×</button>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Page Component
// ─────────────────────────────────────────────────────────────────────────────

import { WorkflowVisualizer } from "../components/WorkflowVisualizer";
import { EmptyState } from "../components/EmptyState";

interface ReviewQueueProps {
  onNavigateToTab?: (tab: string) => void;
}

export const ReviewQueue: React.FC<ReviewQueueProps> = ({ onNavigateToTab }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [selected, setSelected] = useState<ReviewQueueItem | null>(null);
  const [pendingAction, setPendingAction] = useState<ActionType | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getReviewQueue();
      if (res.success) setQueue(res.data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load review queue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Refresh selected item from fresh queue after action
  const refreshSelected = (updatedResolution: ResolutionResponse) => {
    setQueue((prev) =>
      prev.map((item) =>
        item.resolution_id === updatedResolution.resolution_id
          ? { ...item, resolution_status: updatedResolution.resolution_status }
          : item
      )
    );
    setSelected((prev) =>
      prev ? { ...prev, resolution_status: updatedResolution.resolution_status } : null
    );
  };

  const handleConfirm = async (notes: string) => {
    if (!selected || !pendingAction) return;
    let result: { data: ResolutionResponse };
    if (pendingAction === "approve") {
      result = await api.approveCase(selected.resolution_id, notes);
    } else if (pendingAction === "reject") {
      result = await api.rejectCase(selected.resolution_id, notes);
    } else {
      result = await api.unresolveCase(selected.resolution_id, notes);
    }
    refreshSelected(result.data);
    setPendingAction(null);
    const actionDone = pendingAction === "approve" ? "Approved" : pendingAction === "reject" ? "Rejected" : "Reopened";
    setToast(`${actionDone} successfully — ${selected.order_id}`);
    // Reload full queue after brief delay
    setTimeout(load, 500);
  };

  if (loading) return (
    <div className="loading-indicator">
      <div className="status-dot connected" style={{ width: 16, height: 16 }} />
      <span>Loading human review queue...</span>
    </div>
  );

  if (error) return (
    <div className="error-indicator">
      <h3>Unable to load review queue</h3>
      <p>{error}</p>
      <button className="btn-retry" onClick={load}>Retry</button>
    </div>
  );

  const highP  = queue.filter(i => i.priority <= 15).length;
  const medP   = queue.filter(i => i.priority > 15 && i.priority <= 35).length;
  const lowP   = queue.filter(i => i.priority > 35).length;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Human Review</h1>
        <p className="page-subtitle">
          Some financial discrepancies cannot safely be resolved automatically. These cases require a finance operator to make the final decision.
        </p>
      </div>

      {/* Visual Workflow Ribbon */}
      <WorkflowVisualizer currentStepId="review-queue" onStepClick={(id) => onNavigateToTab && onNavigateToTab(id)} />

      {/* Empty State */}
      {queue.length === 0 ? (
        <EmptyState
          title="No cases currently pending human review."
          description="All flagged exceptions have been either automatically resolved with high AI confidence or decided by an operator."
          actionText="Go to Exceptions"
          onAction={() => onNavigateToTab && onNavigateToTab("exceptions")}
        />
      ) : (
        <>
          {/* KPI Cards */}
          <section className="dashboard-section">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--spacing-lg)" }}>
              {[
                { label: "Total Pending", val: queue.length, color: undefined },
                { label: "High Priority", val: highP, color: "var(--danger-text)" },
                { label: "Medium Priority", val: medP, color: "var(--warning-text)" },
                { label: "Low Priority", val: lowP, color: "var(--text-secondary)" },
              ].map(({ label, val, color }) => (
                <div key={label} className="card" style={{ padding: "var(--spacing-md)" }}>
                  <span className="kpi-card-header" style={{ fontSize: "11px" }}>{label}</span>
                  <span className="kpi-card-value font-mono" style={{ fontSize: "24px", color: color ?? "var(--text-primary)" }}>{val}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Queue Table */}
          <section className="dashboard-section">
            <h2 className="section-title">Pending Review Cases</h2>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Priority</th>
                    <th>Order ID</th>
                    <th>Exception Type</th>
                    <th>Resolution Status</th>
                    <th>Eff. Confidence</th>
                    <th>Safety Flags</th>
                    <th>Created</th>
                    <th style={{ textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.map((item) => {
                    const flags = Array.isArray(item.safety_flags) ? item.safety_flags : [];
                    const eff = item.effective_confidence ?? item.confidence;
                    return (
                      <tr key={item.resolution_id}>
                        <td>
                          <span style={{
                            display: "inline-block",
                            width: "26px", height: "26px", lineHeight: "26px",
                            textAlign: "center", borderRadius: "50%",
                            background: item.priority <= 15
                              ? "var(--danger-bg)"
                              : item.priority <= 35
                              ? "var(--warning-bg)"
                              : "var(--bg-primary)",
                            color: item.priority <= 15
                              ? "var(--danger-text)"
                              : item.priority <= 35
                              ? "var(--warning-text)"
                              : "var(--text-secondary)",
                            fontSize: "11px", fontWeight: 800,
                            fontFamily: "var(--font-mono)",
                          }}>
                            {item.priority}
                          </span>
                        </td>
                        <td className="font-mono" style={{ fontWeight: 600 }}>{item.order_id}</td>
                        <td style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>
                          {item.deterministic_exception_type}
                        </td>
                        <td>
                          <span className={`badge ${statusBadgeClass(item.resolution_status)}`}>
                            {formatStatusLabel(item.resolution_status)}
                          </span>
                        </td>
                        <td className="font-mono" style={{ fontWeight: 600, color: "var(--info-text)", fontSize: "12px" }}>
                          {fmtPct(eff)}
                        </td>
                        <td>
                          {flags.length === 0
                            ? <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>None</span>
                            : <span className="badge severity-high" style={{ fontSize: "10px" }}>
                                {flags.length} flag{flags.length > 1 ? "s" : ""}
                              </span>
                          }
                        </td>
                        <td style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                          {fmtTime(item.created_at)}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <button className="btn-action" onClick={() => setSelected(item)}>
                            Review
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {/* Detail Panel */}
      {selected && !pendingAction && (
        <CasePanel
          item={selected}
          investigations={{}}
          onAction={(action) => setPendingAction(action)}
          onClose={() => setSelected(null)}
        />
      )}

      {/* Confirm Modal */}
      {selected && pendingAction && (
        <ConfirmModal
          action={pendingAction}
          resolutionId={selected.resolution_id}
          onConfirm={handleConfirm}
          onCancel={() => setPendingAction(null)}
        />
      )}

      {/* Success Toast */}
      {toast && <SuccessToast message={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
};
