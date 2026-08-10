import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';

import { authAPI } from './utils/api';
import { sessionCheckFinished, logout as logoutAction } from './redux/slices/authSlice';

import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import ProtectedRoute from './components/ProtectedRoute';

import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import MaterialsPage from './pages/MaterialsPage';
import SuppliersPage from './pages/SuppliersPage';
import PurchasesPage from './pages/PurchasesPage';
import IssuesPage from './pages/IssuesPage';
import ClientsPage from './pages/ClientsPage';
import OrdersPage from './pages/OrdersPage';
import PaymentsPage from './pages/PaymentsPage';
import ProjectExpensesPage from './pages/ProjectExpensesPage';
import EmployeesPage from './pages/EmployeesPage';
import AttendancePage from './pages/AttendancePage';
import DailyTasksPage from './pages/DailyTasksPage';
import SettingsPage from './pages/SettingsPage';

function AppLayout({ children }) {
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  const { user } = useSelector((state) => state.auth);
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await authAPI.logout();
    } finally {
      dispatch(logoutAction());
      navigate('/login', { replace: true });
    }
  };

  const navbarUser = user ? { ...user, name: user.full_name || user.username } : null;

  return (
    <div className="app-shell">
      <Navbar user={navbarUser} onLogout={handleLogout} toggleSidebar={() => setSidebarOpen((v) => !v)} />
      <div className="app-body">
        <Sidebar isOpen={isSidebarOpen} user={user} />
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}

function Protected({ children }) {
  return (
    <ProtectedRoute>
      <AppLayout>{children}</AppLayout>
    </ProtectedRoute>
  );
}

function AppRoutes() {
  const dispatch = useDispatch();

  useEffect(() => {
    authAPI
      .me()
      .then((res) => dispatch(sessionCheckFinished(res.data)))
      .catch(() => dispatch(sessionCheckFinished(null)));
  }, [dispatch]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/dashboard" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/materials" element={<Protected><MaterialsPage /></Protected>} />
      <Route path="/suppliers" element={<Protected><SuppliersPage /></Protected>} />
      <Route path="/purchases" element={<Protected><PurchasesPage /></Protected>} />
      <Route path="/issues" element={<Protected><IssuesPage /></Protected>} />
      <Route path="/clients" element={<Protected><ClientsPage /></Protected>} />
      <Route path="/orders" element={<Protected><OrdersPage /></Protected>} />
      <Route path="/payments" element={<Protected><PaymentsPage /></Protected>} />
      <Route path="/project-expenses" element={<Protected><ProjectExpensesPage /></Protected>} />
      <Route path="/employees" element={<Protected><EmployeesPage /></Protected>} />
      <Route path="/attendance" element={<Protected><AttendancePage /></Protected>} />
      <Route path="/daily-tasks" element={<Protected><DailyTasksPage /></Protected>} />
      <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
