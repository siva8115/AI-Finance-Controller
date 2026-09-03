import React, { useState } from "react";
import { HowItWorksModal } from "../components/HowItWorksModal";

interface DashboardLayoutProps {
  children: React.ReactNode;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isConnected: boolean | null;
  onRetryConnection: () => void;
  datasetSource?: string;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({
  children,
  activeTab,
  setActiveTab,
  isConnected,
  onRetryConnection,
  datasetSource,
}) => {
  const [isHowItWorksOpen, setIsHowItWorksOpen] = useState(false);

  const menuItems = [
    { id: "data-import", label: "1. Data Import", icon: "📥" },
    { id: "dashboard", label: "2. Dashboard", icon: "📊" },
    { id: "reconciliation", label: "3. Reconciliation", icon: "⚖️" },
    { id: "exceptions", label: "4. Exceptions", icon: "⚠️" },
    { id: "ai-investigations", label: "5. AI Investigation", icon: "🤖" },
    { id: "review-queue", label: "6. Human Review", icon: "👤" },
    { id: "audit-trail", label: "7. Audit Trail", icon: "📜" },
  ];

  return (
    <div className="app-container">
      {/* Top Header Bar */}
      <header className="top-bar">
        <div className="top-bar-title">
          <span style={{ letterSpacing: "0.8px", color: "var(--text-primary)" }}>
            AI FINANCE CONTROLLER
          </span>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 400 }}>
            | Autonomous Finance Operations & 3-Way Reconciliation
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--spacing-md)" }}>
          {/* How It Works Guide Button */}
          <button
            onClick={() => setIsHowItWorksOpen(true)}
            className="btn-action"
            style={{
              fontSize: "12px",
              padding: "5px 12px",
              borderRadius: "6px",
              backgroundColor: "var(--bg-primary)",
              border: "1px solid var(--border-color)",
            }}
          >
            <span>💡</span>
            <span>How It Works</span>
          </button>

          {/* Dataset source pill */}
          <span
            style={{
              fontSize: "11px",
              padding: "4px 10px",
              borderRadius: "20px",
              backgroundColor:
                datasetSource === "UPLOADED"
                  ? "var(--info-bg)"
                  : datasetSource === "DEMO"
                  ? "var(--warning-bg)"
                  : "var(--bg-primary)",
              color:
                datasetSource === "UPLOADED"
                  ? "var(--info-text)"
                  : datasetSource === "DEMO"
                  ? "var(--warning-text)"
                  : "var(--text-secondary)",
              fontWeight: 700,
              letterSpacing: "0.5px",
              border: "1px solid",
              borderColor:
                datasetSource === "UPLOADED"
                  ? "var(--info-border)"
                  : datasetSource === "DEMO"
                  ? "var(--warning-border)"
                  : "var(--border-color)",
            }}
          >
            {datasetSource === "UPLOADED"
              ? "UPLOADED DATA"
              : datasetSource === "DEMO"
              ? "DEMO DATA"
              : "NO DATA"}
          </span>

          {/* Connection Status */}
          <div className="system-status">
            <span
              className={`status-dot ${
                isConnected === true ? "connected" : "disconnected"
              }`}
            ></span>
            <span style={{ letterSpacing: "0.2px" }}>
              {isConnected === true
                ? "Backend Connected"
                : isConnected === false
                ? "Connection Unavailable"
                : "Checking System..."}
            </span>
            {isConnected === false && (
              <button
                onClick={onRetryConnection}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--accent-primary-hover)",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                  padding: "0 4px",
                  textDecoration: "underline",
                }}
              >
                Retry
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Layout Area */}
      <div className="main-layout">
        {/* Left Navigation Sidebar */}
        <aside className="sidebar">
          <div
            style={{
              padding: "var(--spacing-xs) var(--spacing-md) var(--spacing-md)",
              fontSize: "10.5px",
              textTransform: "uppercase",
              letterSpacing: "1px",
              color: "var(--text-muted)",
              fontWeight: 700,
            }}
          >
            Operations Workflow
          </div>
          <nav className="sidebar-menu">
            {menuItems.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`sidebar-item ${isActive ? "active" : ""}`}
                  style={{
                    textAlign: "left",
                    width: "100%",
                  }}
                >
                  <span style={{ fontSize: "14px", width: "18px" }}>{item.icon}</span>
                  <span style={{ fontSize: "13px" }}>{item.label}</span>
                </button>
              );
            })}
          </nav>

          <div
            style={{
              marginTop: "auto",
              padding: "var(--spacing-md)",
              borderTop: "1px solid var(--border-color)",
              fontSize: "11.5px",
              color: "var(--text-secondary)",
              lineHeight: "1.6",
              backgroundColor: "hsla(224, 28%, 12%, 0.4)",
            }}
          >
            <div><strong>Rule-based</strong> Reconciliation</div>
            <div><strong>Advisory</strong> AI Investigation</div>
            <div><strong>Immutable</strong> Audit Records</div>
          </div>
        </aside>

        {/* Dynamic Page Content Area */}
        <main className="content-area">{children}</main>
      </div>

      {/* How It Works Guide Modal */}
      <HowItWorksModal isOpen={isHowItWorksOpen} onClose={() => setIsHowItWorksOpen(false)} />
    </div>
  );
};
