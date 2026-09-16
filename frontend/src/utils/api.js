import axios from 'axios';

// "localhost", not 127.0.0.1 - deliberately matching the frontend's own
// host (also "localhost", see start_frontend.sh/.bat and CRA's default
// dev server), not just its origin.
//
// Defect repair: this used to default to 127.0.0.1 specifically to
// route around a real Windows quirk (see the IPv6 note below) - but
// that traded a latency problem for a much worse correctness bug.
// Browsers scope a cookie's SameSite behavior to the "site" (registrable
// domain + scheme), and "localhost" and "127.0.0.1" are two different
// sites even though both mean loopback - a request from a page served
// on http://localhost:3000 to an API on http://127.0.0.1:8000 is
// CROSS-SITE, not just cross-origin. The auth cookie is set with
// SameSite=Lax (COOKIE_SAMESITE, see backend/app/platform/config.py) -
// correct and unchanged - and SameSite=Lax cookies are never attached
// to a cross-site XHR/fetch request, only to a top-level navigation.
// The Set-Cookie from POST /api/auth/login was still honored (login
// showed success), but every following API call - XHR, not a page
// navigation - silently went out with NO cookie attached at all,
// which is exactly the "logs in for a second, then every request
// comes back 401 and the app bounces back to /login" symptom this
// was reported as. Same host on both sides makes every request
// same-site (a different PORT alone does not change the site), so the
// cookie attaches normally again.
//
// The original Windows IPv6 concern (some Windows setups resolve
// "localhost" to the IPv6 loopback ::1 first, and a backend listening
// on IPv4 only would leave the browser to fall back to IPv4 after that
// first attempt) is real, but the correct fix for it is on the SERVER
// side, not by giving the two ends of the app different "site"
// identities: start_backend.sh/.bat now bind uvicorn to "::" (dual-
// stack), which - on both Windows (default since Vista) and Linux
// (default on virtually every distro) - accepts both ::1 and
// 127.0.0.1 connections on the one socket, so whichever address
// family "localhost" resolves to first, the backend answers
// immediately; there is no fallback delay to route around anymore.
// If IPv6 is ever genuinely disabled at the OS level on a given
// machine (rare, and not the default anywhere relevant here), the fix
// is a REACT_APP_API_URL override (see below), not reverting this
// default for everyone else.
//
// REACT_APP_API_URL remains a full override for any deployment (a
// real domain in staging/production, a different port, a machine
// where the above genuinely doesn't apply) - this default only governs
// local development with nothing set.
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// withCredentials sends/receives the HttpOnly auth cookie automatically.
// No token is ever read from or written to localStorage/sessionStorage.
const client = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Single-flight guard for the "an authenticated session just turned
// out to be invalid" event dispatched below. Many widgets can all get
// their 401 back in the same tick (e.g. a whole dashboard's worth of
// requests, all rejected together because the token expired while the
// page was open) - only the FIRST one should actually do anything;
// the rest are the exact same fact arriving redundantly, not N
// separate reasons to log out. Reset once a fresh login succeeds (see
// resetSessionInvalidationGuard, called from LoginPage) so a later,
// genuinely new invalidation of THAT session can still be caught.
let sessionInvalidationHandled = false;

export function resetSessionInvalidationGuard() {
  sessionInvalidationHandled = false;
}

// The one route that legitimately checks "is there a session at all"
// as its whole purpose (see App.jsx's bootstrap effect) - a 401 from
// this call is an expected, ordinary outcome (not logged in yet), and
// App.jsx already handles it precisely: dispatch(sessionCheckFinished
// (null)) followed by ProtectedRoute's own <Navigate to="/login" />.
// That is a normal, single, soft client-side redirect - this
// interceptor must not ALSO force a hard window.location redirect for
// the same 401, which would race the two against each other and throw
// away the SPA's own state for no reason.
const AUTH_BOOTSTRAP_PATH = '/api/auth/me';

// Defect repair (F138 P3): sensible, deliberate timeouts by request
// shape instead of one flat number for everything. The 30s default set
// on the client above already covers ordinary CRUD reasonably; the one
// documented exception is a large report/export/download
// (responseType: 'blob') - a real file, potentially large, generated
// server-side on demand, which deserves more room on a slow connection
// than a routine list/get. Only applied when the caller hasn't already
// set an explicit timeout of their own (authAPI.me's dedicated 8s stays
// untouched, since responseType isn't 'blob' there anyway).
client.interceptors.request.use((config) => {
  if (config.responseType === 'blob' && config.timeout === undefined) {
    config.timeout = 90000;
  }
  return config;
});

