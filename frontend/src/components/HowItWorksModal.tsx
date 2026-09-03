import React from "react";

interface HowItWorksModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const HowItWorksModal: React.FC<HowItWorksModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const steps = [
    {
      num: 1,
      title: "Import Data",
      desc: "Provide three standard financial datasets: Orders (internal sales), Payments (gateway transactions), and Settlements (bank payouts).",
      rule: "Supports custom CSV uploads and realistic test datasets.",
    },
    {
      num: 2,
      title: "Validate Records",
      desc: "The system inspects required schemas, data types, date formats, duplicate IDs, and cross-source foreign key linkages before processing.",
      rule: "Blocks reconciliation if mandatory structural columns are missing.",
    },
    {
      num: 3,
      title: "Reconcile Transactions",
      desc: "A deterministic 3-way reconciliation engine compares Order amount, Gateway payment, and Bank settlement to ensure full financial ledger balance.",
      rule: "Authoritative and mathematically exact. 100% reproducible.",
    },
    {
      num: 4,
      title: "Detect Exceptions",
      desc: "Automatically isolates discrepancies: missing payments, missing settlements, fee discrepancies, amount mismatches, duplicate charges, timing delays, and unaccounted refunds.",
      rule: "Calculates exact monetary difference and assigns severity (HIGH, MEDIUM, LOW).",
    },
    {
      num: 5,
      title: "Investigate with AI",
      desc: "Gemini AI analyzes the raw evidence across all 3 ledgers, produces a root-cause explanation narrative, and suggests next operational steps.",
      rule: "AI is strictly ADVISORY. AI never modifies financial records or overrides reconciliation.",
    },
    {
      num: 6,
      title: "Review Risky Cases",
      desc: "Exceptions that trigger safety flags (confidence < 85%, high monetary value, mismatching classifications) are routed to the Human Review Queue.",
      rule: "Human finance operators approve, reject, or reopen resolution proposals.",
    },
    {
      num: 7,
      title: "Record Audit Trail",
      desc: "Every automated AI suggestion and human reviewer action is recorded into a permanent, immutable event log for internal audit and regulatory compliance.",
      rule: "Financial transaction records remain strictly immutable.",
    },
  ];

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 300,
        padding: "var(--spacing-md)",
      }}
    >
      <div
        className="card"
        style={{
          width: "720px",
          maxWidth: "100%",
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-color)",
          boxShadow: "var(--shadow-lg)",
          maxHeight: "90vh",
          overflowY: "auto",
          padding: "var(--spacing-xl)",
          borderRadius: "12px",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            borderBottom: "1px solid var(--border-color)",
            paddingBottom: "var(--spacing-md)",
            marginBottom: "var(--spacing-lg)",
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 700, color: "var(--text-primary)" }}>
              How AI Finance Controller Works
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--text-secondary)" }}>
              Understanding 3-way reconciliation, advisory AI investigations, and human safety controls
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-secondary)",
              fontSize: "22px",
              cursor: "pointer",
              lineHeight: 1,
            }}
          >
            &times;
          </button>
        </div>

        {/* Financial Flow Example */}
        <div
          style={{
            backgroundColor: "var(--bg-primary)",
            border: "1px solid var(--border-color)",
            borderRadius: "8px",
            padding: "var(--spacing-md)",
            marginBottom: "var(--spacing-lg)",
          }}
        >
          <div style={{ fontSize: "11px", fontWeight: 800, color: "var(--accent-primary-hover)", letterSpacing: "0.5px", marginBottom: "8px" }}>
            THE 3-WAY MATCH PRINCIPLE
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr auto 1fr auto 1fr auto 1fr",
              alignItems: "center",
              gap: "8px",
              textAlign: "center",
              fontSize: "12px",
            }}
          >
            <div style={{ background: "var(--bg-surface)", padding: "8px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ color: "var(--text-secondary)", fontSize: "11px" }}>Order</div>
              <strong style={{ fontSize: "14px", fontFamily: "var(--font-mono)" }}>$10,000</strong>
            </div>
            <span style={{ color: "var(--text-secondary)" }}>&rarr;</span>
            <div style={{ background: "var(--bg-surface)", padding: "8px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ color: "var(--text-secondary)", fontSize: "11px" }}>Gateway Payment</div>
              <strong style={{ fontSize: "14px", fontFamily: "var(--font-mono)" }}>$10,000</strong>
            </div>
            <span style={{ color: "var(--text-secondary)" }}>&rarr;</span>
            <div style={{ background: "var(--bg-surface)", padding: "8px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ color: "var(--text-secondary)", fontSize: "11px" }}>Bank Settlement</div>
              <strong style={{ fontSize: "14px", fontFamily: "var(--font-mono)", color: "var(--warning-text)" }}>$9,700</strong>
            </div>
            <span style={{ color: "var(--text-secondary)" }}>&rarr;</span>
            <div style={{ background: "var(--danger-bg)", border: "1px solid var(--danger-border)", padding: "8px", borderRadius: "6px" }}>
              <div style={{ color: "var(--danger-text)", fontSize: "11px" }}>Discrepancy</div>
              <strong style={{ fontSize: "13px", fontFamily: "var(--font-mono)", color: "var(--danger-text)" }}>$300 Mismatch</strong>
            </div>
          </div>
        </div>

        {/* 7 Process Steps */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-sm)", marginBottom: "var(--spacing-lg)" }}>
          {steps.map((s) => (
            <div
              key={s.num}
              style={{
                display: "flex",
                gap: "var(--spacing-md)",
                alignItems: "flex-start",
                padding: "12px",
                backgroundColor: "var(--bg-primary)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "8px",
              }}
            >
              <div
                style={{
                  width: "24px",
                  height: "24px",
                  borderRadius: "50%",
                  backgroundColor: "var(--accent-primary)",
                  color: "#ffffff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 800,
                  fontSize: "11px",
                  flexShrink: 0,
                }}
              >
                {s.num}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-primary)" }}>{s.title}</div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px", lineHeight: "1.5" }}>
                  {s.desc}
                </div>
                <div style={{ fontSize: "11px", color: "var(--info-text)", marginTop: "4px", fontWeight: 500 }}>
                  &bull; {s.rule}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Safety Invariant Notice */}
        <div
          style={{
            backgroundColor: "var(--bg-secondary)",
            borderLeft: "4px solid var(--accent-primary)",
            padding: "12px 14px",
            borderRadius: "6px",
            fontSize: "12px",
            color: "var(--text-secondary)",
            lineHeight: "1.5",
          }}
        >
          <strong style={{ color: "var(--text-primary)" }}>Core Safety Invariant:</strong> Deterministic
          reconciliation is authoritative. Gemini AI provides advisory explanations only. Operational financial records
          remain strictly immutable.
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "var(--spacing-lg)" }}>
          <button
            onClick={onClose}
            className="btn-action"
            style={{
              background: "var(--accent-primary)",
              borderColor: "var(--accent-primary-hover)",
              color: "#ffffff",
              padding: "8px 20px",
              fontWeight: 700,
            }}
          >
            Got It
          </button>
        </div>
      </div>
    </div>
  );
};
