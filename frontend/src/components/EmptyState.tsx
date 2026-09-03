import React from "react";

interface EmptyStateProps {
  title?: string;
  description?: string;
  actionText?: string;
  onAction?: () => void;
  icon?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = "No finance data has been imported yet.",
  description = "Upload Orders, Payments and Settlements data to begin automated 3-way reconciliation.",
  actionText = "Import Finance Data",
  onAction,
  icon = "📊",
}) => {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--spacing-xl) var(--spacing-lg)",
        backgroundColor: "var(--bg-surface)",
        border: "1px dashed var(--border-color)",
        borderRadius: "8px",
        textAlign: "center",
        margin: "var(--spacing-lg) 0",
      }}
    >
      <div style={{ fontSize: "36px", marginBottom: "var(--spacing-md)" }}>{icon}</div>
      <h3 style={{ margin: "0 0 var(--spacing-xs)", color: "var(--text-primary)", fontSize: "16px", fontWeight: 600 }}>
        {title}
      </h3>
      <p
        style={{
          margin: "0 0 var(--spacing-lg)",
          color: "var(--text-secondary)",
          fontSize: "13px",
          maxWidth: "460px",
          lineHeight: "1.5",
        }}
      >
        {description}
      </p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="btn-action"
          style={{
            background: "var(--accent-primary)",
            borderColor: "var(--accent-primary)",
            color: "#ffffff",
            padding: "8px 18px",
            fontWeight: 600,
            fontSize: "13px",
          }}
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
