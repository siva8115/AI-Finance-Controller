import React, { useState } from "react";

export interface WorkflowStep {
  id: string;
  name: string;
  shortDesc: string;
  fullDesc: string;
}

const STEPS: WorkflowStep[] = [
  {
    id: "data-import",
    name: "DATA",
    shortDesc: "Orders, Payments, Settlements",
    fullDesc: "Upload customer orders, payment gateway transactions, and bank settlements.",
  },
  {
    id: "reconciliation",
    name: "RECONCILE",
    shortDesc: "3-Way Match Check",
    fullDesc: "Deterministic rule-based engine compares Order ↔ Payment ↔ Settlement.",
  },
  {
    id: "exceptions",
    name: "EXCEPTIONS",
    shortDesc: "Flagged Discrepancies",
    fullDesc: "Identifies missing payments, missing settlements, fee differences, and amount mismatches.",
  },
  {
    id: "ai-investigation",
    name: "INVESTIGATE",
    shortDesc: "Advisory AI Root Cause",
    fullDesc: "AI analyzes transaction context to suggest likely causes without modifying financial amounts.",
  },
  {
    id: "review-queue",
    name: "REVIEW",
    shortDesc: "Human Operator Decision",
    fullDesc: "Finance operators approve, reject, or request review for high-risk discrepancies.",
  },
  {
    id: "audit-trail",
    name: "AUDIT",
    shortDesc: "Immutable Log",
    fullDesc: "Tamper-evident record of all automated and manual resolution events.",
  },
];

interface WorkflowVisualizerProps {
  currentStepId?: string;
  onStepClick?: (stepId: string) => void;
}

export const WorkflowVisualizer: React.FC<WorkflowVisualizerProps> = ({
  currentStepId = "data-import",
  onStepClick,
}) => {
  const [hoveredStep, setHoveredStep] = useState<WorkflowStep | null>(null);

  const currentIdx = STEPS.findIndex((s) => s.id === currentStepId);

  return (
    <div
      style={{
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border-color)",
        borderRadius: "10px",
        padding: "var(--spacing-md) var(--spacing-lg)",
        marginBottom: "var(--spacing-lg)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "var(--spacing-sm)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              fontSize: "11px",
              textTransform: "uppercase",
              letterSpacing: "0.8px",
              color: "var(--accent-primary-hover)",
              fontWeight: 800,
            }}
          >
            Finance Operations Lifecycle
          </span>
        </div>
        <span style={{ fontSize: "11.5px", color: "var(--text-secondary)" }}>
          {hoveredStep ? hoveredStep.fullDesc : "Click any stage to navigate to that operational step"}
        </span>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          overflowX: "auto",
          paddingBottom: "4px",
        }}
      >
        {STEPS.map((step, idx) => {
          const isCurrent = step.id === currentStepId;
          const isCompleted = idx < (currentIdx >= 0 ? currentIdx : 0);
          const isHovered = hoveredStep?.id === step.id;

          const statusIcon = isCompleted ? "✓" : isCurrent ? "●" : "○";
          const statusText = isCompleted ? "Completed" : isCurrent ? "Current" : "Not started";

          return (
            <React.Fragment key={step.id}>
              {idx > 0 && (
                <div
                  style={{
                    height: "2px",
                    width: "20px",
                    backgroundColor: isCompleted
                      ? "var(--success)"
                      : isCurrent
                      ? "var(--accent-primary)"
                      : "var(--border-color)",
                    transition: "all 0.3s ease",
                    flexShrink: 0,
                  }}
                />
              )}

              <button
                onClick={() => onStepClick && onStepClick(step.id)}
                onMouseEnter={() => setHoveredStep(step)}
                onMouseLeave={() => setHoveredStep(null)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  padding: "8px 12px",
                  borderRadius: "8px",
                  border: isCurrent
                    ? "1px solid var(--accent-primary)"
                    : isHovered
                    ? "1px solid var(--border-color-hover)"
                    : "1px solid var(--border-subtle)",
                  backgroundColor: isCurrent
                    ? "var(--bg-primary)"
                    : isHovered
                    ? "var(--bg-surface-hover)"
                    : "var(--bg-surface)",
                  cursor: "pointer",
                  flexShrink: 0,
                  transition: "all 0.18s ease",
                  textAlign: "left",
                  boxShadow: isCurrent ? "0 0 10px var(--accent-glow)" : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span
                    style={{
                      fontSize: "11px",
                      color: isCompleted
                        ? "var(--success-text)"
                        : isCurrent
                        ? "var(--accent-primary-hover)"
                        : "var(--text-muted)",
                      fontWeight: 800,
                    }}
                  >
                    {statusIcon}
                  </span>
                  <span
                    style={{
                      fontSize: "12px",
                      fontWeight: isCurrent ? 700 : 600,
                      letterSpacing: "0.4px",
                      color: isCurrent ? "var(--text-primary)" : "var(--text-secondary)",
                    }}
                  >
                    {step.name}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: "10px",
                    color: isCompleted
                      ? "var(--success-text)"
                      : isCurrent
                      ? "var(--accent-primary-hover)"
                      : "var(--text-muted)",
                    marginTop: "2px",
                    fontWeight: 500,
                  }}
                >
                  {statusText}
                </span>
              </button>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