// Defect repair (F138 P3): network-aware GET handling - in-flight
// request de-duplication plus a small, bounded automatic retry with
// backoff. Deliberately GET-only. Retrying a POST/PUT/PATCH/DELETE
// automatically is NOT safe to do blindly here: if the original
// request actually reached the server and only the response was lost
// (a real possibility on a flaky connection, not just a hypothetical),
// silently retrying it risks creating a duplicate business record
// (a second order, a second payment). That decision has to stay a
// deliberate, explicit, per-feature choice - see utils/utils.js's
// queueWrite/replayQueue, which documents the identical principle for
// the offline write queue - never a blanket axios behavior applied to
// every mutation in the app.
const GET_RETRY_LIMIT = 2; // 3 attempts total, bounded - never unbounded, never a retry storm
const GET_RETRY_BASE_DELAY_MS = 500; // attempt 2 waits ~500ms, attempt 3 waits ~1000ms

function isRetryableGetFailure(error) {
  if ((error.config?.method || '').toLowerCase() !== 'get') return false;
  if (!error.response) return true; // no response at all: network error, timeout, connection refused, DNS failure
  // 502/503/504 are transient infrastructure failures a moment later
  // likely to succeed. Deliberately NOT 500 (a real application error
  // that retrying won't fix), NOT 429 (retrying immediately would only
  // add to the very load the rate limit exists to shed), and NOT
  // 401/403 (an authorization outcome, not a transient failure - see
  // the session-invalidation handling below, which already treats a
  // 401 as authoritative and must not be raced by a retry loop here).
  return [502, 503, 504].includes(error.response.status);
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Identical concurrent GETs (same method+url+params, fired from two
// widgets/components in the same tick - e.g. two components both
// wanting the same reference data at once) collapse into ONE real
// network request sharing one promise, rather than each firing its
// own. Never applied to mutations (see rawRequest below - only GET is
// routed through this wrapper).
const inFlightGets = new Map();

function getRequestKey(url, config) {
  const params = config?.params ? JSON.stringify(config.params) : '';
  return `${url}?${params}`;
}

const rawGet = client.get.bind(client);

async function networkAwareGet(url, config = {}) {
  const key = getRequestKey(url, config);
  const existing = inFlightGets.get(key);
  if (existing) {
    return existing;
  }
  const promise = (async () => {
    let attempt = 0;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      try {
        return await rawGet(url, config);
      } catch (error) {
        if (attempt >= GET_RETRY_LIMIT || !isRetryableGetFailure(error)) {
          throw error;
        }
        attempt += 1;
        await delay(GET_RETRY_BASE_DELAY_MS * attempt);
      }
    }
  })();
  inFlightGets.set(key, promise);
  try {
    return await promise;
  } finally {
    inFlightGets.delete(key);
  }
}

// Every existing `client.get(...)` call site in this file (and
// anywhere else `client`/the named *API objects are used) goes through
// this same method on this same shared instance, so both the
// deduplication and the bounded retry apply uniformly without having
// to individually rewrite ~150 call sites.
client.get = networkAwareGet;

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const onLoginPage = window.location.pathname === '/login';
    const isBootstrapCheck = error.config?.url === AUTH_BOOTSTRAP_PATH;

    if (status === 401 && !onLoginPage && !isBootstrapCheck) {
      // A 401 from any OTHER authenticated endpoint - reached only
      // after bootstrap has already confirmed a session exists - means
      // get_current_user (app/platform/security.py) has determined,
      // server-side and just now, that this specific request's token
      // is genuinely no longer valid: expired, issued before a
      // password reset, or the account was deleted. It is never a
      // permissions/role problem (that is a 403, not a 401) and never
      // a transient network hiccup (axios only reaches this branch for
      // a real HTTP 401 response - a timeout or dropped connection has
      // no error.response at all and is left alone below). So this
      // really is confirmation the session is invalid - the question
      // is only how many times to act on it when several requests
      // discover the same thing at once.
      if (!sessionInvalidationHandled) {
        sessionInvalidationHandled = true;
        // Dispatched as a browser event, not a direct Redux import
        // here, to keep this plain axios module decoupled from the
        // store - see App.jsx, which listens for this once, dispatches
        // the existing `logout` action (clears isAuthenticated/user),
        // and lets the SPA's own <ProtectedRoute> perform its normal
        // React Router redirect to /login - not a hard page reload,
        // and not a second, independent redirect path racing it.
        window.dispatchEvent(new CustomEvent('woodful:session-invalid'));
      }
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (identifier, password) => client.post('/api/auth/login', { identifier, password }),
  logout: () => client.post('/api/auth/logout'),
  // A shorter, dedicated timeout for this one call: it gates the
  // entire app's first paint (ProtectedRoute shows LoadingShell until
  // it settles), so it should fail fast rather than share the
  // general-purpose 30s client timeout meant for larger data
  // operations elsewhere in the app.
  me: () => client.get(AUTH_BOOTSTRAP_PATH, { timeout: 8000 }),
  forgotPassword: (identifier) => client.post('/api/auth/forgot-password', { identifier }),
  resetPassword: (token, newPassword) => client.post('/api/auth/reset-password', { token, new_password: newPassword }),
};

// Defect repair (P1-13): clientPortalAPI (Family 137 features 1 and 3 -
// the public, unauthenticated client-portal endpoints) removed.
// Woodful is internal-only now and the backend no longer serves
// /api/client-portal/* at all (see backend app/api/routes.py) - these
// calls would only ever 404.

export const dashboardAPI = {
  stock: () => client.get('/api/dashboard/stock'),
  orders: () => client.get('/api/dashboard/orders'),
  staff: () => client.get('/api/dashboard/staff'),
  atRiskOrders: () => client.get('/api/dashboard/at-risk-orders'),
  // Family 137, feature 12 - Forward Cash-Flow Forecast (EXPECTED /
  // ACTUAL / OVERDUE / FORECAST, weekly buckets).
  cashFlowForecast: (weeks) => client.get('/api/dashboard/cash-flow-forecast', { params: weeks ? { weeks } : {} }),
  // Family 137, feature 11 - Owner Daily/Weekly Business Briefing.
  ownerBriefing: (period) => client.get('/api/dashboard/owner-briefing', { params: { period: period || 'daily' } }),
};

export const businessDecisionsAPI = {
  list: () => client.get('/api/business-decisions/'),
  get: (entityType, entityId) => client.get(`/api/business-decisions/${entityType}/${entityId}`),
};

export const analyticsAPI = {
  sales: (months) => client.get('/api/analytics/sales', { params: { months } }),
  inventory: () => client.get('/api/analytics/inventory'),
  purchases: (months) => client.get('/api/analytics/purchases', { params: { months } }),
  production: () => client.get('/api/analytics/production'),
  projects: () => client.get('/api/analytics/projects'),
  tasks: () => client.get('/api/analytics/tasks'),
  payments: (months) => client.get('/api/analytics/payments', { params: { months } }),
  expenses: (months) => client.get('/api/analytics/expenses', { params: { months } }),
  workforce: () => client.get('/api/analytics/workforce'),
  operations: () => client.get('/api/analytics/operations'),
  alerts: () => client.get('/api/analytics/alerts'),
  whatsChanged: () => client.get('/api/analytics/whats-changed'),
};

export const suppliersAPI = {
  list: (params) => client.get('/api/suppliers/', { params }),
  get: (id) => client.get(`/api/suppliers/${id}`),
  create: (data) => client.post('/api/suppliers/', data),
  update: (id, data) => client.put(`/api/suppliers/${id}`, data),
  remove: (id) => client.delete(`/api/suppliers/${id}`),
};

export const materialsAPI = {
  list: (params) => client.get('/api/materials/', { params }),
  get: (id) => client.get(`/api/materials/${id}`),
  create: (data) => client.post('/api/materials/', data),
  update: (id, data) => client.put(`/api/materials/${id}`, data),
  remove: (id) => client.delete(`/api/materials/${id}`),
  // "Intelligent defaults" - existing backend interpreter,
  // just exposed to the material creation form.
  interpretName: (name) => client.get('/api/materials/interpret-name', { params: { name } }),
  // Family 137, feature 7 - Dead-Stock / Material-to-Design Matching.
  deadStockMatches: (idleDays) => client.get('/api/materials/dead-stock-matches', { params: idleDays ? { idle_days: idleDays } : {} }),
};

export const productsAPI = {
  list: (params) => client.get('/api/products/', { params }),
  get: (id) => client.get(`/api/products/${id}`),
  create: (data, confirmDuplicate = false) => client.post('/api/products/', data, { params: { confirm_duplicate: confirmDuplicate } }),
  update: (id, data) => client.put(`/api/products/${id}`, data),
  remove: (id) => client.delete(`/api/products/${id}`),
};

export const productImportAPI = {
  templateUrl: `${API_URL}/api/product-imports/template`,
  preview: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/product-imports/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  commit: (rows) => client.post('/api/product-imports/commit', { rows }),
  errorReport: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/product-imports/error-report', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, responseType: 'blob',
    });
  },
};

