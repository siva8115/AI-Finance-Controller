import React, { useState } from "react";

interface CategoryData {
  type: string;
  count: number;
  impact: number;
}

interface DiscrepancyBarChartProps {
  categoryMap: Record<string, { count: number; impact: number }>;
}

export const DiscrepancyBarChart: React.FC<DiscrepancyBarChartProps> = ({ categoryMap }) => {
  const [hoveredType, setHoveredType] = useState<string | null>(null);

  const categories: CategoryData[] = Object.entries(categoryMap).map(([type, d]) => ({
    type,
    count: d.count,
    impact: d.impact,
  })).sort((a, b) => b.impact - a.impact);

  if (categories.length === 0) return null;

  const maxImpact = Math.max(...categories.map((c) => c.impact), 1);

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
          FINANCIAL IMPACT BY EXCEPTION CATEGORY
        </span>
        <span style={{ fontSize: "11.5px", color: "var(--danger-text)", fontWeight: 700 }}>
          Discrepancy Amount (₹)
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {categories.map((cat) => {
          const pct = Math.max(8, (cat.impact / maxImpact) * 100);
          const isHovered = hoveredType === cat.type;

          return (
            <div
              key={cat.type}
              onMouseEnter={() => setHoveredType(cat.type)}
              onMouseLeave={() => setHoveredType(null)}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "4px",
                padding: "6px 8px",
                borderRadius: "6px",
                backgroundColor: isHovered ? "var(--bg-surface-hover)" : "transparent",
                transition: "background 0.15s ease",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
                <span style={{ fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                  {cat.type.replace("_", " ")}
                </span>
                <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                  <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>{cat.count} cases</span>
                  <span style={{ fontWeight: 800, fontFamily: "var(--font-mono)", color: "var(--danger-text)" }}>
                    ₹{cat.impact.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>

              {/* Progress Track */}
              <div
                style={{
                  height: "10px",
                  backgroundColor: "var(--bg-primary)",
                  borderRadius: "5px",
                  overflow: "hidden",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${pct}%`,
                    backgroundColor: "var(--danger)",
                    borderRadius: "5px",
                    transition: "width 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
                    filter: isHovered ? "brightness(1.2)" : "none",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
