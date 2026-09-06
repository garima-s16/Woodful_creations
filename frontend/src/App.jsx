import React, { Suspense, useEffect, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';

import { authAPI } from './utils/api';
import { setDocumentTitle } from './utils/pageTitle';
import { sessionCheckFinished, logout as logoutAction } from './redux/slices/authSlice';
import { openCart, closeCart, fetchCart, resetCartView } from './redux/slices/cartSlice';

import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import MobileBottomNav from './components/MobileBottomNav';
import ProtectedRoute from './components/ProtectedRoute';
import ChatWidget from './components/ChatWidget';
import Footer from './components/Footer';
import CartDrawer from './modules/procurement/components/CartDrawer';

import LoginPage from './pages/LoginPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import NotFoundPage from './pages/NotFoundPage';
const DashboardPage = React.lazy(() => import('./modules/reporting/pages/DashboardPage'));
const BusinessDecisionCentrePage = React.lazy(() => import('./modules/reporting/pages/BusinessDecisionCentrePage'));
const InventoryPage = React.lazy(() => import('./modules/inventory/pages/InventoryPage'));
const MaterialsPage = React.lazy(() => import('./modules/inventory/pages/MaterialsPage'));
const LocationsPage = React.lazy(() => import('./modules/inventory/pages/LocationsPage'));
const PurchaseImportPage = React.lazy(() => import('./modules/procurement/pages/PurchaseImportPage'));
const ClientImportPage = React.lazy(() => import('./modules/clients/pages/ClientImportPage'));
const MobileAppPage = React.lazy(() => import('./pages/MobileAppPage'));
const MaterialDetailPage = React.lazy(() => import('./modules/inventory/pages/MaterialDetailPage'));
const SuppliersPage = React.lazy(() => import('./modules/procurement/pages/SuppliersPage'));
const ProductsPage = React.lazy(() => import('./modules/catalog/pages/ProductsPage'));
const ProductDetailPage = React.lazy(() => import('./modules/catalog/pages/ProductDetailPage'));
const ProductImportPage = React.lazy(() => import('./modules/catalog/pages/ProductImportPage'));
const MaterialImportPage = React.lazy(() => import('./modules/inventory/pages/MaterialImportPage'));
const CompanyHolidaysPage = React.lazy(() => import('./modules/hr/pages/CompanyHolidaysPage'));
const HolidayImportPage = React.lazy(() => import('./modules/hr/pages/HolidayImportPage'));
const EstimateImportPage = React.lazy(() => import('./modules/sales/pages/EstimateImportPage'));
const OrderImportPage = React.lazy(() => import('./modules/sales/pages/OrderImportPage'));
const RateCardsPage = React.lazy(() => import('./modules/catalog/pages/RateCardsPage'));
const RateCardImportPage = React.lazy(() => import('./modules/catalog/pages/RateCardImportPage'));
const SupplierDetailPage = React.lazy(() => import('./modules/procurement/pages/SupplierDetailPage'));
const PurchasesPage = React.lazy(() => import('./modules/procurement/pages/PurchasesPage'));
const PurchaseDetailPage = React.lazy(() => import('./modules/procurement/pages/PurchaseDetailPage'));
const ProcurementRequirementsPage = React.lazy(() => import('./modules/procurement/pages/ProcurementRequirementsPage'));
const ProcurementRequirementDetailPage = React.lazy(() => import('./modules/procurement/pages/ProcurementRequirementDetailPage'));
const IssuesPage = React.lazy(() => import('./modules/operations/pages/IssuesPage'));
const ClientsPage = React.lazy(() => import('./modules/clients/pages/ClientsPage'));
const ClientDetailPage = React.lazy(() => import('./modules/clients/pages/ClientDetailPage'));
const OrdersPage = React.lazy(() => import('./modules/sales/pages/OrdersPage'));
const OrderDetailPage = React.lazy(() => import('./modules/sales/pages/OrderDetailPage'));
const PaymentsPage = React.lazy(() => import('./modules/sales/pages/PaymentsPage'));
const ProjectExpensesPage = React.lazy(() => import('./modules/operations/pages/ProjectExpensesPage'));
const EmployeesPage = React.lazy(() => import('./modules/hr/pages/EmployeesPage'));
const EmployeeDetailPage = React.lazy(() => import('./modules/hr/pages/EmployeeDetailPage'));
const AttendancePage = React.lazy(() => import('./modules/hr/pages/AttendancePage'));
const LeavesPage = React.lazy(() => import('./modules/hr/pages/LeavesPage'));
const DailyTasksPage = React.lazy(() => import('./modules/operations/pages/DailyTasksPage'));
const TaskDetailPage = React.lazy(() => import('./modules/operations/pages/TaskDetailPage'));
const ProductionJobsPage = React.lazy(() => import('./modules/operations/pages/ProductionJobsPage'));
const ProductionJobDetailPage = React.lazy(() => import('./modules/operations/pages/ProductionJobDetailPage'));
const SettingsPage = React.lazy(() => import('./pages/SettingsPage'));
const EstimatesPage = React.lazy(() => import('./modules/sales/pages/EstimatesPage'));
const EstimateDetailPage = React.lazy(() => import('./modules/sales/pages/EstimateDetailPage'));
const CandidatesPage = React.lazy(() => import('./modules/recruitment/pages/CandidatesPage'));
const CandidateDetailPage = React.lazy(() => import('./modules/recruitment/pages/CandidateDetailPage'));
const InterviewsPage = React.lazy(() => import('./modules/recruitment/pages/InterviewsPage'));
const SalarySlipsPage = React.lazy(() => import('./modules/hr/pages/SalarySlipsPage'));
const SalaryAdvancesPage = React.lazy(() => import('./modules/hr/pages/SalaryAdvancesPage'));
const UsersPage = React.lazy(() => import('./pages/UsersPage'));
const AuditLogsPage = React.lazy(() => import('./pages/AuditLogsPage'));
const AnalyticsPage = React.lazy(() => import('./modules/reporting/pages/AnalyticsPage'));
const LearningCandidatesPage = React.lazy(() => import('./modules/ai/pages/LearningCandidatesPage'));

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
  const location = useLocation();

  useEffect(() => {
    authAPI
      .me()
      .then((res) => dispatch(sessionCheckFinished(res.data)))
      .catch(() => dispatch(sessionCheckFinished(null)));
  }, [dispatch]);

  // One place setting document.title for every route, rather than
  // each page doing it individually.
  useEffect(() => {
    setDocumentTitle(location.pathname);
  }, [location.pathname]);

  return (
    <Suspense fallback={null}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/dashboard" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/business-decisions" element={<Protected><BusinessDecisionCentrePage /></Protected>} />
      <Route path="/analytics" element={<Protected><AnalyticsPage /></Protected>} />
      <Route path="/inventory" element={<Protected><InventoryPage /></Protected>} />
      <Route path="/materials" element={<Protected><MaterialsPage /></Protected>} />
      <Route path="/materials/:materialId" element={<Protected><MaterialDetailPage /></Protected>} />
      <Route path="/locations" element={<Protected><LocationsPage /></Protected>} />
      <Route path="/purchases/import" element={<Protected><PurchaseImportPage /></Protected>} />
      <Route path="/clients/import" element={<Protected><ClientImportPage /></Protected>} />
      <Route path="/mobile-app" element={<Protected><MobileAppPage /></Protected>} />
      <Route path="/suppliers" element={<Protected><SuppliersPage /></Protected>} />
      <Route path="/products" element={<Protected><ProductsPage /></Protected>} />
      <Route path="/products/import" element={<Protected><ProductImportPage /></Protected>} />
      <Route path="/materials/import" element={<Protected><MaterialImportPage /></Protected>} />
      <Route path="/company-holidays" element={<Protected><CompanyHolidaysPage /></Protected>} />
      <Route path="/company-holidays/import" element={<Protected><HolidayImportPage /></Protected>} />
      <Route path="/estimates/import" element={<Protected><EstimateImportPage /></Protected>} />
      <Route path="/orders/import" element={<Protected><OrderImportPage /></Protected>} />
      <Route path="/rate-master" element={<Protected><RateCardsPage /></Protected>} />
      <Route path="/rate-master/import" element={<Protected><RateCardImportPage /></Protected>} />
      <Route path="/products/:productId" element={<Protected><ProductDetailPage /></Protected>} />
      <Route path="/suppliers/:supplierId" element={<Protected><SupplierDetailPage /></Protected>} />
      <Route path="/purchases" element={<Protected><PurchasesPage /></Protected>} />
      <Route path="/purchases/:purchaseId" element={<Protected><PurchaseDetailPage /></Protected>} />
      <Route path="/procurement-requirements" element={<Protected><ProcurementRequirementsPage /></Protected>} />
      <Route path="/procurement-requirements/:requirementId" element={<Protected><ProcurementRequirementDetailPage /></Protected>} />
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
      <Route path="/learning-candidates" element={<Protected><LearningCandidatesPage /></Protected>} />
      <Route path="/users" element={<Protected><UsersPage /></Protected>} />
      <Route path="/audit-logs" element={<Protected><AuditLogsPage /></Protected>} />
      <Route path="/estimates" element={<Protected><EstimatesPage /></Protected>} />
      <Route path="/estimates/:estimateId" element={<Protected><EstimateDetailPage /></Protected>} />
      <Route path="/candidates" element={<Protected><CandidatesPage /></Protected>} />
      <Route path="/candidates/:candidateId" element={<Protected><CandidateDetailPage /></Protected>} />
      <Route path="/interviews" element={<Protected><InterviewsPage /></Protected>} />
      <Route path="/salary-slips" element={<Protected><SalarySlipsPage /></Protected>} />
      <Route path="/salary-advances" element={<Protected><SalaryAdvancesPage /></Protected>} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
    </Suspense>
  );
}

// Keeps <html data-theme="..."> in sync with the theme slice so every
// themed CSS variable in styles/index.css resolves correctly - runs at
// the app root (not inside AppLayout) so the login/forgot-password
// screens' own themed bits (form inputs, focus rings) pick it up too,
// not just the authenticated app shell.
function useThemeSync() {
  const mode = useSelector((state) => state.theme.mode);
  useEffect(() => {
    if (mode === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }, [mode]);
}

function App() {
  useThemeSync();
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
