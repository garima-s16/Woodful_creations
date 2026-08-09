import React from "react";
import ExportButton from "../components/ExportButton";

export default function DashboardStock() {
  return (
    <div style={{ padding: 24 }}>
      <h2>Stock Management Dashboard (Bootstrap)</h2>
      <div style={{ marginBottom: 12 }}>
        <ExportButton url="/reports/stock-dashboard.xlsx" filename="stock-dashboard.xlsx" label="Download Stock Workbook" />
      </div>
      <p>This is a basic dashboard placeholder. Replace with full UI as needed.</p>
    </div>
  );
}
