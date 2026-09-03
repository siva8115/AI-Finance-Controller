import React from "react";

interface LedgerWaterfallChartProps {
  totalOrders: number;
  totalPayments: number;
  totalSettlements: number;
}

export const LedgerWaterfallChart: React.FC<LedgerWaterfallChartProps> = ({
  totalOrders,
  totalPayments,
  totalSettlements,
}) => {
  const maxVal = Math.max(totalOrders, totalPayments, totalSettlements, 1);

  const bars = [
    { label: "1. Orders Expected", count: totalOrders, color: "var(--accent-primary)", heightPct: (totalOrders / maxVal) * 100 },
    { label: "2. Payments Collected", count: totalPayments, color: "var(--info)", heightPct: (totalPayments / maxVal) * 100 },
    { label: "3. Settlements Payout", count: totalSettlements, color: "var(--success)", heightPct: (totalSettlements / maxVal) * 100 },
  ];

  return (
    <div
      style={{
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border-color)",
        borderRadius: "10px",
        padding: "var(--spacing-lg)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--spacing-md)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span
          style={{
            fontSize: "11px",
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: "0.8px",
            color: "var(--text-secondary)",
          }}
        >
          3-WAY LEDGER RECORD COMPARISON
        </span>
        <span style={{ fontSize: "11.5px", color: "var(--text-secondary)" }}>
          Orders vs Gateway vs Bank
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "var(--spacing-md)",
          alignItems: "end",
          height: "140px",
          backgroundColor: "var(--bg-primary)",
          borderRadius: "8px",
          padding: "var(--spacing-md) var(--spacing-lg)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        {bars.map((b) => (
          <div
            key={b.label}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              height: "100%",
              justifyContent: "flex-end",
              gap: "6px",
            }}
          >
            <span style={{ fontSize: "13px", fontWeight: 800, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
              {b.count.toLocaleString()}
            </span>
            <div
              style={{
                width: "100%",
                maxWidth: "60px",
                height: `${Math.max(12, b.heightPct)}%`,
                backgroundColor: b.color,
                borderRadius: "4px 4px 0 0",
                transition: "height 0.4s ease",
              }}
            />
            <span style={{ fontSize: "10.5px", fontWeight: 700, color: "var(--text-secondary)", textAlign: "center" }}>
              {b.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