export const materialImportAPI = {
  templateUrl: `${API_URL}/api/material-imports/template`,
  preview: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/material-imports/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  commit: (rows) => client.post('/api/material-imports/commit', { rows }),
  errorReport: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/material-imports/error-report', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, responseType: 'blob',
    });
  },
};

export const estimateImportAPI = {
  templateUrl: `${API_URL}/api/estimate-imports/template`,
  preview: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/estimate-imports/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  commit: (estimates) => client.post('/api/estimate-imports/commit', { estimates }),
  errorReport: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/estimate-imports/error-report', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, responseType: 'blob',
    });
  },
};

export const orderImportAPI = {
  templateUrl: `${API_URL}/api/order-imports/template`,
  preview: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/order-imports/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  commit: (orders) => client.post('/api/order-imports/commit', { orders }),
  errorReport: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/order-imports/error-report', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, responseType: 'blob',
    });
  },
};

export const ratesAPI = {
  list: (params) => client.get('/api/rate-cards/', { params }),
  get: (id) => client.get(`/api/rate-cards/${id}`),
  history: (id) => client.get(`/api/rate-cards/${id}/history`),
  create: (data) => client.post('/api/rate-cards/', data),
  revise: (id, data) => client.put(`/api/rate-cards/${id}`, data),
  override: (id, data) => client.post(`/api/rate-cards/${id}/override`, data),
  deactivate: (id) => client.post(`/api/rate-cards/${id}/deactivate`),
};

