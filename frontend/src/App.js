import React, { useCallback, useEffect, useState } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom';
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

import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';

const getInitialSidebarState = () =>
  typeof window === 'undefined' ? true : window.innerWidth > 768;

function AppShell({ user, isSidebarOpen, onLogout, onSidebarClose, onSidebarToggle }) {
  return (
    <div className="app-container">
      <Navbar
        isSidebarOpen={isSidebarOpen}
        onLogout={onLogout}
        toggleSidebar={onSidebarToggle}
        user={user}
      />
      <div className="app-content">
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={onSidebarClose}
          user={user}
        />
        <main className="main-content">
          <Routes>
            <Route path="/dashboard" element={<DashboardPage user={user} />} />
            <Route
              path="/stock-inventory"
              element={<StockInventoryPage user={user} />}
            />
            <Route path="/ai-chat" element={<AIChatPage user={user} />} />
            <Route path="/clients" element={<ClientManagementPage user={user} />} />
            <Route path="/attendance" element={<AttendancePage user={user} />} />
            <Route path="/estimates" element={<EstimatesPage user={user} />} />
            <Route path="/interviews" element={<InterviewsPage user={user} />} />
            <Route path="/payments" element={<PaymentsPage user={user} />} />
            <Route path="/analytics" element={<AnalyticsPage user={user} />} />
            <Route path="/" element={<Navigate replace to="/dashboard" />} />
            <Route path="*" element={<Navigate replace to="/dashboard" />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(getInitialSidebarState);

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    const userData = localStorage.getItem('userData');

    if (!token || !userData) {
      return;
    }

    try {
      setIsAuthenticated(true);
      setUser(JSON.parse(userData));
    } catch (error) {
      console.error('Unable to restore saved user data:', error);
      localStorage.removeItem('authToken');
      localStorage.removeItem('userData');
    }
  }, []);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 768) {
        setSidebarOpen(true);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleLogin = (userData, token) => {
    setIsAuthenticated(true);
    setUser(userData);
    localStorage.setItem('authToken', token);
    localStorage.setItem('userData', JSON.stringify(userData));
    setSidebarOpen(getInitialSidebarState());
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setUser(null);
    localStorage.removeItem('authToken');
    localStorage.removeItem('userData');
  };

  const handleSidebarClose = useCallback(() => {
    setSidebarOpen(false);
  }, []);

  const handleSidebarToggle = useCallback(() => {
    setSidebarOpen((open) => !open);
  }, []);

  return (
    <Provider store={store}>
      <Router>
        <Routes>
          <Route
            path="/login"
            element={
              isAuthenticated ? (
                <Navigate replace to="/dashboard" />
              ) : (
                <LoginPage onLogin={handleLogin} />
              )
            }
          />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <AppShell
                  isSidebarOpen={sidebarOpen}
                  onLogout={handleLogout}
                  onSidebarClose={handleSidebarClose}
                  onSidebarToggle={handleSidebarToggle}
                  user={user}
                />
              </ProtectedRoute>
            }
          />
        </Routes>
      </Router>
    </Provider>
  );
}

export default App;