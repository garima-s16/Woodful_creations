import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
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

// Eager (static) imports: only the routes an unauthenticated user
// actually needs. These must render as fast as possible and must
// never wait on the authenticated application's bundle.
import LoginPage from './pages/LoginPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';

// Lazy (code-split) imports: every authenticated-only page. Previously
// these were all static imports sharing App.jsx's module graph, which
// meant the login page could not render until the browser had
// downloaded, parsed, and executed the JS for the entire authenticated
// application - every module's tables, forms, and chart code included.
// React.lazy() + dynamic import() splits each of these into its own
// chunk, fetched only when its route is actually visited.
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const MaterialsPage = lazy(() => import('./pages/MaterialsPage'));
const LocationsPage = lazy(() => import('./pages/LocationsPage'));
const PurchaseImportPage = lazy(() => import('./pages/PurchaseImportPage'));
const MobileAppPage = lazy(() => import('./pages/MobileAppPage'));
const MaterialDetailPage = lazy(() => import('./pages/MaterialDetailPage'));
const ProductsPage = lazy(() => import('./pages/ProductsPage'));
const ProductDetailPage = lazy(() => import('./pages/ProductDetailPage'));
const SuppliersPage = lazy(() => import('./pages/SuppliersPage'));
const SupplierDetailPage = lazy(() => import('./pages/SupplierDetailPage'));
const PurchasesPage = lazy(() => import('./pages/PurchasesPage'));
const PurchaseDetailPage = lazy(() => import('./pages/PurchaseDetailPage'));
const IssuesPage = lazy(() => import('./pages/IssuesPage'));
const ClientsPage = lazy(() => import('./pages/ClientsPage'));
const ClientDetailPage = lazy(() => import('./pages/ClientDetailPage'));
const OrdersPage = lazy(() => import('./pages/OrdersPage'));
const OrderDetailPage = lazy(() => import('./pages/OrderDetailPage'));
const PaymentsPage = lazy(() => import('./pages/PaymentsPage'));
const ProjectExpensesPage = lazy(() => import('./pages/ProjectExpensesPage'));
const EmployeesPage = lazy(() => import('./pages/EmployeesPage'));
const EmployeeDetailPage = lazy(() => import('./pages/EmployeeDetailPage'));
const AttendancePage = lazy(() => import('./pages/AttendancePage'));
const LeavesPage = lazy(() => import('./pages/LeavesPage'));
const DailyTasksPage = lazy(() => import('./pages/DailyTasksPage'));
const TaskDetailPage = lazy(() => import('./pages/TaskDetailPage'));
const ProductionJobsPage = lazy(() => import('./pages/ProductionJobsPage'));
const ProductionJobDetailPage = lazy(() => import('./pages/ProductionJobDetailPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const EstimatesPage = lazy(() => import('./pages/EstimatesPage'));
const EstimateDetailPage = lazy(() => import('./pages/EstimateDetailPage'));
const CandidatesPage = lazy(() => import('./pages/CandidatesPage'));
const CandidateDetailPage = lazy(() => import('./pages/CandidateDetailPage'));
const InterviewsPage = lazy(() => import('./pages/InterviewsPage'));
const SalarySlipsPage = lazy(() => import('./pages/SalarySlipsPage'));
const UsersPage = lazy(() => import('./pages/UsersPage'));
const AuditLogsPage = lazy(() => import('./pages/AuditLogsPage'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));

function AppLayout({ children }) {
  const MOBILE_BREAKPOINT = 768;
  const [isSidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > MOBILE_BREAKPOINT);
  // Tracks which side of the breakpoint we were last on, so a resize only
  // forces the sidebar open/closed when actually crossing into a different
  // layout mode - never on every pixel of a drag-resize, and never
  // overriding a manual toggle made while staying within the same mode.
  const isDesktopRef = useRef(window.innerWidth > MOBILE_BREAKPOINT);
  const isCartOpen = useSelector((state) => state.cart.isOpen);
  const { user } = useSelector((state) => state.auth);
  const dispatch = useDispatch();
  const navigate = useNavigate();

  // Keeps the sidebar usable across a resize. Without this, the sidebar's
  // open/closed flag is only ever set once on mount: starting on a narrow
  // (mobile) viewport with the sidebar closed and then resizing up to
  // desktop width would leave it permanently closed with no way to reopen
  // it, since the hamburger toggle is hidden on desktop layouts.
  useEffect(() => {
    let frame = null;
    const handleResize = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = null;
        const isDesktopNow = window.innerWidth > MOBILE_BREAKPOINT;
        if (isDesktopNow !== isDesktopRef.current) {
          isDesktopRef.current = isDesktopNow;
          setSidebarOpen(isDesktopNow);
        }
      });
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

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
        <Sidebar isOpen={isSidebarOpen} user={user} onClose={() => setSidebarOpen(false)} />
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
    <Suspense fallback={null}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/" element={<Protected><DashboardPage /></Protected>} />
        <Route path="/dashboard" element={<Protected><DashboardPage /></Protected>} />
        <Route path="/analytics" element={<Protected><AnalyticsPage /></Protected>} />
        <Route path="/materials" element={<Protected><MaterialsPage /></Protected>} />
        <Route path="/materials/:materialId" element={<Protected><MaterialDetailPage /></Protected>} />
        <Route path="/products" element={<Protected><ProductsPage /></Protected>} />
        <Route path="/products/:productId" element={<Protected><ProductDetailPage /></Protected>} />
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
    </Suspense>
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