export const rateImportAPI = {
  templateUrl: `${API_URL}/api/rate-card-imports/template`,
  preview: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/rate-card-imports/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  commit: (rows) => client.post('/api/rate-card-imports/commit', { rows }),
  errorReport: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/rate-card-imports/error-report', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, responseType: 'blob',
    });
  },
};

export const clientProductRateAPI = {
  list: (params) => client.get('/api/client-product-rates/', { params }),
  create: (data) => client.post('/api/client-product-rates/', data),
  update: (id, data) => client.put(`/api/client-product-rates/${id}`, data),
  remove: (id) => client.delete(`/api/client-product-rates/${id}`),
  resolve: (data) => client.post('/api/client-product-rates/resolve', data),
};

export const materialCategoriesAPI = {
  list: () => client.get('/api/material-categories/'),
  createCategory: (data) => client.post('/api/material-categories/', data),
  createSubcategory: (data) => client.post('/api/material-categories/subcategories', data),
  getSubcategory: (id) => client.get(`/api/material-categories/subcategories/${id}`),
  createAttribute: (subcategoryId, data) => client.post(`/api/material-categories/subcategories/${subcategoryId}/attributes`, data),
};

export const supplierMaterialsAPI = {
  byMaterial: (materialId) => client.get(`/api/supplier-materials/by-material/${materialId}`),
  bySupplier: (supplierId) => client.get(`/api/supplier-materials/by-supplier/${supplierId}`),
  create: (data) => client.post('/api/supplier-materials/', data),
  update: (id, data) => client.put(`/api/supplier-materials/${id}`, data),
  remove: (id) => client.delete(`/api/supplier-materials/${id}`),
};

export const stockAPI = {
  transfer: (data) => client.post('/api/stock/transfers', data),
  adjust: (data) => client.post('/api/stock/adjustments', data),
  locationStock: (materialId) => client.get(`/api/stock/locations/${materialId}`),
  // These two already existed on the
  // backend (app/api/routes/stock_transactions.py) with zero frontend
  // callers. Wiring them up here, not adding new endpoints.
  ledger: (materialId) => client.get('/api/stock/ledger', { params: { material_id: materialId } }),
  verify: (materialId) => client.get(`/api/stock/verify/${materialId}`),
};

export const holidaysAPI = {
  list: () => client.get('/api/working-calendar/holidays'),
  create: (data) => client.post('/api/working-calendar/holidays', data),
  update: (id, data) => client.put(`/api/working-calendar/holidays/${id}`, data),
  remove: (id) => client.delete(`/api/working-calendar/holidays/${id}`),
};

export const holidayImportAPI = {
  templateUrl: `${API_URL}/api/holiday-imports/template`,
  preview: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/holiday-imports/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  commit: (rows) => client.post('/api/holiday-imports/commit', { rows }),
  errorReport: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/holiday-imports/error-report', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, responseType: 'blob',
    });
  },
};

export const purchaseImportAPI = {
  templateUrl: `${API_URL}/api/purchase-imports/template`,
  preview: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/purchase-imports/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  commit: (rows) => client.post('/api/purchase-imports/commit', { rows }),
  errorReport: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/purchase-imports/error-report', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }, responseType: 'blob',
    });
  },
};

export const clientImportAPI = {
  templateUrl: `${API_URL}/api/client-imports/template`,
  preview: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/client-imports/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  commit: (rows) => client.post('/api/client-imports/commit', { rows }),
  errorReport: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post('/api/client-imports/error-report', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      responseType: 'blob',
    });
  },
};

export const personalCartAPI = {
  list: () => client.get('/api/personal-cart/'),
  add: (data) => client.post('/api/personal-cart/', data),
  update: (id, data) => client.put(`/api/personal-cart/${id}`, data),
  remove: (id) => client.delete(`/api/personal-cart/${id}`),
  clear: () => client.delete('/api/personal-cart/'),
};

export const locationsAPI = {
  list: (params) => client.get('/api/locations/', { params }),
  tree: () => client.get('/api/locations/tree'),
  get: (id) => client.get(`/api/locations/${id}`),
  create: (data) => client.post('/api/locations/', data),
};

