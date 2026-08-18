import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';

import { authAPI } from './utils/api';
import { sessionCheckFinished, logout as logoutAction } from './redux/slices/authSlice';
import { openCart, closeCart, fetchCart, resetCartView } from './redux/slices/cartSlice';

import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import MobileBottomNav from './components/MobileBottomNav';
import ProtectedRoute from './components/ProtectedRoute';
import ChatWidget from './components/ChatWidget';
import Footer from './components/Footer';
import CartDrawer from './components/CartDrawer';

import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import MaterialsPage from './pages/MaterialsPage';
import LocationsPage from './pages/LocationsPage';
import PurchaseImportPage from './pages/PurchaseImportPage';
import MobileAppPage from './pages/MobileAppPage';
import MaterialDetailPage from './pages/MaterialDetailPage';
import SuppliersPage from './pages/SuppliersPage';
import SupplierDetailPage from './pages/SupplierDetailPage';
import PurchasesPage from './pages/PurchasesPage';
import PurchaseDetailPage from './pages/PurchaseDetailPage';
import IssuesPage from './pages/IssuesPage';
import ClientsPage from './pages/ClientsPage';
import ClientDetailPage from './pages/ClientDetailPage';
import OrdersPage from './pages/OrdersPage';
import OrderDetailPage from './pages/OrderDetailPage';
import PaymentsPage from './pages/PaymentsPage';
import ProjectExpensesPage from './pages/ProjectExpensesPage';
import EmployeesPage from './pages/EmployeesPage';
import EmployeeDetailPage from './pages/EmployeeDetailPage';
import AttendancePage from './pages/AttendancePage';
import LeavesPage from './pages/LeavesPage';
import DailyTasksPage from './pages/DailyTasksPage';
import TaskDetailPage from './pages/TaskDetailPage';
import ProductionJobsPage from './pages/ProductionJobsPage';
import ProductionJobDetailPage from './pages/ProductionJobDetailPage';
import SettingsPage from './pages/SettingsPage';
import EstimatesPage from './pages/EstimatesPage';
import EstimateDetailPage from './pages/EstimateDetailPage';
import CandidatesPage from './pages/CandidatesPage';
import CandidateDetailPage from './pages/CandidateDetailPage';
import InterviewsPage from './pages/InterviewsPage';
import SalarySlipsPage from './pages/SalarySlipsPage';
import UsersPage from './pages/UsersPage';
import AuditLogsPage from './pages/AuditLogsPage';

function AppLayout({ children }) {
  const [isSidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 768);
  const isCartOpen = useSelector((state) => state.cart.isOpen);
  const { user } = useSelector((state) => state.auth);
  const dispatch = useDispatch();
  const navigate = useNavigate();

  // Runs whenever the logged-in identity changes (login, logout, or a
  // different user's session restoring) - fetches THAT user's own cart
  // from the database (the backend scopes it to the authenticated
  // token, so no user id needs to be passed here), or clears the
  // in-memory view on logout without touching any stored data.
  useEffect(() => {
    if (user?.id) {
      dispatch(fetchCart());
    } else {
      dispatch(resetCartView());
    }
  }, [dispatch, user?.id]);

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
      <Navbar user={navbarUser} onLogout={handleLogout} toggleSidebar={() => setSidebarOpen((v) => !v)} onOpenCart={() => dispatch(openCart())} />
      <div className="app-body">
        <Sidebar isOpen={isSidebarOpen} user={user} />
        <main className="app-content">{children}</main>
      </div>
      <Footer />
      <MobileBottomNav onOpenMenu={() => setSidebarOpen((v) => !v)} />
      <ChatWidget />
      <CartDrawer open={isCartOpen} onClose={() => dispatch(closeCart())} />
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
      <Route path="/materials/:materialId" element={<Protected><MaterialDetailPage /></Protected>} />
      <Route path="/locations" element={<Protected><LocationsPage /></Protected>} />
      <Route path="/purchases/import" element={<Protected><PurchaseImportPage /></Protected>} />
      <Route path="/mobile-app" element={<Protected><MobileAppPage /></Protected>} />
      <Route path="/suppliers" element={<Protected><SuppliersPage /></Protected>} />
      <Route path="/suppliers/:supplierId" element={<Protected><SupplierDetailPage /></Protected>} />
      <Route path="/purchases" element={<Protected><PurchasesPage /></Protected>} />
      <Route path="/purchases/:purchaseId" element={<Protected><PurchaseDetailPage /></Protected>} />
      <Route path="/issues" element={<Protected><IssuesPage /></Protected>} />
      <Route path="/clients" element={<Protected><ClientsPage /></Protected>} />
      <Route path="/clients/:clientId" element={<Protected><ClientDetailPage /></Protected>} />
      <Route path="/orders" element={<Protected><OrdersPage /></Protected>} />
      <Route path="/orders/:orderId" element={<Protected><OrderDetailPage /></Protected>} />
      <Route path="/payments" element={<Protected><PaymentsPage /></Protected>} />
      <Route path="/project-expenses" element={<Protected><ProjectExpensesPage /></Protected>} />
      <Route path="/employees" element={<Protected><EmployeesPage /></Protected>} />
      <Route path="/employees/:employeeId" element={<Protected><EmployeeDetailPage /></Protected>} />
      <Route path="/attendance" element={<Protected><AttendancePage /></Protected>} />
      <Route path="/leaves" element={<Protected><LeavesPage /></Protected>} />
      <Route path="/daily-tasks" element={<Protected><DailyTasksPage /></Protected>} />
      <Route path="/daily-tasks/:taskId" element={<Protected><TaskDetailPage /></Protected>} />
      <Route path="/production-jobs" element={<Protected><ProductionJobsPage /></Protected>} />
      <Route path="/production-jobs/:jobId" element={<Protected><ProductionJobDetailPage /></Protected>} />
      <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
      <Route path="/users" element={<Protected><UsersPage /></Protected>} />
      <Route path="/audit-logs" element={<Protected><AuditLogsPage /></Protected>} />
      <Route path="/estimates" element={<Protected><EstimatesPage /></Protected>} />
      <Route path="/estimates/:estimateId" element={<Protected><EstimateDetailPage /></Protected>} />
      <Route path="/candidates" element={<Protected><CandidatesPage /></Protected>} />
      <Route path="/candidates/:candidateId" element={<Protected><CandidateDetailPage /></Protected>} />
      <Route path="/interviews" element={<Protected><InterviewsPage /></Protected>} />
      <Route path="/salary-slips" element={<Protected><SalarySlipsPage /></Protected>} />
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
