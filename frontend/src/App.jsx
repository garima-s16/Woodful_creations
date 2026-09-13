import React, { Suspense, useEffect, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
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
import { Footer } from './components/Navigation';

import { LoginPage, ForgotPasswordPage, ResetPasswordPage } from './modules/auth/pages/AuthPages';
import { NotFoundPage } from './pages/SystemPages';

// Defect repair (F138 P1): ChatWidget (components/Assistant.jsx, 600+
// lines - the Cai assistant UI) and CartDrawer
// (modules/procurement/pages/RequirementsCartPages.jsx) used to be
// static imports here. Both only ever render inside AppLayout - i.e.
// only after a successful login - so requiring their code before the
// login page can even paint was pure waste on a slow connection.
// Lazy-loading them splits that code into its own chunk, fetched only
// once the authenticated shell actually mounts; a null Suspense
// fallback is correct here (unlike a route page) since both are
// floating overlays with no meaningful "loading" appearance of their
// own - the rest of the already-rendered shell stays fully usable
// while they load in.
const ChatWidget = React.lazy(() => import('./components/Assistant').then(m => ({ default: m.ChatWidget })));
const CartDrawer = React.lazy(() => import('./modules/procurement/pages/RequirementsCartPages').then(m => ({ default: m.CartDrawer })));

const PUBLIC_ROUTES = ['/login', '/forgot-password', '/reset-password'];
// Defect repair (P1-13): this used to also list the two public,
// token-based client-portal route prefixes (/review-estimate/,
// /my-order/). Woodful is internal-only now and the backend no
// longer serves /api/client-portal/* at all (see backend
// app/api/routes.py) - those pages and their routes below are
// removed, and this stays an empty array rather than being deleted
// outright since both places below that check it are otherwise
// generic and would need no change if a future prefix-matched public
// route is ever added again.
const PUBLIC_ROUTE_PREFIXES = [];
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
// IA consolidation: AttendanceLeaveHub is the single "Attendance &
// Leave" nav destination, combining Attendance/LeavesPage/
// CompanyHolidaysPage (all three still lazy-loaded together as part
// of the same WorkforcePages chunk they already belonged to - no new
// chunk, no duplicate implementation).
const AttendanceLeaveHub = React.lazy(() => import('./modules/hr/pages/WorkforcePages').then(m => ({ default: m.AttendanceLeaveHub })));
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
// IA consolidation: RecruitmentHub is the single "Recruitment" nav
// destination, combining CandidatesPage/InterviewsPage (same
// RecruitmentPages chunk, no duplicate implementation).
const RecruitmentHub = React.lazy(() => import('./modules/recruitment/pages/RecruitmentPages').then(m => ({ default: m.RecruitmentHub })));
const SalarySlipsPage = React.lazy(() => import('./modules/hr/pages/PayrollPages').then(m => ({ default: m.SalarySlipsPage })));
const SalaryAdvancesPage = React.lazy(() => import('./modules/hr/pages/PayrollPages').then(m => ({ default: m.SalaryAdvancesPage })));
// Defect repair (F138 P1): now its own file (see UsersPage.jsx's own
// comment) - this import previously pointed at AuthPages.jsx, the
// same module LoginPage is statically imported from above, which
// silently defeated this lazy() wrapper (webpack already had the
// whole module in the main bundle because of that static import).
const UsersPage = React.lazy(() => import('./modules/auth/pages/UsersPage'));
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
      {/* Defect repair (F138 P1): null fallback is deliberate - these
          are floating overlays (chat bubble, cart drawer), not page
          content, so there is nothing meaningful to show while their
          lazy chunk loads and no reason to block the rest of the
          already-rendered shell above on it. */}
      <Suspense fallback={null}>
        <ChatWidget />
        <CartDrawer open={isCartOpen} onClose={() => dispatch(closeCart())} />
      </Suspense>
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
  // Guards against React 18 StrictMode's deliberate dev-only double-
  // invoke of effects (mount -> cleanup -> mount again, on every
  // component in the tree, specifically to surface effects that
  // aren't safe to run twice). Without this, the very first page load
  // in development fires authAPI.me() TWICE back-to-back - harmless to
  // the server (it's an idempotent GET, and get_current_user doesn't
  // mutate anything), but it is real duplicate network work, and (per
  // this defect repair) exactly the kind of thing that made an
  // already-confusing login bug look even more erratic in the
  // browser's network log. hasStartedBootstrap is a ref (not state) so
  // checking and setting it can't itself trigger a re-render/re-run;
  // it starts false once per real mount of this component (the app
  // root is mounted exactly once for the SPA's lifetime - client-side
  // route changes never remount AppRoutes), so this remains "exactly
  // one bootstrap call per normal page load," StrictMode or not.
  const hasStartedBootstrap = useRef(false);

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
    if (hasStartedBootstrap.current) {
      return;
    }
    hasStartedBootstrap.current = true;
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

  // A 401 from an ordinary authenticated request (any endpoint other
  // than the bootstrap /api/auth/me check above - see utils/api.js's
  // response interceptor, which is what actually decides that and
  // dispatches this event, deduplicated, when it happens) means the
  // session has genuinely become invalid since bootstrap confirmed it.
  // Reusing the existing `logout` reducer here (not a hard
  // window.location redirect) sets isAuthenticated/user back to
  // signed-out state and lets <ProtectedRoute> below perform its own
  // ordinary React Router redirect to /login - a single, soft, in-SPA
  // navigation, not a full page reload racing a second one.
  useEffect(() => {
    const handleSessionInvalid = () => dispatch(logoutAction());
    window.addEventListener('woodful:session-invalid', handleSessionInvalid);
    return () => window.removeEventListener('woodful:session-invalid', handleSessionInvalid);
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
      {/* Dashboard -> Home rename: the existing DashboardPage is the
          single Home/Command Centre implementation, rendered at both
          "/" and the final user-facing "/home" route - no second
          implementation, no duplicate data loading. "/dashboard" is
          kept only as a backward-compatible redirect to "/home" so
          any existing bookmarks/links keep working. */}
      <Route path="/" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/home" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/dashboard" element={<Navigate to="/home" replace />} />
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
      {/* IA consolidation: single "Attendance & Leave" workspace nav
          destination. /attendance, /leaves, /company-holidays above
          and below are untouched and still directly reachable. */}
      <Route path="/attendance-leave" element={<Protected><AttendanceLeaveHub /></Protected>} />
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
      {/* IA consolidation: single "Recruitment" workspace nav
          destination. /candidates, /candidates/:id, and /interviews
          above are untouched and still directly reachable. */}
      <Route path="/recruitment" element={<Protected><RecruitmentHub /></Protected>} />
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