export const notificationsAPI = {
  list: (params) => client.get('/api/notifications/', { params }),
  unreadCount: () => client.get('/api/notifications/unread-count'),
  markRead: (id) => client.put(`/api/notifications/${id}/read`),
  markAllRead: () => client.put('/api/notifications/read-all'),
};

export const purchasesAPI = {
  list: (params) => client.get('/api/purchases/', { params }),
  get: (id) => client.get(`/api/purchases/${id}`),
  create: (data) => client.post('/api/purchases/', data),
  update: (id, data) => client.put(`/api/purchases/${id}`, data),
  receive: (id) => client.post(`/api/purchases/${id}/receive`),
  remove: (id) => client.delete(`/api/purchases/${id}`),
  exportCart: (items) => client.post('/api/purchases/cart-export', { items }, { responseType: 'blob' }),
};

export const procurementRequirementsAPI = {
  list: (params) => client.get('/api/procurement-requirements/', { params }),
  get: (id) => client.get(`/api/procurement-requirements/${id}`),
  create: (data) => client.post('/api/procurement-requirements/', data),
  update: (id, data) => client.put(`/api/procurement-requirements/${id}`, data),
  supplierOptions: (id) => client.get(`/api/procurement-requirements/${id}/supplier-options`),
  recordDecision: (id, data) => client.post(`/api/procurement-requirements/${id}/decision`, data),
  createPurchase: (id, data) => client.post(`/api/procurement-requirements/${id}/purchase`, data),
};

export const issuesAPI = {
  list: (params) => client.get('/api/issues/', { params }),
  create: (data) => client.post('/api/issues/', data),
};

export const clientsAPI = {
  list: (params) => client.get('/api/clients/', { params }),
  get: (id) => client.get(`/api/clients/${id}`),
  create: (data) => client.post('/api/clients/', data),
  update: (id, data) => client.put(`/api/clients/${id}`, data),
  remove: (id) => client.delete(`/api/clients/${id}`),
  checkDuplicates: (name) => client.get('/api/clients/check-duplicates', { params: { name } }),
  // Family 137, feature 5 - Unified Client Relationship Timeline: a
  // presentation layer over existing estimates/orders/payments/
  // documents/activities/communications for this client, never a
  // second, duplicated timeline table.
  relationshipTimeline: (id, limit) =>
    client.get(`/api/clients/${id}/relationship-timeline`, { params: limit ? { limit } : {} }),
};

export const ordersAPI = {
  list: (params) => client.get('/api/orders/', { params }),
  get: (id) => client.get(`/api/orders/${id}`),
  create: (data) => client.post('/api/orders/', data),
  update: (id, data) => client.put(`/api/orders/${id}`, data),
  profitability: (id) => client.get(`/api/orders/${id}/profitability`),
  materialRequirements: (id) => client.get(`/api/orders/${id}/material-requirements`),
  // Deterministic, explainable Order Health/Risk (Family 130 P0.1) -
  // same authoritative computation the chatbot's "what is blocking
  // this order" query uses, exposed directly for the Order Detail
  // header - see OrderService.compute_order_health.
  health: (id) => client.get(`/api/orders/${id}/health`),
  aiReports: (id) => client.get(`/api/orders/${id}/ai-reports`),
  // Project communication: comments tied to this order,
  // and the merged chronological activity timeline (comments + task
  // comments for its tasks + milestones + relevant notifications).
  listComments: (id) => client.get(`/api/orders/${id}/comments`),
  addComment: (id, data) => client.post(`/api/orders/${id}/comments`, data),
  activity: (id, params) => client.get(`/api/orders/${id}/activity`, { params }),
  emailPreview: (id, kind) => client.get(`/api/orders/${id}/email-preview`, { params: { kind } }),
  sendEmail: (id, kind, data) => client.post(`/api/orders/${id}/send-email`, data, { params: { kind } }),
  // Family 137, feature 4 - Balance-Before-Dispatch Guardrail: read-only
  // precheck so the UI can explain an outstanding balance BEFORE the
  // person attempts to mark the order delivered/dispatched, not only
  // reject it after the fact.
  dispatchCheck: (id) => client.get(`/api/orders/${id}/dispatch-check`),
  // Family 137, feature 8 - Approved Specification / Sample Lock.
  listApprovedSpecifications: (id) => client.get(`/api/orders/${id}/approved-specifications`),
  approveSpecification: (id, data) => client.post(`/api/orders/${id}/approved-specifications`, data),
  // Family 137, feature 2 - Visual Build Timeline (Milestone +
  // ProductionJob status, reuses compute_order_health for risk).
  buildTimeline: (id) => client.get(`/api/orders/${id}/build-timeline`),
  // Family 137, feature 12 - Capacity-Aware Delivery Promise.
  // evaluateDeliveryPromise is read-only (a PREDICTION +
  // RECOMMENDATION); recordDeliveryPromise is the one place a human's
  // final promised date is actually written.
  evaluateDeliveryPromise: (id, requestedDate) =>
    client.get(`/api/orders/${id}/delivery-promise`, { params: { requested_date: requestedDate } }),
  recordDeliveryPromise: (id, data) => client.post(`/api/orders/${id}/delivery-promise`, data),
};

