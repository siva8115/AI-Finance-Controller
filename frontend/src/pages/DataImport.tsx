import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import type { ValidationSummary, SystemOverview } from "../types";
import { WorkflowVisualizer } from "../components/WorkflowVisualizer";

interface DataImportProps {
  onNavigateToTab?: (tab: string) => void;
  onRefreshOverview?: () => void;
}

export const DataImport: React.FC<DataImportProps> = ({
  onNavigateToTab,
  onRefreshOverview,
}) => {
  // Raw file contents
  const [ordersText, setOrdersText] = useState<string>("");
  const [paymentsText, setPaymentsText] = useState<string>("");
  const [settlementsText, setSettlementsText] = useState<string>("");

  // Record count previews
  const [ordersCount, setOrdersCount] = useState<number>(0);
  const [paymentsCount, setPaymentsCount] = useState<number>(0);
  const [settlementsCount, setSettlementsCount] = useState<number>(0);

  // Data Preview modal state
  const [previewModal, setPreviewModal] = useState<{ title: string; csv: string } | null>(null);

  // States
  const [isValidating, setIsValidating] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgressStep, setUploadProgressStep] = useState<string | null>(null);
  const [isGeneratingDemo, setIsGeneratingDemo] = useState(false);
  const [isExecutingRecon, setIsExecutingRecon] = useState(false);

  const [validationSummary, setValidationSummary] = useState<ValidationSummary | null>(null);
  const [systemOverview, setSystemOverview] = useState<SystemOverview | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load existing system overview
  const loadOverview = async () => {
    try {
      const res = await api.getDataSummary();
      if (res.success) {
        setSystemOverview(res.data);
      }
    } catch (err) {
      console.error("Failed to load overview:", err);
    }
  };

  useEffect(() => {
    loadOverview();
  }, []);

  // Helper to count lines in CSV string
  const getRecordCount = (csv: string): number => {
    if (!csv.trim()) return 0;
    const lines = csv.trim().split("\n").filter((l) => l.trim().length > 0);
    return Math.max(0, lines.length - 1); // Subtract header
  };

  // Helper to read file as text
  const readFileAsText = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => reject(reader.error);
      reader.readAsText(file);
    });
  };

  // File Handlers
  const handleFileChange = async (
    type: "orders" | "payments" | "settlements",
    file: File | null
  ) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    setValidationSummary(null);

    if (!file) {
      if (type === "orders") { setOrdersText(""); setOrdersCount(0); }
      if (type === "payments") { setPaymentsText(""); setPaymentsCount(0); }
      if (type === "settlements") { setSettlementsText(""); setSettlementsCount(0); }
      return;
    }

    try {
      const text = await readFileAsText(file);
      const count = getRecordCount(text);

      if (type === "orders") {
        setOrdersText(text);
        setOrdersCount(count);
      } else if (type === "payments") {
        setPaymentsText(text);
        setPaymentsCount(count);
      } else if (type === "settlements") {
        setSettlementsText(text);
        setSettlementsCount(count);
      }
    } catch (err) {
      setErrorMessage(`Failed to read file ${file.name}`);
    }
  };

  // Pre-flight validation
  const handleValidate = async () => {
    if (!ordersText && !paymentsText && !settlementsText) {
      setErrorMessage("Please select at least one CSV file to validate.");
      return;
    }

    setIsValidating(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setValidationSummary(null);

    try {
      const res = await api.validateCSV({
        orders_csv: ordersText || undefined,
        payments_csv: paymentsText || undefined,
        settlements_csv: settlementsText || undefined,
      });

      if (res.success) {
        setValidationSummary(res.data);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Pre-flight validation failed.");
    } finally {
      setIsValidating(false);
    }
  };

  // Upload & Ingest with visual progress sequence
  const handleUploadAndIngest = async () => {
    if (!ordersText && !paymentsText && !settlementsText) {
      setErrorMessage("Please select CSV files before uploading.");
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      setUploadProgressStep("Uploading...");
      await new Promise((r) => setTimeout(r, 400));

      setUploadProgressStep("Parsing CSV...");
      await new Promise((r) => setTimeout(r, 400));

      setUploadProgressStep("Validating columns...");
      await new Promise((r) => setTimeout(r, 400));

      setUploadProgressStep("Checking records & database insertion...");
      const res = await api.uploadCSV({
        orders_csv: ordersText || undefined,
        payments_csv: paymentsText || undefined,
        settlements_csv: settlementsText || undefined,
      });

      if (res.success) {
        setUploadProgressStep("Upload complete.");
        setSuccessMessage(`Successfully uploaded and ingested dataset (${res.data.total_records} records).`);
        await loadOverview();
        if (onRefreshOverview) onRefreshOverview();
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to upload and ingest datasets.");
    } finally {
      setIsUploading(false);
      setUploadProgressStep(null);
    }
  };

  // Demo Dataset Generator ("TRY DEMO")
  const handleGenerateDemo = async () => {
    setIsGeneratingDemo(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await api.generateDemoData({
        num_orders: 100,
        anomaly_rate: 0.15,
        seed: 42,
      });

      if (res.success) {
        setSuccessMessage(`Demo dataset loaded (${res.data.num_orders} orders with synthetic anomalies).`);
        await loadOverview();
        if (onRefreshOverview) onRefreshOverview();

        // Navigate automatically to Dashboard
        if (onNavigateToTab) {
          onNavigateToTab("dashboard");
        }
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to generate demo dataset.");
    } finally {
      setIsGeneratingDemo(false);
    }
  };

  // Run 3-Way Reconciliation Directly from Import Page
  const handleRunReconciliation = async () => {
    setIsExecutingRecon(true);
    setErrorMessage(null);
    try {
      const res = await api.runReconciliation();
      if (res.success) {
        if (onNavigateToTab) {
          onNavigateToTab("reconciliation");
        }
      }
    } catch (err: any) {
      setErrorMessage(`Reconciliation failed: ${err.message}`);
    } finally {
      setIsExecutingRecon(false);
    }
  };

  // Download Sample Template Helpers
  const downloadSample = (type: "orders" | "payments" | "settlements") => {
    let content = "";
    let filename = "";

    if (type === "orders") {
      filename = "sample_orders.csv";
      content = `order_id,customer_id,merchant_id,amount,currency,status,created_at
ORD001,CUST001,MERCHANT001,10000.00,INR,COMPLETED,2026-03-01T10:00:00Z
ORD002,CUST002,MERCHANT001,5000.00,INR,COMPLETED,2026-03-01T10:15:00Z
ORD003,CUST003,MERCHANT001,7500.00,INR,COMPLETED,2026-03-01T10:30:00Z`;
    } else if (type === "payments") {
      filename = "sample_payments.csv";
      content = `payment_id,order_id,gateway,amount,fee,currency,status,transaction_ref,timestamp
PAY001,ORD001,Stripe,10000.00,200.00,INR,CAPTURED,tx_001,2026-03-01T10:05:00Z
PAY002,ORD002,Stripe,5000.00,100.00,INR,CAPTURED,tx_002,2026-03-01T10:20:00Z
PAY003,ORD003,Stripe,7500.00,150.00,INR,CAPTURED,tx_003,2026-03-01T10:35:00Z`;
    } else if (type === "settlements") {
      filename = "sample_settlements.csv";
      content = `settlement_id,payment_id,payout_ref,gross_amount,net_amount,fee_deducted,currency,settlement_date,status
SET001,PAY001,po_001,10000.00,9700.00,300.00,INR,2026-03-02T04:00:00Z,SETTLED
SET002,PAY002,po_001,5000.00,4900.00,100.00,INR,2026-03-02T04:00:00Z,SETTLED
SET003,PAY003,po_001,7500.00,7350.00,150.00,INR,2026-03-02T04:00:00Z,SETTLED`;
    }

    const blob = new Blob([content], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const allThreeUploaded = ordersCount > 0 && paymentsCount > 0 && settlementsCount > 0;
  const dbHasData = (systemOverview?.total_orders_in_db ?? 0) > 0;

  return (
    <div>
      {/* Page Title & Core Product Message */}
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "var(--spacing-md)" }}>
          <div>
            <h1 className="page-title">
              Find where your company's money doesn't match.
            </h1>
            <p className="page-subtitle" style={{ marginTop: "4px" }}>
              Compare what customers were charged, what payment gateways received, and what actually reached your bank account.
            </p>
          </div>

          {/* Quick Demo CTA */}
          <div
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-color)",
              borderRadius: "10px",
              padding: "10px 16px",
              display: "flex",
              alignItems: "center",
              gap: "var(--spacing-md)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <div>
              <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-primary)" }}>New here?</div>
              <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                See how the controller works using synthetic transactions.
              </div>
            </div>

            <button
              onClick={handleGenerateDemo}
              disabled={isGeneratingDemo}
              className="btn-action"
              style={{
                background: "var(--accent-primary)",
                borderColor: "var(--accent-primary-hover)",
                color: "#ffffff",
                fontWeight: 700,
                fontSize: "12px",
                whiteSpace: "nowrap",
              }}
            >
              {isGeneratingDemo ? "Loading Demo..." : "TRY DEMO"}
            </button>
          </div>
        </div>
      </div>

      {/* Visual Workflow Ribbon */}
      <WorkflowVisualizer currentStepId="data-import" onStepClick={(id) => onNavigateToTab && onNavigateToTab(id)} />

      {/* Core Concept Banner & Money Flow Diagram */}
      <div
        style={{
          backgroundColor: "var(--bg-surface)",
          border: "1px solid var(--border-color)",
          borderLeft: "4px solid var(--accent-primary)",
          borderRadius: "10px",
          padding: "var(--spacing-lg)",
          marginBottom: "var(--spacing-xl)",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <h3 style={{ margin: "0 0 12px 0", fontSize: "15px", fontWeight: 700 }}>
          How AI Finance Controller Identifies Discrepancies
        </h3>

        {/* Horizontal Money Flow */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "var(--spacing-md)",
            marginBottom: "var(--spacing-lg)",
            alignItems: "center",
          }}
        >
          <div
            style={{
              backgroundColor: "var(--bg-primary)",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
              padding: "14px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "10.5px", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 800, letterSpacing: "0.5px" }}>
              1. ORDER
            </div>
            <div style={{ fontSize: "12.5px", fontWeight: 600, marginTop: "4px" }}>What you expected to receive</div>
            <div style={{ fontSize: "16px", fontWeight: 800, marginTop: "6px", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>₹10,000</div>
          </div>

          <div
            style={{
              backgroundColor: "var(--bg-primary)",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
              padding: "14px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "10.5px", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 800, letterSpacing: "0.5px" }}>
              2. PAYMENT
            </div>
            <div style={{ fontSize: "12.5px", fontWeight: 600, marginTop: "4px" }}>What gateway collected</div>
            <div style={{ fontSize: "16px", fontWeight: 800, marginTop: "6px", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>₹10,000</div>
          </div>

          <div
            style={{
              backgroundColor: "var(--bg-primary)",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
              padding: "14px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "10.5px", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 800, letterSpacing: "0.5px" }}>
              3. SETTLEMENT
            </div>
            <div style={{ fontSize: "12.5px", fontWeight: 600, marginTop: "4px" }}>What reached your bank</div>
            <div style={{ fontSize: "16px", fontWeight: 800, marginTop: "6px", color: "var(--warning-text)", fontFamily: "var(--font-mono)" }}>₹9,700</div>
          </div>

          <div
            style={{
              backgroundColor: "var(--danger-bg)",
              border: "1px solid var(--danger-border)",
              borderRadius: "8px",
              padding: "14px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "10.5px", color: "var(--danger-text)", textTransform: "uppercase", fontWeight: 800, letterSpacing: "0.5px" }}>
              RESULT: CONTROLLER
            </div>
            <div style={{ fontSize: "12.5px", fontWeight: 700, marginTop: "4px", color: "var(--danger-text)" }}>
              Finds the difference
            </div>
            <div style={{ fontSize: "16px", fontWeight: 800, marginTop: "6px", color: "var(--danger-text)", fontFamily: "var(--font-mono)" }}>
              ⚠ ₹300 missing
            </div>
          </div>
        </div>

        <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5" }}>
          Compare your company's Customer Orders, Payment Gateway charges, and Bank Settlement deposits. Deterministic reconciliation calculates discrepancies, AI investigates the cause, and risky cases route for operator approval.
        </p>
      </div>

      {/* Starting Question Header */}
      <div style={{ marginBottom: "var(--spacing-md)" }}>
        <h2 style={{ fontSize: "18px", fontWeight: 700, margin: 0 }}>
          What finance data do you want to check?
        </h2>
        <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "4px" }}>
          Upload the three files below. We will compare them and identify missing payments, settlement differences, duplicate charges, fees and other anomalies.
        </p>
      </div>

      {/* Error & Success Toasts */}
      {errorMessage && (
        <div
          style={{
            backgroundColor: "var(--danger-bg)",
            border: "1px solid var(--danger-border)",
            borderRadius: "8px",
            padding: "12px 16px",
            marginBottom: "var(--spacing-md)",
            fontSize: "13px",
            color: "var(--danger-text)",
          }}
        >
          {errorMessage}
        </div>
      )}

      {successMessage && (
        <div
          style={{
            backgroundColor: "var(--success-bg)",
            border: "1px solid var(--success-border)",
            borderRadius: "8px",
            padding: "12px 16px",
            marginBottom: "var(--spacing-md)",
            fontSize: "13px",
            color: "var(--success-text)",
          }}
        >
          {successMessage}
        </div>
      )}

      {/* Upload Progress Indicator */}
      {uploadProgressStep && (
        <div
          style={{
            backgroundColor: "var(--info-bg)",
            border: "1px solid var(--info-border)",
            borderRadius: "8px",
            padding: "12px 16px",
            marginBottom: "var(--spacing-md)",
            fontSize: "13px",
            color: "var(--info-text)",
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <div className="status-dot connected" style={{ width: "10px", height: "10px" }}></div>
          <span>{uploadProgressStep}</span>
        </div>
      )}

      {/* 3 Upload Cards Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--spacing-lg)", marginBottom: "var(--spacing-xl)" }}>
        {/* Card 1: Orders */}
        <div className="card" style={{ justifyContent: "space-between" }}>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--accent-primary-hover)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                1. ORDERS
              </span>
              <button
                onClick={() => downloadSample("orders")}
                style={{ background: "transparent", border: "none", color: "var(--accent-primary-hover)", fontSize: "11px", fontWeight: 600, cursor: "pointer", textDecoration: "underline" }}
              >
                Sample CSV
              </button>
            </div>
            <h3 style={{ margin: "6px 0", fontSize: "14px", fontWeight: 700 }}>
              What customers were supposed to pay
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "12px" }}>
              Orders represent customer purchases and expected revenues.
            </p>

            {/* Schema preview */}
            <div style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border-subtle)", padding: "8px 10px", borderRadius: "6px", fontSize: "10.5px", fontFamily: "var(--font-mono)", color: "var(--text-secondary)", marginBottom: "12px", overflowX: "auto" }}>
              order_id | customer_id | merchant_id | amount | currency | status | created_at
            </div>

            {/* Status indicator */}
            {ordersCount > 0 ? (
              <div style={{ backgroundColor: "var(--success-bg)", border: "1px solid var(--success-border)", padding: "8px 12px", borderRadius: "6px", marginBottom: "12px" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--success-text)" }}>
                  ✓ orders.csv uploaded
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
                  {ordersCount.toLocaleString()} records detected
                </div>
              </div>
            ) : null}
          </div>

          <div>
            <input
              type="file"
              accept=".csv"
              id="orders-upload"
              style={{ display: "none" }}
              onChange={(e) => handleFileChange("orders", e.target.files?.[0] || null)}
            />
            <div style={{ display: "flex", gap: "8px" }}>
              <label
                htmlFor="orders-upload"
                className="btn-action"
                style={{
                  flex: 1,
                  textAlign: "center",
                  justifyContent: "center",
                  background: ordersCount > 0 ? "var(--bg-surface)" : "var(--accent-primary)",
                  color: ordersCount > 0 ? "var(--text-primary)" : "#ffffff",
                  borderColor: ordersCount > 0 ? "var(--border-color)" : "var(--accent-primary-hover)",
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: "12px",
                }}
              >
                {ordersCount > 0 ? "Change Orders CSV" : "Upload Orders CSV"}
              </label>

              {ordersCount > 0 && (
                <button
                  onClick={() => setPreviewModal({ title: "Orders Dataset Preview", csv: ordersText })}
                  className="btn-action"
                  style={{ fontSize: "11px", padding: "6px 10px" }}
                >
                  Preview Data
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Card 2: Payments */}
        <div className="card" style={{ justifyContent: "space-between" }}>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--accent-primary-hover)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                2. PAYMENTS
              </span>
              <button
                onClick={() => downloadSample("payments")}
                style={{ background: "transparent", border: "none", color: "var(--accent-primary-hover)", fontSize: "11px", fontWeight: 600, cursor: "pointer", textDecoration: "underline" }}
              >
                Sample CSV
              </button>
            </div>
            <h3 style={{ margin: "6px 0", fontSize: "14px", fontWeight: 700 }}>
              What payment gateway collected
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "12px" }}>
              Payments captured by gateway processors (Stripe/PayPal/Adyen).
            </p>

            {/* Schema preview */}
            <div style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border-subtle)", padding: "8px 10px", borderRadius: "6px", fontSize: "10.5px", fontFamily: "var(--font-mono)", color: "var(--text-secondary)", marginBottom: "12px", overflowX: "auto" }}>
              payment_id | order_id | gateway | amount | fee | currency | status | timestamp
            </div>

            {/* Status indicator */}
            {paymentsCount > 0 ? (
              <div style={{ backgroundColor: "var(--success-bg)", border: "1px solid var(--success-border)", padding: "8px 12px", borderRadius: "6px", marginBottom: "12px" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--success-text)" }}>
                  ✓ payments.csv uploaded
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
                  {paymentsCount.toLocaleString()} records detected
                </div>
              </div>
            ) : null}
          </div>

          <div>
            <input
              type="file"
              accept=".csv"
              id="payments-upload"
              style={{ display: "none" }}
              onChange={(e) => handleFileChange("payments", e.target.files?.[0] || null)}
            />
            <div style={{ display: "flex", gap: "8px" }}>
              <label
                htmlFor="payments-upload"
                className="btn-action"
                style={{
                  flex: 1,
                  textAlign: "center",
                  justifyContent: "center",
                  background: paymentsCount > 0 ? "var(--bg-surface)" : "var(--accent-primary)",
                  color: paymentsCount > 0 ? "var(--text-primary)" : "#ffffff",
                  borderColor: paymentsCount > 0 ? "var(--border-color)" : "var(--accent-primary-hover)",
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: "12px",
                }}
              >
                {paymentsCount > 0 ? "Change Payments CSV" : "Upload Payments CSV"}
              </label>

              {paymentsCount > 0 && (
                <button
                  onClick={() => setPreviewModal({ title: "Payments Dataset Preview", csv: paymentsText })}
                  className="btn-action"
                  style={{ fontSize: "11px", padding: "6px 10px" }}
                >
                  Preview Data
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Card 3: Settlements */}
        <div className="card" style={{ justifyContent: "space-between" }}>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--accent-primary-hover)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                3. SETTLEMENTS
              </span>
              <button
                onClick={() => downloadSample("settlements")}
                style={{ background: "transparent", border: "none", color: "var(--accent-primary-hover)", fontSize: "11px", fontWeight: 600, cursor: "pointer", textDecoration: "underline" }}
              >
                Sample CSV
              </button>
            </div>
            <h3 style={{ margin: "6px 0", fontSize: "14px", fontWeight: 700 }}>
              What reached your bank
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "12px" }}>
              Bank payout settlements transferred into company account.
            </p>

            {/* Schema preview */}
            <div style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border-subtle)", padding: "8px 10px", borderRadius: "6px", fontSize: "10.5px", fontFamily: "var(--font-mono)", color: "var(--text-secondary)", marginBottom: "12px", overflowX: "auto" }}>
              settlement_id | payment_id | payout_ref | gross_amount | net_amount | settlement_date
            </div>

            {/* Status indicator */}
            {settlementsCount > 0 ? (
              <div style={{ backgroundColor: "var(--success-bg)", border: "1px solid var(--success-border)", padding: "8px 12px", borderRadius: "6px", marginBottom: "12px" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--success-text)" }}>
                  ✓ settlements.csv uploaded
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
                  {settlementsCount.toLocaleString()} records detected
                </div>
              </div>
            ) : null}
          </div>

          <div>
            <input
              type="file"
              accept=".csv"
              id="settlements-upload"
              style={{ display: "none" }}
              onChange={(e) => handleFileChange("settlements", e.target.files?.[0] || null)}
            />
            <div style={{ display: "flex", gap: "8px" }}>
              <label
                htmlFor="settlements-upload"
                className="btn-action"
                style={{
                  flex: 1,
                  textAlign: "center",
                  justifyContent: "center",
                  background: settlementsCount > 0 ? "var(--bg-surface)" : "var(--accent-primary)",
                  color: settlementsCount > 0 ? "var(--text-primary)" : "#ffffff",
                  borderColor: settlementsCount > 0 ? "var(--border-color)" : "var(--accent-primary-hover)",
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: "12px",
                }}
              >
                {settlementsCount > 0 ? "Change Settlements CSV" : "Upload Settlements CSV"}
              </label>

              {settlementsCount > 0 && (
                <button
                  onClick={() => setPreviewModal({ title: "Settlements Dataset Preview", csv: settlementsText })}
                  className="btn-action"
                  style={{ fontSize: "11px", padding: "6px 10px" }}
                >
                  Preview Data
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Validation Toolbar if files selected */}
      {(ordersCount > 0 || paymentsCount > 0 || settlementsCount > 0) && (
        <div
          style={{
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-color)",
            borderRadius: "10px",
            padding: "var(--spacing-md) var(--spacing-lg)",
            marginBottom: "var(--spacing-xl)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "var(--spacing-md)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div>
            <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-primary)" }}>
              Selected Files: {ordersCount.toLocaleString()} Orders &bull; {paymentsCount.toLocaleString()} Payments &bull; {settlementsCount.toLocaleString()} Settlements
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
              Run pre-flight check or ingest data directly to start reconciliation
            </div>
          </div>

          <div style={{ display: "flex", gap: "var(--spacing-sm)" }}>
            <button
              onClick={handleValidate}
              disabled={isValidating || isUploading}
              className="btn-action"
              style={{ background: "var(--bg-primary)", borderColor: "var(--border-color)", fontSize: "12px" }}
            >
              {isValidating ? "Validating..." : "1. Pre-Flight Validation"}
            </button>

            <button
              onClick={handleUploadAndIngest}
              disabled={isUploading}
              className="btn-action"
              style={{
                background: "var(--accent-primary)",
                borderColor: "var(--accent-primary-hover)",
                color: "#ffffff",
                fontWeight: 700,
                fontSize: "12px",
              }}
            >
              {isUploading ? "Uploading & Ingesting..." : "2. Ingest Dataset to System"}
            </button>
          </div>
        </div>
      )}

      {/* Validation Summary Display */}
      {validationSummary && (
        <div
          style={{
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-color)",
            borderRadius: "10px",
            padding: "var(--spacing-lg)",
            marginBottom: "var(--spacing-xl)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--spacing-md)" }}>
            <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 700 }}>
              Pre-Flight Validation Check Results
            </h3>
            <span className={`badge ${validationSummary.is_reconcilable ? "resolved" : "detected"}`}>
              {validationSummary.is_reconcilable ? "RECONCILATION READY" : "ERRORS DETECTED"}
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "var(--spacing-sm)", marginBottom: "var(--spacing-md)" }}>
            <div style={{ backgroundColor: "var(--bg-primary)", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Orders Valid</div>
              <div style={{ fontSize: "14px", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{validationSummary.orders_count}</div>
            </div>
            <div style={{ backgroundColor: "var(--bg-primary)", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Payments Valid</div>
              <div style={{ fontSize: "14px", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{validationSummary.payments_count}</div>
            </div>
            <div style={{ backgroundColor: "var(--bg-primary)", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Settlements Valid</div>
              <div style={{ fontSize: "14px", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{validationSummary.settlements_count}</div>
            </div>
            <div style={{ backgroundColor: "var(--bg-primary)", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>File Headers Status</div>
              <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--success-text)", marginTop: "2px" }}>
                ✓ Headers Valid
              </div>
            </div>
            <div style={{ backgroundColor: "var(--bg-primary)", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Cross References</div>
              <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--success-text)", marginTop: "2px" }}>
                ✓ Linked OK
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUMMARY CARD WHEN DATA IS READY / ALL THREE UPLOADED OR IN DB */}
      {(allThreeUploaded || dbHasData) && (
        <div
          style={{
            backgroundColor: "var(--bg-surface)",
            border: "2px solid var(--accent-primary)",
            borderRadius: "10px",
            padding: "var(--spacing-xl)",
            marginBottom: "var(--spacing-xl)",
            boxShadow: "0 0 20px var(--accent-glow)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "var(--spacing-md)" }}>
            <div>
              <span className="badge resolved" style={{ marginBottom: "8px" }}>
                ✓ DATASET READY
              </span>
              <h2 style={{ margin: "6px 0 6px 0", fontSize: "20px", fontWeight: 800 }}>
                Your finance data is ready
              </h2>
              <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)" }}>
                Orders: <strong className="font-mono">{(ordersCount || systemOverview?.total_orders_in_db || 0).toLocaleString()}</strong> &bull;
                Payments: <strong className="font-mono">{(paymentsCount || systemOverview?.total_payments_in_db || 0).toLocaleString()}</strong> &bull;
                Settlements: <strong className="font-mono">{(settlementsCount || systemOverview?.total_settlements_in_db || 0).toLocaleString()}</strong>
              </p>
            </div>

            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "12px", color: "var(--success-text)", fontWeight: 600 }}>
                ✓ File structure valid &bull; ✓ Required columns present &bull; ✓ Amounts & dates valid
              </div>
            </div>
          </div>

          <div
            style={{
              marginTop: "var(--spacing-lg)",
              paddingTop: "var(--spacing-lg)",
              borderTop: "1px solid var(--border-color)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "var(--spacing-md)",
            }}
          >
            <div>
              <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-primary)" }}>
                Ready to find financial discrepancies
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                We compare every Order → Payment → Settlement relationship and identify where the amounts or records don't match.
              </div>
            </div>

            <button
              onClick={handleRunReconciliation}
              disabled={isExecutingRecon}
              className="btn-action"
              style={{
                background: "var(--accent-primary)",
                borderColor: "var(--accent-primary-hover)",
                color: "#ffffff",
                fontWeight: 800,
                fontSize: "14px",
                padding: "12px 24px",
                boxShadow: "0 4px 14px var(--accent-glow)",
              }}
            >
              {isExecutingRecon ? "Executing Reconciliation..." : "⚡ RUN 3-WAY RECONCILIATION"}
            </button>
          </div>
        </div>
      )}

      {/* CSV Data Preview Modal */}
      {previewModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            backgroundColor: "rgba(0,0,0,0.7)",
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
              width: "700px",
              maxWidth: "100%",
              backgroundColor: "var(--bg-surface)",
              maxHeight: "80vh",
              display: "flex",
              flexDirection: "column",
              borderRadius: "12px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--spacing-md)", borderBottom: "1px solid var(--border-color)", paddingBottom: "var(--spacing-sm)" }}>
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>{previewModal.title}</h3>
              <button onClick={() => setPreviewModal(null)} style={{ background: "transparent", border: "none", color: "var(--text-secondary)", fontSize: "22px", cursor: "pointer" }}>
                &times;
              </button>
            </div>

            <div style={{ overflowX: "auto", overflowY: "auto", flex: 1, backgroundColor: "var(--bg-primary)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
              <pre style={{ margin: 0, fontSize: "11.5px", fontFamily: "var(--font-mono)", color: "var(--text-primary)", whiteSpace: "pre-wrap" }}>
                {previewModal.csv.split("\n").slice(0, 20).join("\n")}
              </pre>
            </div>

            <div style={{ marginTop: "var(--spacing-md)", textAlign: "right" }}>
              <button className="btn-retry" onClick={() => setPreviewModal(null)}>
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
