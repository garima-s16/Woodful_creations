import React, { Suspense, useEffect, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';

import { authAPI } from './utils/api';
import { setDocumentTitle } from './utils/utils';
import { sessionCheckFinished, sessionCheckFailed, logout as logoutAction } from './redux/slices';
import { openCart, closeCart, fetchCart, resetCartView } from './redux/slices';

import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import { MobileBottomNav } from './components/Navigation';
import { ProtectedRoute } from './components/Infrastructure';
import { LoadingShell } from './components/Infrastructure';
import { OfflineBanner } from './components/Infrastructure';
import { ChatWidget } from './components/Assistant';
import { Footer } from './components/Navigation';
import { CartDrawer } from './modules/procurement/pages/RequirementsCartPages';

import { LoginPage, ForgotPasswordPage, ResetPasswordPage } from './modules/auth/pages/AuthPages';
import { NotFoundPage } from './pages/SystemPages';

const PUBLIC_ROUTES = ['/login', '/forgot-password', '/reset-password'];
// These two carry a :token URL param, so they can't be exact-matched
// against PUBLIC_ROUTES the way the fixed-path ones above are -
// checked separately below wherever PUBLIC_ROUTES is checked.
const PUBLIC_ROUTE_PREFIXES = ['/review-estimate/', '/my-order/'];
const EstimateReviewPage = React.lazy(() => import('./modules/clients/pages/ClientPortalPages').then(m => ({ default: m.EstimateReviewPage })));
const MyOrderPage = React.lazy(() => import('./modules/clients/pages/ClientPortalPages').then(m => ({ default: m.MyOrderPage })));
const DashboardPage = React.lazy(() => import('./modules/reporting/pages/DashboardPage'));
const BusinessDecisionCentrePage = React.lazy(() => import('./modules/reporting/pages/AnalyticsPages').then(m => ({ default: m.BusinessDecisionCentrePage })));
const OwnerBriefingPage = React.lazy(() => import('./modules/reporting/pages/AnalyticsPages').then(m => ({ default: m.OwnerBriefingPage })));
const InventoryPage = React.lazy(() => import('./modules/inventory/pages/InventoryPages').then(m => ({ default: m.InventoryPage })));
const MaterialsPage = React.lazy(() => import('./modules/inventory/pages/InventoryPages').then(m => ({ default: m.MaterialsPage })));
const LocationsPage = React.lazy(() => import('./modules/inventory/pages/MaterialPages').then(m => ({ default: m.LocationsPage })));
const PurchaseImportPage = React.lazy(() => import('./modules/procurement/pages/ProcurementPages').then(m => ({ default: m.PurchaseImportPage })));
const ClientImportPage = React.lazy(() => import('./modules/clients/pages/ClientPages').then(m => ({ default: m.ClientImportPage })));
const MobileAppPage = React.lazy(() => import('./pages/SystemPages').then(m => ({ default: m.MobileAppPage })));
const MaterialDetailPage = React.lazy(() => import('./modules/inventory/pages/MaterialPages').then(m => ({ default: m.MaterialDetailPage })));
const SuppliersPage = React.lazy(() => import('./modules/procurement/pages/ProcurementPages').then(m => ({ default: m.SuppliersPage })));
const ProductsPage = React.lazy(() => import('./modules/catalog/pages/CatalogPages').then(m => ({ default: m.ProductsPage })));
const ProductDetailPage = React.lazy(() => import('./modules/catalog/pages/CatalogPages').then(m => ({ default: m.ProductDetailPage })));
const ProductImportPage = React.lazy(() => import('./modules/catalog/pages/CatalogPages').then(m => ({ default: m.ProductImportPage })));
const MaterialImportPage = React.lazy(() => import('./modules/inventory/pages/MaterialPages').then(m => ({ default: m.MaterialImportPage })));
const CompanyHolidaysPage = React.lazy(() => import('./modules/hr/pages/WorkforcePages').then(m => ({ default: m.CompanyHolidaysPage })));
const HolidayImportPage = React.lazy(() => import('./modules/hr/pages/WorkforcePages').then(m => ({ default: m.HolidayImportPage })));
const EstimateImportPage = React.lazy(() => import('./modules/sales/pages/SalesSupportPages').then(m => ({ default: m.EstimateImportPage })));
const OrderImportPage = React.lazy(() => import('./modules/sales/pages/SalesSupportPages').then(m => ({ default: m.OrderImportPage })));
const RateCardsPage = React.lazy(() => import('./modules/catalog/pages/CatalogPages').then(m => ({ default: m.RateCardsPage })));
const RateCardImportPage = React.lazy(() => import('./modules/catalog/pages/CatalogPages').then(m => ({ default: m.RateCardImportPage })));
const SupplierDetailPage = React.lazy(() => import('./modules/procurement/pages/ProcurementPages').then(m => ({ default: m.SupplierDetailPage })));
const PurchasesPage = React.lazy(() => import('./modules/procurement/pages/ProcurementPages').then(m => ({ default: m.PurchasesPage })));
const PurchaseDetailPage = React.lazy(() => import('./modules/procurement/pages/ProcurementPages').then(m => ({ default: m.PurchaseDetailPage })));
const ProcurementRequirementsPage = React.lazy(() => import('./modules/procurement/pages/RequirementsCartPages').then(m => ({ default: m.ProcurementRequirementsPage })));
const ProcurementRequirementDetailPage = React.lazy(() => import('./modules/procurement/pages/RequirementsCartPages').then(m => ({ default: m.ProcurementRequirementDetailPage })));
const IssuesPage = React.lazy(() => import('./modules/operations/pages/OperationsPages').then(m => ({ default: m.IssuesPage })));
const ClientsPage = React.lazy(() => import('./modules/clients/pages/ClientPages').then(m => ({ default: m.ClientsPage })));
const ClientDetailPage = React.lazy(() => import('./modules/clients/pages/ClientDetailPage'));
const OrdersPage = React.lazy(() => import('./modules/sales/pages/SalesListPages').then(m => ({ default: m.OrdersPage })));
const OrderDetailPage = React.lazy(() => import('./modules/sales/pages/SalesDetailPages').then(m => ({ default: m.OrderDetailPage })));
const PaymentsPage = React.lazy(() => import('./modules/sales/pages/SalesSupportPages').then(m => ({ default: m.PaymentsPage })));
const ProjectExpensesPage = React.lazy(() => import('./modules/operations/pages/OperationsPages').then(m => ({ default: m.ProjectExpensesPage })));
const EmployeesPage = React.lazy(() => import('./modules/hr/pages/WorkforcePages').then(m => ({ default: m.EmployeesPage })));
const EmployeeDetailPage = React.lazy(() => import('./modules/hr/pages/WorkforcePages').then(m => ({ default: m.EmployeeDetailPage })));
const AttendancePage = React.lazy(() => import('./modules/hr/pages/WorkforcePages').then(m => ({ default: m.AttendancePage })));
const LeavesPage = React.lazy(() => import('./modules/hr/pages/WorkforcePages').then(m => ({ default: m.LeavesPage })));
const DailyTasksPage = React.lazy(() => import('./modules/operations/pages/OperationsPages').then(m => ({ default: m.DailyTasksPage })));
const TaskDetailPage = React.lazy(() => import('./modules/operations/pages/OperationsPages').then(m => ({ default: m.TaskDetailPage })));
const ProductionJobsPage = React.lazy(() => import('./modules/operations/pages/ProductionPages').then(m => ({ default: m.ProductionJobsPage })));
const ProductionJobDetailPage = React.lazy(() => import('./modules/operations/pages/ProductionPages').then(m => ({ default: m.ProductionJobDetailPage })));
const SettingsPage = React.lazy(() => import('./pages/SystemPages').then(m => ({ default: m.SettingsPage })));
const EstimatesPage = React.lazy(() => import('./modules/sales/pages/SalesListPages').then(m => ({ default: m.EstimatesPage })));
const EstimateDetailPage = React.lazy(() => import('./modules/sales/pages/SalesDetailPages').then(m => ({ default: m.EstimateDetailPage })));
const CandidatesPage = React.lazy(() => import('./modules/recruitment/pages/RecruitmentPages').then(m => ({ default: m.CandidatesPage })));
const CandidateDetailPage = React.lazy(() => import('./modules/recruitment/pages/RecruitmentPages').then(m => ({ default: m.CandidateDetailPage })));
const InterviewsPage = React.lazy(() => import('./modules/recruitment/pages/RecruitmentPages').then(m => ({ default: m.InterviewsPage })));
const SalarySlipsPage = React.lazy(() => import('./modules/hr/pages/PayrollPages').then(m => ({ default: m.SalarySlipsPage })));
const SalaryAdvancesPage = React.lazy(() => import('./modules/hr/pages/PayrollPages').then(m => ({ default: m.SalaryAdvancesPage })));
const UsersPage = React.lazy(() => import('./modules/auth/pages/AuthPages').then(m => ({ default: m.UsersPage })));
const AuditLogsPage = React.lazy(() => import('./pages/SystemPages').then(m => ({ default: m.AuditLogsPage })));
const AnalyticsPage = React.lazy(() => import('./modules/reporting/pages/AnalyticsPages').then(m => ({ default: m.AnalyticsPage })));
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
      <OfflineBanner />
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

  const initialPathname = useRef(location.pathname);
  useEffect(() => {
    if (PUBLIC_ROUTES.includes(initialPathname.current) || PUBLIC_ROUTE_PREFIXES.some((p) => initialPathname.current.startsWith(p))) {
      // No auth state is needed to render these pages - skip the
      // network round-trip entirely rather than firing it on every
      // page load just to discard the result. loginSuccess (fired on
      // an actual successful login from LoginPage) independently sets
      // checkingSession=false, so this can never leave the app stuck
      // "checking" once the user does log in. Runs once on mount only
      // (checking the route present at initial load, not on every
      // subsequent navigation) - the auth bootstrap is a one-time
      // startup concern, not something to redo on every page change.
      dispatch(sessionCheckFinished(null));
      return;
    }
    authAPI
      .me()
      .then((res) => dispatch(sessionCheckFinished(res.data)))
      .catch((err) => {
        // A real 401/403 means the server IS reachable and has
        // genuinely determined there's no valid session - that's the
        // normal "not logged in" case. Anything else here (timeout,
        // DNS failure, connection refused) means the request never
        // got a server response at all, which is a different,
        // actionable problem the person should be told about rather
        // than silently redirected to the login page as if they'd
        // simply logged out.
        const isAuthResponse = err.response?.status === 401 || err.response?.status === 403;
        if (isAuthResponse) {
          dispatch(sessionCheckFinished(null));
        } else {
          dispatch(sessionCheckFailed());
        }
      });
  }, [dispatch]);

  // One place setting document.title for every route, rather than
  // each page doing it individually.
  useEffect(() => {
    setDocumentTitle(location.pathname);
  }, [location.pathname]);

  return (
    <Suspense fallback={<LoadingShell />}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/review-estimate/:token" element={<EstimateReviewPage />} />
      <Route path="/my-order/:token" element={<MyOrderPage />} />
      <Route path="/" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/dashboard" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/business-decisions" element={<Protected><BusinessDecisionCentrePage /></Protected>} />
      <Route path="/owner-briefing" element={<Protected><OwnerBriefingPage /></Protected>} />
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