export const communicationAPI = {
  // Searches actual communication content (task/order
  // comments, client activity, notifications), not just master-record
  // names/codes like /api/search.
  search: (q) => client.get('/api/communication/search', { params: { q } }),
  // Rule-based extractive summary/action-items/unanswered-items over
  // an order's or client's recorded communication - never a real LLM,
  // see communication_ai_service.py.
  insights: (entityType, entityId) => client.post('/api/communication/insights', {
    entity_type: entityType, entity_id: entityId,
  }),
  // Template-filled draft for the user to review and send themselves -
  // nothing is ever sent automatically.
  draft: (entityType, entityId, purpose, detail) => client.post('/api/communication/draft', {
    entity_type: entityType, entity_id: entityId, purpose, detail,
  }),
  // Master-only: view the central Woodful sender identity/configuration
  // status (never the password) and send a real test email through the
  // same EmailService every business email uses.
  emailStatus: () => client.get('/api/communication/email-status'),
  sendTestEmail: (recipientEmail) => client.post('/api/communication/email-test', { recipient_email: recipientEmail }),
};

export const paymentsAPI = {
  list: (params) => client.get('/api/payments/', { params }),
  get: (id) => client.get(`/api/payments/${id}`),
  create: (data) => client.post('/api/payments/', data),
  update: (id, data) => client.put(`/api/payments/${id}`, data),
  remove: (id) => client.delete(`/api/payments/${id}`),
  emailPreview: (id) => client.get(`/api/payments/${id}/email-preview`),
  sendEmail: (id, data) => client.post(`/api/payments/${id}/send-email`, data),
};

export const projectExpensesAPI = {
  list: (params) => client.get('/api/project-expenses/', { params }),
  create: (data) => client.post('/api/project-expenses/', data),
  update: (id, data) => client.put(`/api/project-expenses/${id}`, data),
};

export const employeesAPI = {
  list: (params) => client.get('/api/employees/', { params }),
  get: (id) => client.get(`/api/employees/${id}`),
  create: (data) => client.post('/api/employees/', data),
  update: (id, data) => client.put(`/api/employees/${id}`, data),
  remove: (id) => client.delete(`/api/employees/${id}`),
  // Family 137 - Employee 360 / HR Command Center (section 13).
  overview360: (id) => client.get(`/api/employees/${id}/360-overview`),
  workload: (id) => client.get(`/api/employees/${id}/workload`),
  relationships: (id) => client.get(`/api/employees/${id}/relationships`),
  calendar: (id, year, month) => client.get(`/api/employees/${id}/calendar`, { params: { year, month } }),
  activityTimeline: (id, limit) => client.get(`/api/employees/${id}/activity-timeline`, { params: { limit } }),
  lifecycle: (id, phase) => client.get(`/api/employees/${id}/lifecycle`, { params: { phase } }),
  updateLifecycleItem: (id, itemId, data) => client.put(`/api/employees/${id}/lifecycle/${itemId}`, data),
};

export const attendanceAPI = {
  list: (params) => client.get('/api/attendance/', { params }),
  create: (data) => client.post('/api/attendance/', data),
  update: (id, data) => client.put(`/api/attendance/${id}`, data),
  overtime: (data) => client.post('/api/attendance/overtime', data),
  // Attendance & Overtime Command Center (calendar-first redesign):
  // one call per view, all backend-aggregated - never every record
  // fetched client-side and reduced in the browser.
  periodSummary: (employeeId, start, end) =>
    client.get('/api/attendance/period-summary', { params: { employee_id: employeeId, start, end } }),
  dayDetail: (employeeId, date) =>
    client.get('/api/attendance/day-detail', { params: { employee_id: employeeId, date } }),
  teamGrid: (start, end, department) =>
    client.get('/api/attendance/team-grid', { params: { start, end, department } }),
  exceptions: (start, end, employeeId) =>
    client.get('/api/attendance/exceptions', { params: { start, end, employee_id: employeeId } }),
};

export const overtimeRequestsAPI = {
  list: (params) => client.get('/api/overtime-requests/', { params }),
  create: (data) => client.post('/api/overtime-requests/', data),
  update: (id, data) => client.put(`/api/overtime-requests/${id}`, data),
  submit: (id) => client.post(`/api/overtime-requests/${id}/submit`),
  approve: (id, data) => client.put(`/api/overtime-requests/${id}/approve`, data || {}),
  reject: (id, data) => client.put(`/api/overtime-requests/${id}/reject`, data || {}),
  remove: (id) => client.delete(`/api/overtime-requests/${id}`),
};

