import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Provider } from 'react-redux';
import store from './redux/store';
import './styles/App.css';

import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import StockInventoryPage from './pages/StockInventoryPage';
import AIChatPage from './pages/AIChatPage';
import ClientManagementPage from './pages/ClientManagementPage';
import AttendancePage from './pages/AttendancePage';
import EstimatesPage from './pages/EstimatesPage';
import InterviewsPage from './pages/InterviewsPage';
import PaymentsPage from './pages/PaymentsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import SalesOrdersPage from './pages/SalesOrdersPage';

import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    const userData = localStorage.getItem('userData');
    
    if (token && userData) {
      setIsAuthenticated(true);
      setUser(JSON.parse(userData));
    }
  }, []);

  const handleLogin = (userData, token) => {
    setIsAuthenticated(true);
    setUser(userData);
    localStorage.setItem('authToken', token);
    localStorage.setItem('userData', JSON.stringify(userData));
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setUser(null);
    localStorage.removeItem('authToken');
    localStorage.removeItem('userData');
  };

  if (!isAuthenticated) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <Provider store={store}>
      <Router>
        <div className="app-container">
          <Navbar user={user} onLogout={handleLogout} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
          <div className="app-content">
            <Sidebar isOpen={sidebarOpen} user={user} />
            <main className="main-content">
              <Routes>
                <Route path="/dashboard" element={
                  <ProtectedRoute>
                    <DashboardPage user={user} />
                  </ProtectedRoute>
                } />
                <Route path="/stock-inventory" element={
                  <ProtectedRoute>
                    <StockInventoryPage user={user} />
                  </ProtectedRoute>
                } />
                <Route path="/ai-chat" element={
                  <ProtectedRoute>
                    <AIChatPage user={user} />
                  </ProtectedRoute>
                } />
                <Route path="/clients" element={
                  <ProtectedRoute>
                    <ClientManagementPage user={user} />
                  </ProtectedRoute>
                } />
                <Route path="/attendance" element={
                  <ProtectedRoute>
                    <AttendancePage user={user} />
                  </ProtectedRoute>
                } />
                <Route path="/estimates" element={
                  <ProtectedRoute>
                    <EstimatesPage user={user} />
                  </ProtectedRoute>
                } />
                <Route path="/interviews" element={
                  <ProtectedRoute>
                    <InterviewsPage user={user} />
                  </ProtectedRoute>
                } />
                <Route path="/payments" element={
                  <ProtectedRoute>
                    <PaymentsPage user={user} />
                  </ProtectedRoute>
                } />
                <Route path="/analytics" element={
                  <ProtectedRoute>
                    <AnalyticsPage user={user} />
                  </ProtectedRoute>
                } />
                <Route path="/sales" element={
                  <ProtectedRoute>
                    <SalesOrdersPage user={user} />
                  </ProtectedRoute>
                } />
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </main>
          </div>
        </div>
      </Router>
    </Provider>
  );
}

export default App;