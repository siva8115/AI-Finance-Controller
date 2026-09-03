import React, { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "../services/api";
import type { ResolutionEventResponse } from "../types";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function fmtTime(iso?: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function actorBadge(actor: string): string {
  return actor === "HUMAN" ? "detected" : "resolved";
}

function statusBadgeClass(s?: string): string {
  if (!s) return "detected";
  if (s.includes("AUTO_RESOLVED") || s.includes("APPROVED")) return "resolved";
  if (s.includes("REJECTED") || s.includes("AI_FAILED")) return "severity-high";
  if (s.includes("HUMAN_REVIEW") || s.includes("UNRESOLVED")) return "detected";
  return "detected";
}

function formatStatusLabel(s?: string): string {
  if (!s) return "";
  if (s === "AI_FAILED") return "Routing to Human Review";
  return s;
}

const STATUS_OPTIONS = [
  "ALL",
  "AUTO_RESOLVED",
  "HUMAN_REVIEW_REQUIRED",
  "REVIEW_RECOMMENDED",
  "APPROVED_BY_HUMAN",
  "REJECTED_BY_HUMAN",
  "UNRESOLVED",
  "AI_FAILED",
  "PENDING_INVESTIGATION",
];

// ─────────────────────────────────────────────────────────────────────────────
// Detail Panel Component
// ─────────────────────────────────────────────────────────────────────────────

const DetailPanel: React.FC<{
  event: ResolutionEventResponse;
  onClose: () => void;
}> = ({ event, onClose }) => (
  <div style={{
    position: "fixed", top: 0, left: 0, width: "100%", height: "100%",
    backgroundColor: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)", display: "flex",
    alignItems: "flex-start", justifyContent: "flex-end", zIndex: 200,
  }}>
    <div style={{
      width: "500px", maxWidth: "100vw", height: "100vh", overflowY: "auto",
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
          <div style={{ fontSize: "14px", fontWeight: 700 }}>Audit Event Detail</div>
          <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--text-secondary)", marginTop: "2px" }}>
            {event.event_id}
          </div>
        </div>
        <button onClick={onClose} style={{
          background: "transparent", border: "none",
          color: "var(--text-secondary)", fontSize: "22px", cursor: "pointer",
        }}>&times;</button>
      </div>

      <div style={{ padding: "var(--spacing-lg)", display: "flex", flexDirection: "column", gap: "var(--spacing-lg)" }}>
        {/* Core fields */}
        <section>
          <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
            Event Identifiers
          </h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--spacing-md)", backgroundColor: "var(--bg-primary)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
            {([
              ["Event ID", <span key="ev" className="font-mono">{event.event_id}</span>],
              ["Resolution ID", <span key="res" className="font-mono">{event.resolution_id}</span>],
              ["Actor Type", <span key="act" className={`badge ${actorBadge(event.actor_type)}`}>{event.actor_type}</span>],
              ["Actor ID", <span key="aid" className="font-mono">{event.actor_id || "N/A"}</span>],
              ["Timestamp", fmtTime(event.created_at)],
            ] as [string, React.ReactNode][]).map(([label, val]) => (
              <div key={String(label)}>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>{label}</div>
                <div style={{ fontSize: "13px", fontWeight: 600, marginTop: "2px" }}>{val}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Status transition */}
        <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
          <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
            Status Transition
          </h4>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", backgroundColor: "var(--bg-primary)", padding: "14px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
            <div>
              <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "4px" }}>Previous</div>
              <span className={`badge ${statusBadgeClass(event.previous_status)}`}>
                {event.previous_status ? formatStatusLabel(event.previous_status) : "N/A"}
              </span>
            </div>
            <div style={{ color: "var(--accent-primary-hover)", fontSize: "18px", fontWeight: 700 }}>&rarr;</div>
            <div>
              <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "4px" }}>New Status</div>
              <span className={`badge ${statusBadgeClass(event.new_status)}`}>
                {formatStatusLabel(event.new_status)}
              </span>
            </div>
          </div>
        </section>

        {/* Reason / Notes */}
        <section style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--spacing-lg)" }}>
          <h4 style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.6px", color: "var(--text-secondary)", margin: "0 0 var(--spacing-sm)", fontWeight: 700 }}>
            Reason / Notes
          </h4>
          <div style={{
            background: "var(--bg-primary)", borderLeft: "4px solid var(--accent-primary)",
            borderRadius: "6px", padding: "10px 14px", fontSize: "13px",
            color: "var(--text-primary)", lineHeight: "1.5",
          }}>
            {event.reason || "N/A"}
          </div>
        </section>

        {/* Immutability notice */}
        <div style={{
          background: "var(--bg-primary)", borderRadius: "8px", padding: "var(--spacing-md)",
          fontSize: "11.5px", color: "var(--text-secondary)", lineHeight: "1.6", border: "1px solid var(--border-subtle)",
        }}>
          Audit events are immutable records of system and human actions.
          Financial transaction records are never modified by the resolution workflow.
        </div>
      </div>
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// Page Component
// ─────────────────────────────────────────────────────────────────────────────

