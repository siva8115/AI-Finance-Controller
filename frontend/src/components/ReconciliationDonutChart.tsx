import React, { useState } from "react";

interface DonutSegment {
  label: string;
  count: number;
  color: string;
  bgToken: string;
}

interface ReconciliationDonutChartProps {
  matchedCount: number;
  exceptionsCount: number;
  totalRecords: number;
}

export const ReconciliationDonutChart: React.FC<ReconciliationDonutChartProps> = ({
  matchedCount,
  exceptionsCount,
  totalRecords,
}) => {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (totalRecords === 0) return null;

  const matchRate = (matchedCount / totalRecords) * 100;
  const excRate = (exceptionsCount / totalRecords) * 100;

  const segments: DonutSegment[] = [
    { label: "Matched Clean", count: matchedCount, color: "var(--success-text)", bgToken: "var(--success)" },
    { label: "Flagged Exceptions", count: exceptionsCount, color: "var(--danger-text)", bgToken: "var(--danger)" },
  ];

  // SVG Donut Calculations
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const matchStrokeDash = (matchRate / 100) * circumference;
  const excStrokeDash = (excRate / 100) * circumference;

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
          RECONCILIATION MATCH DISTRIBUTION
        </span>
        <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
          {totalRecords.toLocaleString()} Total Records
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-around", flexWrap: "wrap", gap: "var(--spacing-lg)" }}>
        {/* SVG Donut Ring */}
        <div style={{ position: "relative", width: "160px", height: "160px", flexShrink: 0 }}>
          <svg width="160" height="160" viewBox="0 0 160 160" style={{ transform: "rotate(-90deg)" }}>
            {/* Background Circle Track */}
            <circle
              cx="80"
              cy="80"
              r={radius}
              fill="transparent"
              stroke="var(--bg-primary)"
              strokeWidth="16"
            />
            {/* Matched Segment */}
            <circle
              cx="80"
              cy="80"
              r={radius}
              fill="transparent"
              stroke="var(--success)"
              strokeWidth="16"
              strokeDasharray={`${matchStrokeDash} ${circumference}`}
              strokeDashoffset="0"
              style={{
                transition: "stroke-width 0.2s ease, filter 0.2s ease",
                cursor: "pointer",
                filter: hoveredIdx === 0 ? "brightness(1.2)" : "none",
                strokeWidth: hoveredIdx === 0 ? "20" : "16",
              }}
              onMouseEnter={() => setHoveredIdx(0)}
              onMouseLeave={() => setHoveredIdx(null)}
            />
            {/* Exceptions Segment */}
            <circle
              cx="80"
              cy="80"
              r={radius}
              fill="transparent"
              stroke="var(--danger)"
              strokeWidth="16"
              strokeDasharray={`${excStrokeDash} ${circumference}`}
              strokeDashoffset={`-${matchStrokeDash}`}
              style={{
                transition: "stroke-width 0.2s ease, filter 0.2s ease",
                cursor: "pointer",
                filter: hoveredIdx === 1 ? "brightness(1.2)" : "none",
                strokeWidth: hoveredIdx === 1 ? "20" : "16",
              }}
              onMouseEnter={() => setHoveredIdx(1)}
              onMouseLeave={() => setHoveredIdx(null)}
            />
          </svg>

          {/* Center Stat Callout */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              pointerEvents: "none",
            }}
          >
            <span style={{ fontSize: "22px", fontWeight: 800, fontFamily: "var(--font-mono)", color: "var(--info-text)" }}>
              {matchRate.toFixed(1)}%
            </span>
            <span style={{ fontSize: "10px", textTransform: "uppercase", color: "var(--text-secondary)", fontWeight: 700 }}>
              MATCH RATE
            </span>
          </div>
        </div>

        {/* Interactive Legend Items */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", minWidth: "180px" }}>
          {segments.map((seg, idx) => {
            const pct = totalRecords > 0 ? ((seg.count / totalRecords) * 100).toFixed(1) : "0.0";
            const isHovered = hoveredIdx === idx;
            return (
              <div
                key={seg.label}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  borderRadius: "8px",
                  backgroundColor: isHovered ? "var(--bg-surface-hover)" : "var(--bg-primary)",
                  border: isHovered ? `1px solid ${seg.color}` : "1px solid var(--border-subtle)",
                  transition: "all 0.18s ease",
                  cursor: "pointer",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div
                    style={{
                      width: "10px",
                      height: "10px",
                      borderRadius: "3px",
                      backgroundColor: seg.bgToken,
                    }}
                  />
                  <span style={{ fontSize: "12.5px", fontWeight: 600, color: "var(--text-primary)" }}>
                    {seg.label}
                  </span>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "13px", fontWeight: 800, fontFamily: "var(--font-mono)", color: seg.color }}>
                    {seg.count.toLocaleString()}
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>{pct}%</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
