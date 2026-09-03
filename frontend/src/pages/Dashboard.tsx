import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import type {
  SystemOverview,
  ReconciliationRunSummary,
  ExceptionRecordResponse,
  ResolutionSummaryResponse,
} from "../types";
import { WorkflowVisualizer } from "../components/WorkflowVisualizer";
import { EmptyState } from "../components/EmptyState";
import { ReconciliationDonutChart } from "../components/ReconciliationDonutChart";
import { DiscrepancyBarChart } from "../components/DiscrepancyBarChart";
import { LedgerWaterfallChart } from "../components/LedgerWaterfallChart";

interface DashboardProps {
  onNavigateToTab?: (tab: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onNavigateToTab }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // States
  const [systemOverview, setSystemOverview] = useState<SystemOverview | null>(null);
  const [reconSummary, setReconSummary] = useState<ReconciliationRunSummary | null>(null);
  const [exceptions, setExceptions] = useState<ExceptionRecordResponse[]>([]);
  const [resolutionSummary, setResolutionSummary] = useState<ResolutionSummaryResponse | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        overviewRes,
        reconRes,
        exceptionsRes,
        resolutionRes,
      ] = await Promise.all([
        api.getDataSummary(),
        api.getReconciliationSummary(),
        api.getExceptions(),
        api.getResolutionSummary(),
      ]);

      if (overviewRes.success) setSystemOverview(overviewRes.data);
      if (reconRes.success) setReconSummary(reconRes.data);
      if (exceptionsRes.success) setExceptions(exceptionsRes.data);
      if (resolutionRes.success) setResolutionSummary(resolutionRes.data);
    } catch (err: any) {
      console.error("Dashboard data load error:", err);
      setError("Failed to fetch dashboard metrics. Please verify that the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Quick Action: Run Reconciliation
  const handleRunReconciliation = async () => {
    setActionLoading("Reconciling 3-way transactions...");
    setActionMessage(null);
    try {
      const res = await api.runReconciliation();
      if (res.success) {
        setActionMessage({
          text: `Reconciliation run completed: ${res.data.matched} matched, ${res.data.exceptions} exceptions detected.`,
          type: "success",
        });
        await loadData();
      }
    } catch (err: any) {
      setActionMessage({
        text: `Reconciliation failed: ${err.message}`,
        type: "error",
      });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="loading-indicator">
        <div className="status-dot connected" style={{ width: "16px", height: "16px" }}></div>
        <span>Loading financial dashboard operations data...</span>
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

  // Derived KPI metrics
  const totalOrders = systemOverview?.total_orders_in_db ?? 0;
  const totalPayments = systemOverview?.total_payments_in_db ?? 0;
  const totalSettlements = systemOverview?.total_settlements_in_db ?? 0;
  const isDbEmpty = totalOrders === 0 && totalPayments === 0 && totalSettlements === 0;

  const totalMatched = reconSummary?.matched ?? 0;
  const totalExceptions = reconSummary?.exceptions ?? 0;
  const totalReconciled = reconSummary?.total_records ?? 0;
  const matchRate = totalReconciled > 0 ? (totalMatched / totalReconciled) * 100 : 0;

  const humanReview = (resolutionSummary?.human_review_required ?? 0) + (resolutionSummary?.review_recommended ?? 0);
  const financialExposure = exceptions.reduce((sum, exc) => sum + (exc.difference || 0), 0);

  // Exception category breakdown with calculated financial impact
  const categoryMap: Record<string, { count: number; impact: number }> = {};
  exceptions.forEach((exc) => {
    const type = exc.exception_type;
    if (!categoryMap[type]) {
      categoryMap[type] = { count: 0, impact: 0 };
    }
    categoryMap[type].count += 1;
    categoryMap[type].impact += exc.difference || 0;
  });

  const datasetLabel =
    systemOverview?.dataset_source === "UPLOADED"
      ? "Dataset: Uploaded"
      : systemOverview?.dataset_source === "DEMO"
      ? "Dataset: Demo"
      : "Dataset: Empty";

  const hasReconciliationRun = (systemOverview?.total_reconciliation_runs ?? 0) > 0;

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--spacing-md)" }}>
          <div>
            <h1 className="page-title">Finance Control Center</h1>
            <p className="page-subtitle">See where customer payments and bank settlements don't match.</p>
          </div>

          <div style={{ display: "flex", gap: "var(--spacing-sm)", alignItems: "center", flexWrap: "wrap" }}>
            <span
              style={{
                fontSize: "11px",
                padding: "4px 10px",
                borderRadius: "20px",
                backgroundColor:
                  systemOverview?.dataset_source === "UPLOADED"
                    ? "var(--info-bg)"
                    : systemOverview?.dataset_source === "DEMO"
                    ? "var(--warning-bg)"
                    : "var(--bg-surface)",
                color:
                  systemOverview?.dataset_source === "UPLOADED"
                    ? "var(--info-text)"
                    : systemOverview?.dataset_source === "DEMO"
                    ? "var(--warning-text)"
                    : "var(--text-secondary)",
                border: "1px solid var(--border-color)",
                fontWeight: 700,
                letterSpacing: "0.5px",
              }}
            >
              {datasetLabel}
            </span>

            {!hasReconciliationRun ? (
              <button
                onClick={handleRunReconciliation}
                disabled={actionLoading !== null}
                className="btn-action"
                style={{
                  background: "var(--accent-primary)",
                  borderColor: "var(--accent-primary-hover)",
                  color: "#ffffff",
                  fontWeight: 700,
                  boxShadow: "0 2px 10px var(--accent-glow)",
                }}
              >
                ⚡ FIND DISCREPANCIES
              </button>
            ) : (
              <button
                onClick={() => onNavigateToTab && onNavigateToTab("exceptions")}
                className="btn-action"
                style={{
                  background: "var(--accent-primary)",
                  borderColor: "var(--accent-primary-hover)",
                  color: "#ffffff",
                  fontWeight: 700,
                  boxShadow: "0 2px 10px var(--accent-glow)",
                }}
              >
                REVIEW EXCEPTIONS &rarr;
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Visual Workflow Ribbon */}
      <WorkflowVisualizer currentStepId="dashboard" onStepClick={(id) => onNavigateToTab && onNavigateToTab(id)} />

      {/* Toast Notification */}
      {actionMessage && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: "8px",
            marginBottom: "var(--spacing-lg)",
            fontSize: "13px",
            backgroundColor: actionMessage.type === "success" ? "var(--success-bg)" : "var(--danger-bg)",
            border: `1px solid ${actionMessage.type === "success" ? "var(--success-border)" : "var(--danger-border)"}`,
            color: actionMessage.type === "success" ? "var(--success-text)" : "var(--danger-text)",
            fontWeight: 500,
          }}
        >
          {actionMessage.text}
        </div>
      )}

      {/* EMPTY STATE IF NO DATA */}
      {isDbEmpty ? (
        <EmptyState
          title="No finance data yet"
          description="Upload Orders, Payments and Settlements to start finding financial discrepancies."
          actionText="IMPORT FINANCE DATA"
          onAction={() => onNavigateToTab && onNavigateToTab("data-import")}
        />
      ) : (
        <>
          {/* Top Primary KPI Grid */}
          <section className="dashboard-section">
            <div className="grid-cols-4">
              <div className="card">
                <span className="kpi-card-header">Total Orders</span>
                <span className="kpi-card-value font-mono">{totalOrders.toLocaleString()}</span>
                <span className="kpi-card-meta">Expected revenue logs</span>
              </div>
              <div className="card">
                <span className="kpi-card-header">Total Payments</span>
                <span className="kpi-card-value font-mono">{totalPayments.toLocaleString()}</span>
                <span className="kpi-card-meta">Gateway captured</span>
              </div>
              <div className="card">
                <span className="kpi-card-header">Total Settlements</span>
                <span className="kpi-card-value font-mono">{totalSettlements.toLocaleString()}</span>
                <span className="kpi-card-meta">Bank payout ledger</span>
              </div>
              <div className="card">
                <span className="kpi-card-header">Match Rate</span>
                <span className="kpi-card-value font-mono" style={{ color: "var(--info-text)" }}>
                  {matchRate.toFixed(1)}%
                </span>
                <span className="kpi-card-meta">{totalMatched} matched clean</span>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--spacing-lg)", marginTop: "var(--spacing-md)" }}>
              <div className="card" style={{ borderLeft: "4px solid var(--danger)" }}>
                <span className="kpi-card-header">Financial Exposure</span>
                <span className="kpi-card-value font-mono" style={{ color: "var(--danger-text)", fontSize: "28px" }}>
                  ₹{financialExposure.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </span>
                <span className="kpi-card-meta" style={{ fontWeight: 600 }}>
                  Total value of unresolved discrepancies
                </span>
              </div>
              <div className="card">
                <span className="kpi-card-header">Open Exceptions</span>
                <span className="kpi-card-value font-mono" style={{ color: "var(--warning-text)" }}>
                  {totalExceptions}
                </span>
                <span className="kpi-card-meta">Discrepancy cases detected</span>
              </div>
              <div className="card">
                <span className="kpi-card-header">Cases Requiring Review</span>
                <span className="kpi-card-value font-mono" style={{ color: "var(--warning-text)" }}>
                  {humanReview}
                </span>
                <span className="kpi-card-meta">Safety-gated operator reviews</span>
              </div>
            </div>
          </section>

          {/* Interactive Super Visual Charts Section */}
          <section className="dashboard-section">
            <h2 className="section-title">Visual Analytics & Distribution</h2>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--spacing-lg)", marginBottom: "var(--spacing-lg)" }}>
              <ReconciliationDonutChart
                matchedCount={totalMatched}
                exceptionsCount={totalExceptions}
                totalRecords={totalReconciled}
              />
              <LedgerWaterfallChart
                totalOrders={totalOrders}
                totalPayments={totalPayments}
                totalSettlements={totalSettlements}
              />
            </div>
            {Object.keys(categoryMap).length > 0 && (
              <DiscrepancyBarChart categoryMap={categoryMap} />
            )}
          </section>

          {/* "What did we find?" Table Section */}
          <section className="dashboard-section">
            <h2 className="section-title">What did we find?</h2>
            <div className="table-container">
              {Object.keys(categoryMap).length === 0 ? (
                <div className="empty-state">
                  No discrepancies found. All checked transactions matched successfully.
                </div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Exception Category</th>
                      <th>Cases</th>
                      <th style={{ textAlign: "right" }}>Financial Impact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(categoryMap).map(([type, data]) => (
                      <tr key={type}>
                        <td style={{ fontWeight: 600, fontFamily: "var(--font-mono)", fontSize: "12.5px" }}>
                          {type.replace("_", " ")}
                        </td>
                        <td style={{ fontWeight: 600 }}>{data.count} cases</td>
                        <td className="font-mono" style={{ textAlign: "right", fontWeight: 700, color: "var(--danger-text)" }}>
                          ₹{data.impact.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>

          {/* Recent Discrepancy Items Table */}
          <section className="dashboard-section">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--spacing-md)" }}>
              <h2 className="section-title" style={{ margin: 0 }}>Recent Unresolved Discrepancies</h2>
              {onNavigateToTab && exceptions.length > 0 && (
                <button
                  onClick={() => onNavigateToTab("exceptions")}
                  style={{ background: "transparent", border: "none", color: "var(--accent-primary-hover)", fontSize: "12px", cursor: "pointer", fontWeight: 700 }}
                >
                  View all {exceptions.length} exceptions &rarr;
                </button>
              )}
            </div>

            <div className="table-container">
              {exceptions.length === 0 ? (
                <div className="empty-state">No unresolved discrepancies detected.</div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Order ID</th>
                      <th>Exception Type</th>
                      <th>Expected</th>
                      <th>Actual</th>
                      <th>Difference</th>
                      <th>Severity</th>
                      <th style={{ textAlign: "right" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exceptions.slice(0, 8).map((exc) => (
                      <tr key={exc.id}>
                        <td className="font-mono" style={{ fontWeight: 600 }}>{exc.order_id || "N/A"}</td>
                        <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>
                          {exc.exception_type}
                        </td>
                        <td>{exc.expected_value || "—"}</td>
                        <td>{exc.actual_value || "—"}</td>
                        <td className="font-mono" style={{ fontWeight: 700, color: "var(--danger-text)" }}>
                          {exc.difference ? `₹${exc.difference.toFixed(2)}` : "—"}
                        </td>
                        <td>
                          <span className={`badge severity-${exc.severity.toLowerCase()}`}>
                            {exc.severity}
                          </span>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {onNavigateToTab && (
                            <button className="btn-action" onClick={() => onNavigateToTab("exceptions")}>
                              Review
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
};
