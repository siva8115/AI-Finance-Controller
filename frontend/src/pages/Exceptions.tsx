import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import type { ExceptionRecordResponse, AIInvestigationResponse } from "../types";
import { WorkflowVisualizer } from "../components/WorkflowVisualizer";
import { EmptyState } from "../components/EmptyState";
import { DiscrepancyBarChart } from "../components/DiscrepancyBarChart";

interface ExceptionsProps {
  onNavigateToTab?: (tab: string) => void;
}

export const Exceptions: React.FC<ExceptionsProps> = ({ onNavigateToTab }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // States
  const [exceptions, setExceptions] = useState<ExceptionRecordResponse[]>([]);
  const [investigations, setInvestigations] = useState<AIInvestigationResponse[]>([]);

  // Selected Exception Detail State
  const [selectedException, setSelectedException] = useState<ExceptionRecordResponse | null>(null);
  const [matchedInvestigation, setMatchedInvestigation] = useState<AIInvestigationResponse | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [exceptionsRes, investigationsRes] = await Promise.all([
        api.getExceptions(),
        api.getAIInvestigations(),
      ]);

      if (exceptionsRes.success) {
        const severityOrder: Record<string, number> = { HIGH: 1, MEDIUM: 2, LOW: 3 };
        const sorted = [...exceptionsRes.data].sort((a, b) => {
          const aOrder = severityOrder[a.severity.toUpperCase()] || 99;
          const bOrder = severityOrder[b.severity.toUpperCase()] || 99;
          if (aOrder !== bOrder) return aOrder - bOrder;
          return (b.difference || 0) - (a.difference || 0);
        });
        setExceptions(sorted);
      }
      if (investigationsRes.success) {
        setInvestigations(investigationsRes.data);
      }
    } catch (err: any) {
      console.error("Exceptions data load error:", err);
      setError("Failed to fetch exceptions. Please verify that the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedException) {
      const matched = investigations.find(
        (inv) => inv.order_id === selectedException.order_id
      );
      setMatchedInvestigation(matched || null);
    } else {
      setMatchedInvestigation(null);
    }
  }, [selectedException, investigations]);

  const handleRunBatchInvestigation = async () => {
    if (exceptions.length === 0) return;
    const runId = exceptions[0].run_id;
    setIsInvestigating(true);
    setToastMessage(null);
    try {
      const res = await api.runBatchAIInvestigation({
        reconciliation_run_id: runId,
        max_cases: 50,
      });
      if (res.success) {
        await api.runBatchResolution({
          reconciliation_run_id: runId,
          max_cases: 50,
        });

        setToastMessage({
          text: `AI Investigation complete: ${res.data.investigated_cases} exceptions investigated.`,
          type: "success",
        });
        await loadData();

        if (onNavigateToTab) {
          onNavigateToTab("ai-investigations");
        }
      }
    } catch (err: any) {
      setToastMessage({
        text: `Investigation run failed: ${err.message}`,
        type: "error",
      });
    } finally {
      setIsInvestigating(false);
    }
  };

  if (loading) {
    return (
      <div className="loading-indicator">
        <div className="status-dot connected" style={{ width: "16px", height: "16px" }}></div>
        <span>Loading flagged exception records...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-indicator">
        <h3>Backend Connection Unavailable</h3>
        <p>Start the Finance Controller backend and retry.</p>
        <button onClick={loadData} className="btn-retry">
          Retry Connection
        </button>
      </div>
    );
  }

  const formatCurrency = (val?: number) => {
    if (val === undefined || val === null) return "—";
    return `₹${val.toFixed(2)}`;
  };

  const totalExceptions = exceptions.length;
  const totalFinancialDifference = exceptions.reduce((sum, e) => sum + (e.difference || 0), 0);

  // Exception category map
  const categoryMap: Record<string, { count: number; impact: number }> = {};
  exceptions.forEach((exc) => {
    const type = exc.exception_type;
    if (!categoryMap[type]) {
      categoryMap[type] = { count: 0, impact: 0 };
    }
    categoryMap[type].count += 1;
    categoryMap[type].impact += exc.difference || 0;
  });

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--spacing-md)" }}>
          <div>
            <h1 className="page-title">What went wrong?</h1>
            <p className="page-subtitle">Review financial discrepancies detected by deterministic 3-way reconciliation.</p>
          </div>

          <button
            onClick={handleRunBatchInvestigation}
            disabled={isInvestigating || exceptions.length === 0}
            className="btn-action"
            style={{
              background: "var(--accent-primary)",
              borderColor: "var(--accent-primary-hover)",
              color: "#ffffff",
              fontWeight: 800,
              padding: "10px 20px",
              fontSize: "14px",
              boxShadow: "0 4px 14px var(--accent-glow)",
            }}
          >
            {isInvestigating ? "Investigating..." : "🤖 INVESTIGATE WITH AI"}
          </button>
        </div>
      </div>

      {/* Visual Workflow Ribbon */}
      <WorkflowVisualizer currentStepId="exceptions" onStepClick={(id) => onNavigateToTab && onNavigateToTab(id)} />

      {/* Toast */}
      {toastMessage && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: "8px",
            marginBottom: "var(--spacing-lg)",
            fontSize: "13px",
            backgroundColor: toastMessage.type === "success" ? "var(--success-bg)" : "var(--danger-bg)",
            border: `1px solid ${toastMessage.type === "success" ? "var(--success-border)" : "var(--danger-border)"}`,
            color: toastMessage.type === "success" ? "var(--success-text)" : "var(--danger-text)",
            fontWeight: 500,
          }}
        >
          {toastMessage.text}
        </div>
      )}

      {/* Empty State */}
      {exceptions.length === 0 ? (
        <EmptyState
          title="No discrepancies found"
          description="All checked transactions matched successfully. Run reconciliation if you imported new datasets."
          actionText="RUN 3-WAY RECONCILIATION"
          onAction={() => onNavigateToTab && onNavigateToTab("reconciliation")}
        />
      ) : (
        <>
          {/* KPI Header Cards */}
          <section className="dashboard-section">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--spacing-lg)" }}>
              <div className="card">
                <span className="kpi-card-header">Total Exception Cases</span>
                <span className="kpi-card-value font-mono">{totalExceptions}</span>
              </div>
              <div className="card" style={{ borderLeft: "4px solid var(--danger)" }}>
                <span className="kpi-card-header">Total Unexplained Difference</span>
                <span className="kpi-card-value font-mono" style={{ color: "var(--danger-text)" }}>
                  {formatCurrency(totalFinancialDifference)}
                </span>
              </div>
              <div className="card">
                <span className="kpi-card-header">AI Investigations Generated</span>
                <span className="kpi-card-value font-mono">{investigations.length}</span>
              </div>
            </div>
          </section>

          {/* Super Visual Category Chart */}
          {Object.keys(categoryMap).length > 0 && (
            <section className="dashboard-section">
              <DiscrepancyBarChart categoryMap={categoryMap} />
            </section>
          )}

          {/* Exception Table */}
          <section className="dashboard-section">
            <h2 className="section-title">Detected Financial Discrepancies</h2>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Order ID</th>
                    <th>Exception Type</th>
                    <th>Expected</th>
                    <th>Actual</th>
                    <th>Difference</th>
                    <th>Severity</th>
                    <th>AI Status</th>
                    <th style={{ textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {exceptions.map((row) => (
                    <tr key={row.id}>
                      <td className="font-mono" style={{ fontWeight: 700 }}>{row.order_id || "—"}</td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>{row.exception_type}</td>
                      <td className="font-mono">{row.expected_value || "—"}</td>
                      <td className="font-mono">{row.actual_value || "—"}</td>
                      <td className="font-mono" style={{ fontWeight: 800, color: "var(--danger-text)" }}>
                        {formatCurrency(row.difference)}
                      </td>
                      <td>
                        <span className={`badge severity-${row.severity.toLowerCase()}`}>
                          {row.severity}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${row.ai_investigated ? "resolved" : "detected"}`}>
                          {row.ai_investigated ? "AI INVESTIGATED" : "NOT INVESTIGATED"}
                        </span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button className="btn-action" onClick={() => setSelectedException(row)}>
                          Audit & Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {/* Exception Detail Modal */}
      {selectedException && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            backgroundColor: "rgba(0, 0, 0, 0.7)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 200,
            padding: "var(--spacing-md)",
          }}
        >
          <div
            className="card"
            style={{
              width: "650px",
              maxWidth: "100%",
              backgroundColor: "var(--bg-surface)",
              maxHeight: "95vh",
              overflowY: "auto",
              borderRadius: "12px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderBottom: "1px solid var(--border-color)",
                paddingBottom: "var(--spacing-md)",
                marginBottom: "var(--spacing-md)",
              }}
            >
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>
                Exception Comparison: <span className="font-mono">{selectedException.order_id || "N/A"}</span>
              </h3>
              <button
                onClick={() => setSelectedException(null)}
                style={{ background: "transparent", border: "none", color: "var(--text-secondary)", fontSize: "22px", cursor: "pointer" }}
              >
                &times;
              </button>
            </div>

            {/* Plain English Discrepancy Statement */}
            <div
              style={{
                backgroundColor: "var(--danger-bg)",
                border: "1px solid var(--danger-border)",
                padding: "12px 16px",
                borderRadius: "8px",
                marginBottom: "var(--spacing-md)",
                fontSize: "13px",
                color: "var(--danger-text)",
                lineHeight: "1.5",
              }}
            >
              <strong>Detected Discrepancy:</strong> The customer was charged {selectedException.expected_value || formatCurrency(selectedException.difference)}, but actual ledger value was {selectedException.actual_value || "different"}. The controller detected a {formatCurrency(selectedException.difference)} difference.
            </div>

            {/* Structured Table */}
            <div className="table-container" style={{ marginBottom: "var(--spacing-lg)" }}>
              <table>
                <thead>
                  <tr>
                    <th>Source Ledger</th>
                    <th>Recorded Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Order ID</td>
                    <td className="font-mono" style={{ fontWeight: 600 }}>{selectedException.order_id}</td>
                  </tr>
                  <tr>
                    <td>Exception Type</td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{selectedException.exception_type}</td>
                  </tr>
                  <tr>
                    <td>Expected Contract Amount</td>
                    <td className="font-mono">{selectedException.expected_value || "—"}</td>
                  </tr>
                  <tr>
                    <td>Actual Ledger Amount</td>
                    <td className="font-mono">{selectedException.actual_value || "—"}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 700, color: "var(--danger-text)" }}>Financial Difference</td>
                    <td className="font-mono" style={{ fontWeight: 800, color: "var(--danger-text)" }}>
                      {formatCurrency(selectedException.difference)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* AI Investigation Section */}
            {matchedInvestigation ? (
              <div
                style={{
                  backgroundColor: "var(--bg-primary)",
                  padding: "14px",
                  borderRadius: "8px",
                  borderLeft: "4px solid var(--accent-primary)",
                  marginBottom: "var(--spacing-md)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 800, color: "var(--accent-primary-hover)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  🤖 Advisory AI Investigation Finding
                </div>
                <div style={{ fontSize: "13px", marginTop: "6px", fontWeight: 600 }}>
                  Likely Cause: {matchedInvestigation.likely_cause}
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px" }}>
                  Confidence: <span className="font-mono">{((matchedInvestigation.effective_confidence ?? matchedInvestigation.ai_confidence ?? 0) * 100).toFixed(1)}%</span> &bull; Recommendation: {matchedInvestigation.recommended_action}
                </div>
              </div>
            ) : null}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              {!matchedInvestigation && (
                <button
                  onClick={handleRunBatchInvestigation}
                  disabled={isInvestigating}
                  className="btn-action"
                  style={{ background: "var(--accent-primary)", borderColor: "var(--accent-primary-hover)", color: "#ffffff", fontWeight: 700 }}
                >
                  {isInvestigating ? "Investigating..." : "🤖 INVESTIGATE WITH AI"}
                </button>
              )}
              <button className="btn-retry" onClick={() => setSelectedException(null)}>
                Close Window
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