import { WorkflowVisualizer } from "../components/WorkflowVisualizer";
import { EmptyState } from "../components/EmptyState";

interface AuditTrailProps {
  onNavigateToTab?: (tab: string) => void;
}

export const AuditTrail: React.FC<AuditTrailProps> = ({ onNavigateToTab }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<ResolutionEventResponse[]>([]);
  const [selected, setSelected] = useState<ResolutionEventResponse | null>(null);

  // Filters (client-side)
  const [actorFilter, setActorFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [search, setSearch] = useState<string>("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getAuditEvents();
      if (res.success) setEvents(res.data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load audit events.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Apply filters client-side
  const filtered = useMemo(() => {
    return events.filter((e) => {
      if (actorFilter !== "ALL" && e.actor_type !== actorFilter) return false;
      if (statusFilter !== "ALL" && e.new_status !== statusFilter) return false;
      if (search.trim()) {
        const q = search.trim().toLowerCase();
        if (
          !e.resolution_id.toLowerCase().includes(q) &&
          !(e.actor_id || "").toLowerCase().includes(q) &&
          !e.new_status.toLowerCase().includes(q)
        ) return false;
      }
      return true;
    });
  }, [events, actorFilter, statusFilter, search]);

  const systemCount = events.filter(e => e.actor_type === "SYSTEM").length;
  const humanCount  = events.filter(e => e.actor_type === "HUMAN").length;

  if (loading) return (
    <div className="loading-indicator">
      <div className="status-dot connected" style={{ width: 16, height: 16 }} />
      <span>Loading audit trail...</span>
    </div>
  );

  if (error) return (
    <div className="error-indicator">
      <h3>Unable to load audit trail</h3>
      <p>{error}</p>
      <button className="btn-retry" onClick={load}>Retry</button>
    </div>
  );

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Audit Trail</h1>
        <p className="page-subtitle">
          Every reconciliation, AI investigation and human decision is recorded for accountability.
        </p>
      </div>

      {/* Visual Workflow Ribbon */}
      <WorkflowVisualizer currentStepId="audit-trail" onStepClick={(id) => onNavigateToTab && onNavigateToTab(id)} />

      {/* Immutability notice banner */}
      <div style={{
        background: "var(--bg-surface)", border: "1px solid var(--border-color)",
        borderLeft: "4px solid var(--accent-primary)", borderRadius: "10px",
        padding: "12px 16px", marginBottom: "var(--spacing-lg)",
        fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5",
        boxShadow: "var(--shadow-sm)",
      }}>
        <strong style={{ color: "var(--text-primary)" }}>Original financial records are immutable.</strong>&ensp;
        Audit events record all automated and operator resolutions without modifying raw transaction ledgers.
      </div>

      {/* KPI Cards */}
      <section className="dashboard-section">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--spacing-lg)" }}>
          {[
            { label: "Total Events", val: events.length, color: undefined },
            { label: "System Events", val: systemCount, color: "var(--info-text)" },
            { label: "Human Events",  val: humanCount,  color: "var(--warning-text)" },
          ].map(({ label, val, color }) => (
            <div key={label} className="card" style={{ padding: "var(--spacing-md)" }}>
              <span className="kpi-card-header" style={{ fontSize: "11px" }}>{label}</span>
              <span className="kpi-card-value font-mono" style={{ fontSize: "24px", color: color ?? "var(--text-primary)" }}>
                {val}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Filters */}
      <section className="dashboard-section">
        <div style={{ display: "flex", gap: "var(--spacing-md)", flexWrap: "wrap", alignItems: "center" }}>
          {/* Search */}
          <input
            id="audit-search"
            type="text"
            placeholder="Search by Resolution ID, Actor ID, or Status…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              flex: "1 1 260px", background: "var(--bg-surface)",
              border: "1px solid var(--border-color)", color: "var(--text-primary)",
              padding: "8px 12px", borderRadius: "6px", fontSize: "13px",
              fontFamily: "var(--font-sans)",
            }}
          />

          {/* Actor filter */}
          <select
            id="audit-actor-filter"
            value={actorFilter}
            onChange={(e) => setActorFilter(e.target.value)}
            style={{
              background: "var(--bg-surface)", border: "1px solid var(--border-color)",
              color: "var(--text-primary)", padding: "8px 12px", borderRadius: "6px",
              fontSize: "13px", cursor: "pointer", fontFamily: "var(--font-sans)",
            }}
          >
            <option value="ALL">All Actors</option>
            <option value="SYSTEM">SYSTEM</option>
            <option value="HUMAN">HUMAN</option>
          </select>

          {/* Status filter */}
          <select
            id="audit-status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              background: "var(--bg-surface)", border: "1px solid var(--border-color)",
              color: "var(--text-primary)", padding: "8px 12px", borderRadius: "6px",
              fontSize: "13px", cursor: "pointer", fontFamily: "var(--font-sans)",
            }}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s === "ALL" ? "All Statuses" : formatStatusLabel(s)}</option>
            ))}
          </select>

          {/* Reload */}
          <button
            className="btn-action"
            onClick={load}
            style={{ whiteSpace: "nowrap" }}
          >
            ↻ Refresh
          </button>

          {/* Result count */}
          <span style={{ fontSize: "12px", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
            {filtered.length} of {events.length} event{events.length !== 1 ? "s" : ""}
          </span>
        </div>
      </section>

      {/* Events Table or Empty State */}
      {events.length === 0 ? (
        <EmptyState
          title="No audit events recorded yet."
          description="Run the reconciliation and resolution workflow to generate audit records. All automated and operator actions are immutably logged here."
          actionText="Go to Reconciliation"
          onAction={() => onNavigateToTab && onNavigateToTab("reconciliation")}
        />
      ) : (
        <section className="dashboard-section">
          <h2 className="section-title">Resolution Event History</h2>
          <div className="table-container">
            {filtered.length === 0 ? (
              <div className="empty-state">No events match the current filters.</div>
            ) : (
              <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event ID</th>
                  <th>Resolution ID</th>
                  <th>Actor</th>
                  <th>Prev. Status</th>
                  <th>New Status</th>
                  <th>Reason / Notes</th>
                  <th style={{ textAlign: "right" }}>Detail</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((evt) => (
                  <tr key={evt.event_id}>
                    <td style={{ fontSize: "11.5px", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                      {fmtTime(evt.created_at)}
                    </td>
                    <td className="font-mono" style={{ fontSize: "11px" }}>
                      {evt.event_id}
                    </td>
                    <td className="font-mono" style={{ fontSize: "11px" }}>
                      {evt.resolution_id}
                    </td>
                    <td>
                      <span className={`badge ${actorBadge(evt.actor_type)}`}>
                        {evt.actor_type}
                      </span>
                    </td>
                    <td>
                      {evt.previous_status
                        ? <span className={`badge ${statusBadgeClass(evt.previous_status)}`} style={{ fontSize: "10px" }}>
                            {formatStatusLabel(evt.previous_status)}
                          </span>
                        : <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>—</span>
                      }
                    </td>
                    <td>
                      <span className={`badge ${statusBadgeClass(evt.new_status)}`} style={{ fontSize: "10px" }}>
                        {formatStatusLabel(evt.new_status)}
                      </span>
                    </td>
                    <td style={{
                      maxWidth: "280px", overflow: "hidden",
                      textOverflow: "ellipsis", whiteSpace: "nowrap",
                      fontSize: "12px", color: "var(--text-secondary)",
                    }}
                      title={evt.reason || ""}
                    >
                      {evt.reason || "—"}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <button className="btn-action" onClick={() => setSelected(evt)}>View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
      )}

      {selected && <DetailPanel event={selected} onClose={() => setSelected(null)} />}
    </div>
  );
};
