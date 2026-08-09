import React from "react";
import DashboardStock from "./pages/DashboardStock";

function App() {
  return (
    <div>
      <header style={{ background: "#123", color: "#fff", padding: 12 }}>
        <img src="/logo.png" alt="Woodful Logo" style={{ height: 48 }} />
      </header>
      <main>
        <DashboardStock />
      </main>
    </div>
  );
}
export default App;