export const leavesAPI = {
  list: (params) => client.get('/api/leaves/', { params }),
  create: (data) => client.post('/api/leaves/', data),
  update: (id, data) => client.put(`/api/leaves/${id}`, data),
};

export const dailyTasksAPI = {
  list: (params) => client.get('/api/daily-tasks/', { params }),
  get: (id) => client.get(`/api/daily-tasks/${id}`),
  create: (data) => client.post('/api/daily-tasks/', data),
  update: (id, data) => client.put(`/api/daily-tasks/${id}`, data),
  completeAndAssignNext: (id, data) => client.post(`/api/daily-tasks/${id}/complete-and-assign-next`, data),
  listComments: (id) => client.get(`/api/daily-tasks/${id}/comments`),
  addComment: (id, data) => client.post(`/api/daily-tasks/${id}/comments`, data),
  sendEmail: (id) => client.post(`/api/daily-tasks/${id}/send-email`),
};

export const productionJobsAPI = {
  list: (params) => client.get('/api/production-jobs/', { params }),
  get: (id) => client.get(`/api/production-jobs/${id}`),
  create: (data) => client.post('/api/production-jobs/', data),
  update: (id, data) => client.put(`/api/production-jobs/${id}`, data),
  readiness: (id) => client.get(`/api/production-jobs/${id}/readiness`),
  materialStatus: (id) => client.get(`/api/production-jobs/${id}/material-status`),
  variance: (id) => client.get(`/api/production-jobs/${id}/variance`),
  risks: (id) => client.get(`/api/production-jobs/${id}/risks`),
  cutList: (id) => client.get(`/api/production-jobs/${id}/cut-list`),
  nesting: (id, params) => client.get(`/api/production-jobs/${id}/nesting`, { params }),
};

export const productionOperationsAPI = {
  list: (params) => client.get('/api/production-operations/', { params }),
  get: (id) => client.get(`/api/production-operations/${id}`),
  create: (data) => client.post('/api/production-operations/', data),
  update: (id, data) => client.put(`/api/production-operations/${id}`, data),
};

export const cuttingRequirementsAPI = {
  list: (params) => client.get('/api/cutting-requirements/', { params }),
  get: (id) => client.get(`/api/cutting-requirements/${id}`),
  create: (data) => client.post('/api/cutting-requirements/', data),
  update: (id, data) => client.put(`/api/cutting-requirements/${id}`, data),
  remove: (id) => client.delete(`/api/cutting-requirements/${id}`),
};

export const workCentresAPI = {
  list: (params) => client.get('/api/work-centres/', { params }),
  get: (id) => client.get(`/api/work-centres/${id}`),
  create: (data) => client.post('/api/work-centres/', data),
  update: (id, data) => client.put(`/api/work-centres/${id}`, data),
  capacity: (id, date) => client.get(`/api/work-centres/${id}/capacity`, { params: date ? { date } : {} }),
};

export const settingsAPI = {
  types: () => client.get('/api/settings/'),
  list: (lookupType) => client.get(`/api/settings/${lookupType}`),
  create: (lookupType, data) => client.post(`/api/settings/${lookupType}`, data),
  update: (lookupType, id, data) => client.put(`/api/settings/${lookupType}/${id}`, data),
  remove: (lookupType, id) => client.delete(`/api/settings/${lookupType}/${id}`),
};

export const estimatesAPI = {
  list: (params) => client.get('/api/estimates/', { params }),
  get: (id) => client.get(`/api/estimates/${id}`),
  create: (data) => client.post('/api/estimates/', data),
  update: (id, data) => client.put(`/api/estimates/${id}`, data),
  revise: (id) => client.post(`/api/estimates/${id}/revise`),
  versions: (id) => client.get(`/api/estimates/${id}/versions`),
  emailPreview: (id) => client.get(`/api/estimates/${id}/email-preview`),
  sendEmail: (id, data) => client.post(`/api/estimates/${id}/send-email`, data),
  // Family 137, feature 9 - Cost-Drift Alert: read-only comparison of
  // quote-time cost basis vs current cost, never mutates the estimate.
  costDrift: (id) => client.get(`/api/estimates/${id}/cost-drift`),
  // Family 137, feature 6 - Smart Estimate / Margin Optimization.
  marginOptimization: (id, data) => client.post(`/api/estimates/${id}/margin-optimization`, data),
};

export const clientActivitiesAPI = {
  list: (params) => client.get('/api/client-activities/', { params }),
  create: (data) => client.post('/api/client-activities/', data),
  update: (id, data) => client.put(`/api/client-activities/${id}`, data),
  remove: (id) => client.delete(`/api/client-activities/${id}`),
  pendingFollowUps: (params) => client.get('/api/client-activities/follow-ups', { params }),
  completeFollowUp: (id) => client.patch(`/api/client-activities/${id}/complete-follow-up`),
};

