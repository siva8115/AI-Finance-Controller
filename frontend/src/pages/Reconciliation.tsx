import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import type { ReconciliationRunSummary, ReconciliationResultResponse } from "../types";
import { WorkflowVisualizer } from "../components/WorkflowVisualizer";
import { EmptyState } from "../components/EmptyState";

interface ReconciliationProps {
  onNavigateToTab?: (tab: string) => void;
}

export const Reconciliation: React.FC<ReconciliationProps> = ({ onNavigateToTab }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRunningRecon, setIsRunningRecon] = useState(false);
  const [reconProgressStep, setReconProgressStep] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // States
  const [runSummary, setRunSummary] = useState<ReconciliationRunSummary | null>(null);
  const [results, setResults] = useState<ReconciliationResultResponse[]>([]);
  const [filteredResults, setFilteredResults] = useState<ReconciliationResultResponse[]>([]);

  // Search and Filter States
  const [searchOrderId, setSearchOrderId] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL"); // ALL, MATCHED, EXCEPTION
  const [exceptionFilter, setExceptionFilter] = useState("ALL");

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 25;

  // Selected Detail Modal State
  const [selectedResult, setSelectedResult] = useState<ReconciliationResultResponse | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryRes, resultsRes] = await Promise.all([
        api.getReconciliationSummary(),
        api.getReconciliationResults(),
      ]);

      if (summaryRes.success) setRunSummary(summaryRes.data);
      if (resultsRes.success) {
        setResults(resultsRes.data);
        setFilteredResults(resultsRes.data);
      }
    } catch (err: any) {
      console.error("Reconciliation data load error:", err);
      setError("Failed to fetch reconciliation metrics. Please verify that the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Filter Logic
  useEffect(() => {
    let temp = [...results];

    if (searchOrderId.trim()) {
      temp = temp.filter((r) =>
        r.order_id.toLowerCase().includes(searchOrderId.toLowerCase().trim())
      );
    }

    if (statusFilter !== "ALL") {
      temp = temp.filter((r) => r.reconciliation_status === statusFilter);
    }

    if (exceptionFilter !== "ALL") {
      temp = temp.filter((r) => r.exception_types && r.exception_types.includes(exceptionFilter));
    }

    setFilteredResults(temp);
    setCurrentPage(1);
  }, [searchOrderId, statusFilter, exceptionFilter, results]);

  // Run Reconciliation Trigger with Progress Sequence
  const handleExecuteReconciliation = async () => {
    setIsRunningRecon(true);
    setToastMessage(null);
    try {
      setReconProgressStep("Analyzing transactions...");
      await new Promise((r) => setTimeout(r, 300));

      setReconProgressStep("Matching Orders with Payments...");
      await new Promise((r) => setTimeout(r, 300));

      setReconProgressStep("Matching Payments with Settlements...");
      await new Promise((r) => setTimeout(r, 300));

      setReconProgressStep("Checking settlement amounts...");
      await new Promise((r) => setTimeout(r, 300));

      setReconProgressStep("Detecting anomalies...");
      const res = await api.runReconciliation();

      if (res.success) {
        setReconProgressStep("Reconciliation complete.");
        setToastMessage({
          text: `Reconciliation complete: ${res.data.matched} matched clean, ${res.data.exceptions} discrepancies detected.`,
          type: "success",
        });
        await loadData();
      }
    } catch (err: any) {
      setToastMessage({
        text: `Reconciliation run failed: ${err.message}`,
        type: "error",
      });
    } finally {
      setIsRunningRecon(false);
      setReconProgressStep(null);
    }
  };

  if (loading) {
    return (
      <div className="loading-indicator">
        <div className="status-dot connected" style={{ width: "16px", height: "16px" }}></div>
        <span>Loading reconciliation run data...</span>
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

  // Pagination calculations
  const indexOfLastRow = currentPage * rowsPerPage;
  const indexOfFirstRow = indexOfLastRow - rowsPerPage;
  const currentRows = filteredResults.slice(indexOfFirstRow, indexOfLastRow);
  const totalPages = Math.ceil(filteredResults.length / rowsPerPage);

  const matchedCount = runSummary?.matched ?? 0;
  const totalRecords = runSummary?.total_records ?? 0;
  const matchRate = totalRecords > 0 ? (matchedCount / totalRecords) * 100 : 0;

  const exceptionCategories = [
    "MISSING_PAYMENT",
    "UNMATCHED_SETTLEMENT",
    "AMOUNT_MISMATCH",
    "FEE_DISCREPANCY",
    "TIMING_DELAY",
    "DUPLICATE_PAYMENT",
    "UNACCOUNTED_REFUND",
  ];

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--spacing-md)" }}>
          <div>
            <h1 className="page-title">3-Way Reconciliation</h1>
            <p className="page-subtitle">
              Reconciliation compares each Order with its Payment and Bank Settlement to determine whether the money flow is correct.
            </p>
          </div>

          <button
            onClick={handleExecuteReconciliation}
            disabled={isRunningRecon}
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
            {isRunningRecon ? "Running Reconciliation..." : "⚡ RUN 3-WAY RECONCILIATION"}
          </button>
        </div>
      </div>

      {/* Visual Workflow Ribbon */}
      <WorkflowVisualizer currentStepId="reconciliation" onStepClick={(id) => onNavigateToTab && onNavigateToTab(id)} />

      {/* Progress Toast */}
      {reconProgressStep && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: "8px",
            marginBottom: "var(--spacing-lg)",
            fontSize: "13px",
            backgroundColor: "var(--info-bg)",
            border: "1px solid var(--info-border)",
            color: "var(--info-text)",
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <div className="status-dot connected" style={{ width: "10px", height: "10px" }}></div>
          <span>{reconProgressStep}</span>
        </div>
      )}

      {/* Notification Toast */}
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
      {results.length === 0 ? (
        <EmptyState
          title="Your data is ready"
          description="Run 3-way reconciliation to find financial discrepancies between your Orders, Payments, and Bank Settlements."
          actionText="RUN 3-WAY RECONCILIATION"
          onAction={handleExecuteReconciliation}
        />
      ) : (
        <>
          {/* KPI Summary Cards */}
          <section className="dashboard-section">
            <div className="grid-cols-4">
              <div className="card">
                <span className="kpi-card-header">Transactions Checked</span>
                <span className="kpi-card-value font-mono">{totalRecords}</span>
              </div>
              <div className="card">
                <span className="kpi-card-header">Matched Clean</span>
                <span className="kpi-card-value font-mono" style={{ color: "var(--success-text)" }}>
                  {matchedCount}
                </span>
              </div>
              <div className="card">
                <span className="kpi-card-header">Exceptions</span>
                <span className="kpi-card-value font-mono" style={{ color: "var(--danger-text)" }}>
                  {runSummary?.exceptions ?? 0}
                </span>
              </div>
              <div className="card">
                <span className="kpi-card-header">Match Rate</span>
                <span className="kpi-card-value font-mono" style={{ color: "var(--info-text)" }}>
                  {matchRate.toFixed(1)}%
                </span>
              </div>
            </div>
          </section>

          {/* Results Table Section */}
          <section className="dashboard-section">
            <h2 className="section-title">Reconciliation Results Registry</h2>

            {/* Filter Toolbar */}
            <div
              style={{
                display: "flex",
                gap: "var(--spacing-md)",
                marginBottom: "var(--spacing-md)",
                flexWrap: "wrap",
                alignItems: "center",
              }}
            >
              <input
                type="text"
                placeholder="Search Order ID..."
                value={searchOrderId}
                onChange={(e) => setSearchOrderId(e.target.value)}
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-primary)",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  fontSize: "13px",
                  minWidth: "220px",
                  fontFamily: "var(--font-sans)",
                }}
              />

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-primary)",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  fontSize: "13px",
                  fontFamily: "var(--font-sans)",
                }}
              >
                <option value="ALL">All Statuses</option>
                <option value="MATCHED">Matched</option>
                <option value="EXCEPTION">Exceptions Only</option>
              </select>

              <select
                value={exceptionFilter}
                onChange={(e) => setExceptionFilter(e.target.value)}
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-primary)",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  fontSize: "13px",
                  fontFamily: "var(--font-sans)",
                }}
              >
                <option value="ALL">All Exception Categories</option>
                {exceptionCategories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            {/* Table */}
            <div className="table-container">
              {currentRows.length === 0 ? (
                <div className="empty-state">No matching reconciliation records.</div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Order ID</th>
                      <th>Order Amount</th>
                      <th>Payment Amount</th>
                      <th>Settlement Gross</th>
                      <th>Difference</th>
                      <th>Status</th>
                      <th style={{ textAlign: "right" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentRows.map((row) => (
                      <tr key={row.id}>
                        <td className="font-mono" style={{ fontWeight: 700 }}>{row.order_id}</td>
                        <td className="font-mono">{formatCurrency(row.order_amount)}</td>
                        <td className="font-mono">{formatCurrency(row.payment_amount)}</td>
                        <td className="font-mono">{formatCurrency(row.settlement_gross_amount)}</td>
                        <td
                          className="font-mono"
                          style={{
                            fontWeight: 700,
                            color: (row.amount_difference || 0) !== 0 ? "var(--danger-text)" : "inherit",
                          }}
                        >
                          {formatCurrency(row.amount_difference)}
                        </td>
                        <td>
                          <span
                            className={`badge ${
                              row.reconciliation_status === "MATCHED" ? "resolved" : "detected"
                            }`}
                          >
                            {row.reconciliation_status === "MATCHED" ? "✓ MATCHED" : "⚠ EXCEPTION"}
                          </span>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <button className="btn-action" onClick={() => setSelectedResult(row)}>
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginTop: "var(--spacing-md)",
                }}
              >
                <button
                  onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                  disabled={currentPage === 1}
                  className="btn-action"
                  style={{ padding: "6px 14px" }}
                >
                  Previous
                </button>
                <span style={{ fontSize: "12.5px", color: "var(--text-secondary)", fontWeight: 500 }}>
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                  disabled={currentPage === totalPages}
                  className="btn-action"
                  style={{ padding: "6px 14px" }}
                >
                  Next
                </button>
              </div>
            )}
          </section>
        </>
      )}

      {/* Detail Modal */}
      {selectedResult && (
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
              width: "600px",
              maxWidth: "100%",
              backgroundColor: "var(--bg-surface)",
              maxHeight: "90vh",
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
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: "700" }}>
                3-Way Transaction Breakdown: <span className="font-mono">{selectedResult.order_id}</span>
              </h3>
              <button
                onClick={() => setSelectedResult(null)}
                style={{ background: "transparent", border: "none", color: "var(--text-secondary)", fontSize: "22px", cursor: "pointer" }}
              >
                &times;
              </button>
            </div>

            {/* Money Flow Table */}
            <div className="table-container" style={{ marginBottom: "var(--spacing-lg)" }}>
              <table>
                <thead>
                  <tr>
                    <th>Source Ledger</th>
                    <th>Recorded Amount</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Customer Order</td>
                    <td className="font-mono" style={{ fontWeight: 600 }}>{formatCurrency(selectedResult.order_amount)}</td>
                  </tr>
                  <tr>
                    <td>Payment Gateway</td>
                    <td className="font-mono" style={{ fontWeight: 600 }}>{formatCurrency(selectedResult.payment_amount)}</td>
                  </tr>
                  <tr>
                    <td>Bank Settlement Gross</td>
                    <td className="font-mono" style={{ fontWeight: 600 }}>{formatCurrency(selectedResult.settlement_gross_amount)}</td>
                  </tr>
                  <tr>
                    <td>Bank Settlement Net</td>
                    <td className="font-mono" style={{ fontWeight: 600 }}>{formatCurrency(selectedResult.settlement_net_amount)}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 700, color: "var(--danger-text)" }}>Detected Difference</td>
                    <td className="font-mono" style={{ fontWeight: 800, color: "var(--danger-text)" }}>
                      {formatCurrency(selectedResult.amount_difference)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Plain English explanation */}
            <div
              style={{
                backgroundColor: "var(--bg-primary)",
                padding: "12px 16px",
                borderRadius: "8px",
                borderLeft: "4px solid var(--accent-primary)",
                marginBottom: "var(--spacing-lg)",
                fontSize: "13px",
                color: "var(--text-primary)",
                lineHeight: "1.5",
              }}
            >
              <strong>Controller Audit Analysis:</strong>{" "}
              {selectedResult.explanation ||
                `The customer was charged ${formatCurrency(selectedResult.order_amount)}, but ${formatCurrency(selectedResult.settlement_gross_amount)} reached bank settlement. The controller detected a ${formatCurrency(selectedResult.amount_difference)} discrepancy.`}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button className="btn-retry" onClick={() => setSelectedResult(null)}>
                Close Breakdown
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
