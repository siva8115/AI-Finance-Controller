import React, { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import type { AIInvestigationResponse, ResolutionSummaryResponse } from "../types";
import { WorkflowVisualizer } from "../components/WorkflowVisualizer";
import { EmptyState } from "../components/EmptyState";

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
    case "REVIEW_RECOMMENDED": return "detected";   // amber
    case "HUMAN_REVIEW_REQUIRED": return "detected";
    case "AI_FAILED": return "severity-high";
    default: return "detected";
  }
}

function formatStatusLabel(status: string): string {
  if (status === "AI_FAILED") return "ROUTING TO HUMAN REVIEW";
  return status;
}

// ─────────────────────────────────────────────────────────────────────────────
// Detail Panel Component
// ─────────────────────────────────────────────────────────────────────────────

const DetailPanel: React.FC<{
  inv: AIInvestigationResponse;
  onClose: () => void;
}> = ({ inv, onClose }) => {
  const flags = Array.isArray(inv.safety_flags) ? inv.safety_flags : [];
  const facts = Array.isArray(inv.evidence_facts) ? inv.evidence_facts : [];
  const causes = Array.isArray(inv.possible_causes) ? inv.possible_causes : [];
  const gaps = Array.isArray(inv.evidence_gaps) ? inv.evidence_gaps : [];

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, width: "100%", height: "100%",
      backgroundColor: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)", display: "flex",
      alignItems: "flex-start", justifyContent: "flex-end", zIndex: 200,
    }}>
      <div style={{
        width: "540px", maxWidth: "100vw", height: "100vh", overflowY: "auto",
        backgroundColor: "var(--bg-surface)", borderLeft: "1px solid var(--border-color)",
        display: "flex", flexDirection: "column", boxShadow: "var(--shadow-lg)",
      }}>
        {/* Header */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "var(--spacing-lg)", borderBottom: "1px solid var(--border-color)",
          position: "sticky", top: 0, background: "var(--bg-surface)", zIndex: 1,
        }}>
          <div>
            <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-primary)" }}>
              Investigation Detail
            </div>
            <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--text-secondary)", marginTop: "2px" }}>
              {inv.investigation_id}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "transparent", border: "none",
            color: "var(--text-secondary)", fontSize: "22px", cursor: "pointer", lineHeight: 1,
          }}>&times;</button>
        </div>

        <div style={{ padding: "var(--spacing-lg)", display: "flex", flexDirection: "column", gap: "var(--spacing-lg)" }}>

          {/* ── AI FAILED warning ─────────────────────────────────────────── */}
          {inv.investigation_status === "AI_FAILED" && (
            <div style={{
              background: "var(--danger-bg)", border: "1px solid var(--danger-border)",
              borderRadius: "8px", padding: "var(--spacing-md)",
            }}>
              <div style={{ fontWeight: 700, color: "var(--danger-text)", marginBottom: "4px" }}>
                ⚠ AI Investigation Failed &bull; ROUTING TO HUMAN REVIEW
              </div>
              <div style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                {inv.summary}
              </div>
              <div style={{ marginTop: "8px", fontSize: "12px", color: "var(--text-secondary)" }}>
                Recommended action: {inv.recommended_action}
              </div>
              <div style={{ marginTop: "8px" }}>
                <span className="badge detected">HUMAN REVIEW REQUIRED</span>
              </div>
            </div>
          )}

          {/* ── Investigation metadata ─────────────────────────────────────── */}
          <section>
            <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
              Investigation Details
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--spacing-md)", backgroundColor: "var(--bg-primary)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
              {[
                ["Order ID", <span key="ord" className="font-mono">{inv.order_id}</span>],
                ["Exception Type", <span key="exc" className="font-mono" style={{ fontSize: "11px" }}>{inv.exception_type}</span>],
                ["Status", <span key="st" className={`badge ${statusBadgeClass(inv.investigation_status)}`}>{formatStatusLabel(inv.investigation_status)}</span>],
                ["Created", fmtTime(inv.created_at)],
              ].map(([label, val]) => (
                <div key={String(label)}>
                  <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>{label}</div>
                  <div style={{ fontSize: "13px", fontWeight: 600, marginTop: "2px" }}>{val}</div>
                </div>
              ))}
            </div>
          </section>

          {/* ── Evidence Escalation Architecture ───────────────────────────── */}
          <section style={{
            background: "var(--bg-primary)", border: "1px solid var(--border-color)",
            borderRadius: "8px", padding: "var(--spacing-md)",
          }}>
            <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--info-text)", margin: "0 0 var(--spacing-sm)", fontWeight: 800 }}>
              ⚡ Evidence Escalation Architecture
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--spacing-sm)", marginBottom: "var(--spacing-md)" }}>
              <div>
                <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>Evidence Level</div>
                <div style={{ marginTop: "3px" }}>
                  <span className="badge" style={{
                    background: (inv.evidence_level === "LEVEL 3") ? "rgba(239, 68, 68, 0.2)" : (inv.evidence_level === "LEVEL 2") ? "rgba(245, 158, 11, 0.2)" : "rgba(59, 130, 246, 0.2)",
                    color: (inv.evidence_level === "LEVEL 3") ? "var(--danger-text)" : (inv.evidence_level === "LEVEL 2") ? "var(--warning-text)" : "var(--info-text)",
                    border: "1px solid currentColor",
                  }}>
                    {inv.evidence_level || "LEVEL 1"}
                  </span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>Records Analyzed</div>
                <div className="font-mono" style={{ fontSize: "13px", fontWeight: 700, marginTop: "2px", color: "var(--text-primary)" }}>
                  {inv.evidence_records_count ?? 3} records
                </div>
              </div>
              <div>
                <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>AI Attempts</div>
                <div className="font-mono" style={{ fontSize: "13px", fontWeight: 700, marginTop: "2px", color: "var(--text-primary)" }}>
                  {inv.ai_attempts ?? 1}
                </div>
              </div>
            </div>

            {/* Escalation history timeline */}
            {Array.isArray(inv.escalation_history) && inv.escalation_history.length > 0 && (
              <div style={{ borderTop: "1px dashed var(--border-color)", paddingTop: "var(--spacing-sm)" }}>
                <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "6px", fontWeight: 700 }}>Escalation Path Timeline</div>
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  {inv.escalation_history.map((step, idx) => (
                    <div key={idx} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "11px", background: "var(--bg-surface)", padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
                      <span style={{ fontWeight: 700, fontFamily: "var(--font-mono)" }}>{String(step.level)}</span>
                      <span style={{ color: "var(--text-secondary)" }}>{String(step.records_analyzed ?? 0)} records</span>
                      <span style={{ color: "var(--info-text)", fontWeight: 600 }}>Conf: {fmtPct(Number(step.effective_confidence ?? step.ai_confidence))}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* ── AI Assessment ─────────────────────────────────────────────── */}
          <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
            <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
              AI Assessment
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--spacing-md)" }}>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>AI Classification</div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: "12px", marginTop: "2px", color: "var(--warning-text)" }}>
                  {inv.ai_classification || "—"}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Classification Match</div>
                <div style={{ marginTop: "2px" }}>
                  <span className={`badge ${inv.ai_classification_matches_deterministic ? "resolved" : "severity-high"}`}>
                    {inv.ai_classification_matches_deterministic ? "MATCHES" : "DISAGREES"}
                  </span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Raw AI Confidence</div>
                <div className="font-mono" style={{ fontSize: "13px", fontWeight: 600, marginTop: "2px" }}>
                  {fmtPct(inv.ai_confidence)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                  Effective Confidence <span style={{ color: "var(--info-text)", fontSize: "10px" }}>(safety-controlled)</span>
                </div>
                <div className="font-mono" style={{ fontSize: "15px", fontWeight: 700, marginTop: "2px", color: "var(--info-text)" }}>
                  {fmtPct(inv.effective_confidence ?? inv.confidence)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Confidence Level</div>
                <div style={{ fontSize: "13px", fontWeight: 600, marginTop: "2px" }}>{inv.confidence_level}</div>
              </div>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Human Review Required</div>
                <div style={{ marginTop: "2px" }}>
                  <span className={`badge ${inv.requires_human_review ? "detected" : "resolved"}`}>
                    {inv.requires_human_review ? "YES" : "NO"}
                  </span>
                </div>
              </div>
            </div>
          </section>

          {/* ── Safety Flags ──────────────────────────────────────────────── */}
          <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
            <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
              Safety Checks
            </h4>
            {flags.length === 0 ? (
              <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                No safety flags detected.
              </div>
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

          {/* ── Evidence Facts ────────────────────────────────────────────── */}
          {facts.length > 0 && (
            <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
              <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
                Evidence Facts
              </h4>
              <ul style={{ margin: 0, paddingLeft: "1.2em", display: "flex", flexDirection: "column", gap: "4px" }}>
                {facts.map((f, i) => (
                  <li key={i} style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: "1.5" }}>{f}</li>
                ))}
              </ul>
            </section>
          )}

          {/* ── AI Hypotheses ─────────────────────────────────────────────── */}
          {causes.length > 0 && (
            <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
              <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--warning-text)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
                AI Hypotheses <span style={{ fontSize: "10px", color: "var(--text-secondary)", textTransform: "none" }}>(unconfirmed — requires human verification)</span>
              </h4>
              <ul style={{ margin: 0, paddingLeft: "1.2em", display: "flex", flexDirection: "column", gap: "4px" }}>
                {causes.map((c, i) => (
                  <li key={i} style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: "1.5" }}>{c}</li>
                ))}
              </ul>
            </section>
          )}

          {/* ── Evidence Gaps ─────────────────────────────────────────────── */}
          {gaps.length > 0 && (
            <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
              <div style={{
                background: "var(--warning-bg)", border: "1px solid var(--warning-border)",
                borderRadius: "8px", padding: "var(--spacing-md)",
              }}>
                <div style={{ fontWeight: 700, color: "var(--warning-text)", fontSize: "12px", marginBottom: "8px" }}>
                  Additional evidence required
                </div>
                <ul style={{ margin: 0, paddingLeft: "1.2em", display: "flex", flexDirection: "column", gap: "4px" }}>
                  {gaps.map((g, i) => (
                    <li key={i} style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: "1.5" }}>{g}</li>
                  ))}
                </ul>
              </div>
            </section>
          )}

          {/* ── Recommended Action ────────────────────────────────────────── */}
          <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
            <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
              Recommended Action
            </h4>
            <div style={{
              background: "var(--bg-primary)", borderLeft: "4px solid var(--accent-primary)",
              borderRadius: "6px", padding: "10px 14px", fontSize: "13px",
              color: "var(--text-primary)", lineHeight: "1.5",
            }}>
              {inv.recommended_action}
            </div>
          </section>

          {/* Safety notice */}
          <div style={{
            background: "var(--bg-primary)", borderRadius: "8px", padding: "var(--spacing-md)",
            fontSize: "11.5px", color: "var(--text-secondary)", lineHeight: "1.6", border: "1px solid var(--border-subtle)",
          }}>
            AI recommendations are advisory. Deterministic reconciliation remains authoritative.
            Financial records are immutable during investigation and resolution.
          </div>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Page Component
