import { useState, useEffect } from "react";
import { DashboardLayout } from "./layouts/DashboardLayout";
import { DataImport } from "./pages/DataImport";
import { Dashboard } from "./pages/Dashboard";
import { Reconciliation } from "./pages/Reconciliation";
import { Exceptions } from "./pages/Exceptions";
import { AIInvestigations } from "./pages/AIInvestigations";
import { ReviewQueue } from "./pages/ReviewQueue";
import { AuditTrail } from "./pages/AuditTrail";
import { api } from "./services/api";

function App() {
  const [activeTab, setActiveTab] = useState<string>("data-import");
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [datasetSource, setDatasetSource] = useState<string>("EMPTY");

  const checkHealthAndSummary = async () => {
    try {
      const [healthRes, dataSummaryRes] = await Promise.allSettled([
        api.getHealth(),
        api.getDataSummary(),
      ]);

      if (healthRes.status === "fulfilled" && healthRes.value?.database_connected) {
        setIsConnected(true);
      } else {
        setIsConnected(false);
      }

      if (dataSummaryRes.status === "fulfilled" && dataSummaryRes.value?.success) {
        setDatasetSource(dataSummaryRes.value.data.dataset_source || "EMPTY");
      }
    } catch (err) {
      console.error("Health & summary check error:", err);
      setIsConnected(false);
    }
  };

  useEffect(() => {
    // Initial check
    checkHealthAndSummary();

    // Check periodically every 15 seconds
    const interval = setInterval(checkHealthAndSummary, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleNavigateTab = (tab: string) => {
    // Normalize step identifiers from workflow visualizer
    const tabMap: Record<string, string> = {
      order: "data-import",
      payment: "data-import",
      settlement: "data-import",
      "data-import": "data-import",
      dashboard: "dashboard",
      reconciliation: "reconciliation",
      exceptions: "exceptions",
      "ai-investigations": "ai-investigations",
      "ai-investigation": "ai-investigations",
      "review-queue": "review-queue",
      "audit-trail": "audit-trail",
    };
    setActiveTab(tabMap[tab] || tab);
  };

  const renderContent = () => {
    switch (activeTab) {
      case "data-import":
        return (
          <DataImport
            onNavigateToTab={handleNavigateTab}
            onRefreshOverview={checkHealthAndSummary}
          />
        );
      case "dashboard":
        return <Dashboard onNavigateToTab={handleNavigateTab} />;
      case "reconciliation":
        return <Reconciliation onNavigateToTab={handleNavigateTab} />;
      case "exceptions":
        return <Exceptions onNavigateToTab={handleNavigateTab} />;
      case "ai-investigations":
        return <AIInvestigations onNavigateToTab={handleNavigateTab} />;
      case "review-queue":
        return <ReviewQueue onNavigateToTab={handleNavigateTab} />;
      case "audit-trail":
        return <AuditTrail onNavigateToTab={handleNavigateTab} />;
      default:
        return (
          <DataImport
            onNavigateToTab={handleNavigateTab}
            onRefreshOverview={checkHealthAndSummary}
          />
        );
    }
  };

  return (
    <DashboardLayout
      activeTab={activeTab}
      setActiveTab={setActiveTab}
      isConnected={isConnected}
      onRetryConnection={checkHealthAndSummary}
      datasetSource={datasetSource}
    >
      {renderContent()}
    </DashboardLayout>
  );
}

export default App;