export const candidatesAPI = {
  list: (params) => client.get('/api/candidates/', { params }),
  get: (id) => client.get(`/api/candidates/${id}`),
  create: (data) => client.post('/api/candidates/', data),
  update: (id, data) => client.put(`/api/candidates/${id}`, data),
  uploadResume: (id, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post(`/api/candidates/${id}/resume`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  resumeDownloadUrl: (id) => `${API_URL}/api/candidates/${id}/resume`,
  deleteResume: (id) => client.delete(`/api/candidates/${id}/resume`),
};

export const interviewsAPI = {
  list: (params) => client.get('/api/interviews/', { params }),
  create: (data) => client.post('/api/interviews/', data),
  update: (id, data) => client.put(`/api/interviews/${id}`, data),
};

export const salarySlipsAPI = {
  list: (params) => client.get('/api/salary-slips/', { params }),
  create: (data) => client.post('/api/salary-slips/', data),
  update: (id, data) => client.put(`/api/salary-slips/${id}`, data),
  attendanceSummary: (employeeId, month, year) =>
    client.get('/api/salary-slips/attendance-summary', { params: { employee_id: employeeId, month, year } }),
  payrollSummary: (month, year) => client.get('/api/salary-slips/payroll-summary', { params: { month, year } }),
};

export const salaryAdvancesAPI = {
  list: (params) => client.get('/api/salary-advances/', { params }),
  get: (id) => client.get(`/api/salary-advances/${id}`),
  create: (data) => client.post('/api/salary-advances/', data),
  approve: (id, data) => client.put(`/api/salary-advances/${id}/approve`, data),
  reject: (id, data) => client.put(`/api/salary-advances/${id}/reject`, data),
  recover: (id, data) => client.post(`/api/salary-advances/${id}/recover`, data),
};

export const searchAPI = {
  query: (q) => client.get('/api/search/', { params: { q } }),
};

export const chatAPI = {
  send: (message, context) => client.post('/api/chat/', { message, context }),
  learningCandidates: (status = 'pending') => client.get('/api/chat/learning-candidates', { params: { status } }),
  approveLearningCandidate: (id) => client.post(`/api/chat/learning-candidates/${id}/approve`),
  rejectLearningCandidate: (id) => client.post(`/api/chat/learning-candidates/${id}/reject`),
};

export const usersAPI = {
  list: (params) => client.get('/api/users/', { params }),
  create: (data) => client.post('/api/users/', data),
  update: (id, data) => client.put(`/api/users/${id}`, data),
  remove: (id) => client.delete(`/api/users/${id}`),
};

export const auditLogsAPI = {
  list: (params) => client.get('/api/audit-logs/', { params }),
};

export const reportsAPI = {
  downloadUrl: (path) => `${API_URL}/api/reports/${path}`,
};

export const documentsAPI = {
  list: (parentType, parentId) => client.get(`/api/documents/${parentType}/${parentId}`),
  upload: (parentType, parentId, file, description, extra = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    if (description) formData.append('description', description);
    // Family 137 (Employee 360, section 13.8) - optional categorization/
    // expiry metadata, shared by every parent type via the same generic
    // document endpoint (not employee-only). Omitted entirely unless a
    // caller passes one, so every pre-existing call site is unaffected.
    if (extra.documentType) formData.append('document_type', extra.documentType);
    if (extra.issueDate) formData.append('issue_date', extra.issueDate);
    if (extra.expiryDate) formData.append('expiry_date', extra.expiryDate);
    return client.post(`/api/documents/${parentType}/${parentId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  downloadUrl: (parentType, parentId, documentId) =>
    `${API_URL}/api/documents/${parentType}/${parentId}/${documentId}/download`,
  remove: (parentType, parentId, documentId) =>
    client.delete(`/api/documents/${parentType}/${parentId}/${documentId}`),
};

export const clientDocumentsAPI = {
  list: (clientId) => client.get(`/api/clients/${clientId}/documents`),
  upload: (clientId, file, description) => {
    const formData = new FormData();
    formData.append('file', file);
    if (description) formData.append('description', description);
    return client.post(`/api/clients/${clientId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  downloadUrl: (clientId, documentId) => `${API_URL}/api/clients/${clientId}/documents/${documentId}/download`,
  remove: (clientId, documentId) => client.delete(`/api/clients/${clientId}/documents/${documentId}`),
};

export const paymentDocumentsAPI = {
  list: (paymentId) => client.get(`/api/payments/${paymentId}/documents`),
  upload: (paymentId, file, description) => {
    const formData = new FormData();
    formData.append('file', file);
    if (description) formData.append('description', description);
    return client.post(`/api/payments/${paymentId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  downloadUrl: (paymentId, documentId) => `${API_URL}/api/payments/${paymentId}/documents/${documentId}/download`,
  remove: (paymentId, documentId) => client.delete(`/api/payments/${paymentId}/documents/${documentId}`),
};

export default client;