// ─────────────────────────────────────────────────────────────────────────────

interface AIInvestigationsProps {
  onNavigateToTab?: (tab: string) => void;
}

export const AIInvestigations: React.FC<AIInvestigationsProps> = ({ onNavigateToTab }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [investigations, setInvestigations] = useState<AIInvestigationResponse[]>([]);
  const [resolutionSummary, setResolutionSummary] = useState<ResolutionSummaryResponse | null>(null);
  const [selected, setSelected] = useState<AIInvestigationResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [invRes, sumRes] = await Promise.all([
        api.getAIInvestigations(),
        api.getResolutionSummary(),
      ]);
      if (invRes.success) setInvestigations(invRes.data);
      if (sumRes.success) setResolutionSummary(sumRes.data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load AI investigations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return (
    <div className="loading-indicator">
      <div className="status-dot connected" style={{ width: 16, height: 16 }} />
      <span>Loading AI investigation records...</span>
    </div>
  );

  if (error) return (
    <div className="error-indicator">
      <h3>Unable to load AI investigations</h3>
      <p>{error}</p>
      <button className="btn-retry" onClick={load}>Retry</button>
    </div>
  );

  const total = investigations.length;
  const autoResolved = investigations.filter(i => i.investigation_status === "AUTO_RESOLVED").length;
  const reviewRecommended = investigations.filter(i => i.investigation_status === "REVIEW_RECOMMENDED").length;
  const humanRequired = investigations.filter(i => i.investigation_status === "HUMAN_REVIEW_REQUIRED").length;
  const aiFailed = investigations.filter(i => i.investigation_status === "AI_FAILED").length;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Why did this difference happen?</h1>
        <p className="page-subtitle">
          AI reviews the transaction context and suggests possible reasons. It does not modify financial records or make the final decision.
        </p>
      </div>

      {/* Visual Workflow Ribbon */}
      <WorkflowVisualizer currentStepId="ai-investigation" onStepClick={(id) => onNavigateToTab && onNavigateToTab(id)} />

      {/* Explicit Advisory Notice Banner */}
      <div
        style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-color)",
          borderLeft: "4px solid var(--info)",
          borderRadius: "10px",
          padding: "12px 16px",
          marginBottom: "var(--spacing-lg)",
          fontSize: "13px",
          color: "var(--text-secondary)",
          lineHeight: "1.5",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <strong style={{ color: "var(--text-primary)" }}>Advisory AI System:</strong> AI investigates the transaction evidence and generates root-cause hypotheses. Deterministic reconciliation rules remain authoritative, and risky cases route to a human operator for final decision.
      </div>

      {/* Empty State */}
      {investigations.length === 0 ? (
        <EmptyState
          title="No AI investigations yet"
          description="Run AI Investigation on detected exceptions to understand their likely causes."
          actionText="INVESTIGATE EXCEPTIONS"
          onAction={() => onNavigateToTab && onNavigateToTab("exceptions")}
        />
      ) : (
        <>
          {/* KPI Cards */}
          <section className="dashboard-section">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "var(--spacing-md)" }}>
              {[
                { label: "Total Investigations", val: total, color: undefined },
                { label: "Auto Resolved", val: resolutionSummary?.auto_resolved ?? autoResolved, color: "var(--success-text)" },
                { label: "Review Recommended", val: resolutionSummary?.review_recommended ?? reviewRecommended, color: "var(--info-text)" },
                { label: "Human Review Required", val: resolutionSummary?.human_review_required ?? humanRequired, color: "var(--warning-text)" },
                { label: "Routing to Human Review", val: resolutionSummary?.ai_failed ?? aiFailed, color: "var(--danger-text)" },
              ].map(({ label, val, color }) => (
                <div key={label} className="card" style={{ padding: "var(--spacing-md)" }}>
                  <span className="kpi-card-header" style={{ fontSize: "10.5px" }}>{label}</span>
                  <span className="kpi-card-value font-mono" style={{ fontSize: "22px", color: color ?? "var(--text-primary)" }}>{val}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Progressive Evidence Escalation Architecture Component */}
          <section className="dashboard-section">
            <div
              style={{
                backgroundColor: "var(--bg-surface)",
                border: "1px solid var(--border-color)",
                borderRadius: "10px",
                padding: "var(--spacing-lg)",
                marginBottom: "var(--spacing-lg)",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <div style={{ fontSize: "11px", fontWeight: 800, color: "var(--info-text)", textTransform: "uppercase", letterSpacing: "0.8px", marginBottom: "12px" }}>
                PROGRESSIVE EVIDENCE ESCALATION PIPELINE
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr auto 1fr auto 1fr", gap: "10px", alignItems: "center", textAlign: "center" }}>
                <div style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border-color)", padding: "12px", borderRadius: "8px" }}>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--info-text)" }}>LEVEL 1</div>
                  <div style={{ fontSize: "12px", fontWeight: 600, marginTop: "4px" }}>Core 3 Ledgers</div>
                  <div style={{ fontSize: "10.5px", color: "var(--text-secondary)", marginTop: "2px" }}>Orders ↔ Payments ↔ Settlements</div>
                </div>
                <span style={{ color: "var(--text-secondary)", fontSize: "16px" }}>&rarr;</span>
                <div style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border-color)", padding: "12px", borderRadius: "8px" }}>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--warning-text)" }}>LEVEL 2</div>
                  <div style={{ fontSize: "12px", fontWeight: 600, marginTop: "4px" }}>Extended Evidence</div>
                  <div style={{ fontSize: "10.5px", color: "var(--text-secondary)", marginTop: "2px" }}>Gateway Fees & Timing Logs</div>
                </div>
                <span style={{ color: "var(--text-secondary)", fontSize: "16px" }}>&rarr;</span>
                <div style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border-color)", padding: "12px", borderRadius: "8px" }}>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--danger-text)" }}>LEVEL 3</div>
                  <div style={{ fontSize: "12px", fontWeight: 600, marginTop: "4px" }}>Full Context</div>
                  <div style={{ fontSize: "10.5px", color: "var(--text-secondary)", marginTop: "2px" }}>Refunds & Bank Discrepancies</div>
                </div>
                <span style={{ color: "var(--text-secondary)", fontSize: "16px" }}>&rarr;</span>
                <div style={{ backgroundColor: "var(--warning-bg)", border: "1px solid var(--warning-border)", padding: "12px", borderRadius: "8px" }}>
                  <div style={{ fontSize: "11px", fontWeight: 800, color: "var(--warning-text)" }}>HUMAN REVIEW</div>
                  <div style={{ fontSize: "12px", fontWeight: 700, marginTop: "4px", color: "var(--warning-text)" }}>Operator Decision</div>
                  <div style={{ fontSize: "10.5px", color: "var(--text-secondary)", marginTop: "2px" }}>Safety-Gated Action</div>
                </div>
              </div>
            </div>
          </section>

          {/* Table */}
          <section className="dashboard-section">
            <h2 className="section-title">Investigation Registry</h2>
            <div className="table-container">
              {investigations.length === 0 ? (
                <div className="empty-state">No AI investigations available.</div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Investigation ID</th>
                      <th>Order ID</th>
                      <th>Exception Type</th>
                      <th>Evidence Level</th>
                      <th>Records</th>
                      <th>Raw Conf</th>
                      <th>Effective Conf</th>
                      <th>Status</th>
                      <th>Human Review</th>
                      <th>Created</th>
                      <th style={{ textAlign: "right" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {investigations.map((inv) => (
                      <tr key={inv.investigation_id}>
                        <td className="font-mono" style={{ fontSize: "11.5px" }}>
                          {inv.investigation_id}
                        </td>
                        <td className="font-mono" style={{ fontWeight: 600 }}>{inv.order_id}</td>
                        <td style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>{inv.exception_type}</td>
                        <td>
                          <span className="badge" style={{
                            fontSize: "10px",
                            background: (inv.evidence_level === "LEVEL 3") ? "rgba(239, 68, 68, 0.2)" : (inv.evidence_level === "LEVEL 2") ? "rgba(245, 158, 11, 0.2)" : "rgba(59, 130, 246, 0.2)",
                            color: (inv.evidence_level === "LEVEL 3") ? "var(--danger-text)" : (inv.evidence_level === "LEVEL 2") ? "var(--warning-text)" : "var(--info-text)",
                            border: "1px solid currentColor",
                          }}>
                            {inv.evidence_level || "LEVEL 1"}
                          </span>
                        </td>
                        <td className="font-mono" style={{ fontSize: "12px" }}>
                          {inv.evidence_records_count ?? 3} recs
                        </td>
                        <td className="font-mono" style={{ fontSize: "12px" }}>{fmtPct(inv.ai_confidence)}</td>
                        <td className="font-mono" style={{ fontSize: "12px", fontWeight: 700, color: "var(--info-text)" }}>
                          {fmtPct(inv.effective_confidence ?? inv.confidence)}
                        </td>
                        <td>
                          <span className={`badge ${statusBadgeClass(inv.investigation_status)}`}>
                            {formatStatusLabel(inv.investigation_status)}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${inv.requires_human_review ? "detected" : "resolved"}`}>
                            {inv.requires_human_review ? "REQUIRED" : "AUTO"}
                          </span>
                        </td>
                        <td style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{fmtTime(inv.created_at)}</td>
                        <td style={{ textAlign: "right" }}>
                          <button className="btn-action" onClick={() => setSelected(inv)}>View</button>
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

      {selected && <DetailPanel inv={selected} onClose={() => setSelected(null)} />}
    </div>
  );
};
