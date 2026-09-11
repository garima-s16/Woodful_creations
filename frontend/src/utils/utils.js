// Non-API utilities: currency/number/date formatting, status
// classes, load-error classification, offline write-queue,
// document-title-from-path, and theme resolution. Combines the
// former format.js, loadError.js, offlineQueue.js, pageTitle.js,
// and theme.js.

import client from './api';

// --- format.js ---
/**
 * Shared display-formatting utilities - currency/number formatting,
 * date defaults, and status-to-badge-class mapping. Consolidated
 * because all three are the same kind of thing (a raw value in,
 * a display-ready presentation out) used across many pages instead
 * of each one building its own version.
 */

/**
 * Centralized currency/number formatting - Indian digit grouping
 * (lakhs/crores: 1,25,000 not 125,000) with the Rupee symbol, used
 * everywhere money is displayed in the app instead of each page
 * building its own "Rs ${...}" string.
 */
const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

export function formatCurrency(value) {
  return inrFormatter.format(Number(value || 0));
}

export function formatNumber(value) {
  return Number(value || 0).toLocaleString('en-IN');
}

export function formatPercent(value, decimals = 1) {
  return `${Number(value || 0).toFixed(decimals)}%`;
}

/** Today's date as YYYY-MM-DD, for pre-filling <input type="date"> fields
 * so users aren't manually picking "today" on every quick-action form. */
export function today() {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Single canonical status → badge-class mapping used across the whole
 * app, so the same status word always gets the same color no matter
 * which page it appears on.
 *
 * COMPLETED / DONE / PAID / STOCK OK / APPROVED / RECEIVED  -> green
 * IN PROGRESS / DOING                               -> gold
 * PENDING / NOT STARTED / TO DO / LOW STOCK / PARTIALLY PAID
 *   / ORDERED / PARTIALLY RECEIVED                  -> amber
 * ON HOLD / BLOCKED                                 -> neutral
 * OVERDUE / OUT OF STOCK / REJECTED / UNPAID / INACTIVE -> red
 * CANCELLED                              -> muted
 */
export function statusClass(status) {
  const s = (status || '').toLowerCase().trim();

  if (['completed', 'paid', 'stock ok', 'in stock', 'approved', 'active', 'done', 'received', 'closed'].includes(s)) return 'status-ok';
  if (s === 'in progress' || s === 'doing') return 'status-gold';
  if (['pending', 'not started', 'low stock', 'partially paid', 'to do', 'ordered', 'partially received'].includes(s)) return 'status-warning';
  if (s === 'on hold' || s === 'blocked') return 'status-neutral';
  if (s === 'cancelled') return 'status-muted';
  if (['overdue', 'out of stock', 'rejected', 'unpaid', 'inactive'].includes(s)) return 'status-danger';

  return 'status-info';
}

// --- loadError.js ---
/* Classifies a failed primary-record fetch into an honest message the
 * user can act on. Shared by every detail page's primary load instead
 * of duplicating this logic per page (Client/Employee/Material/Supplier
 * DetailPage already did this inline; this is the same behavior,
 * extracted so the 7 pages fixed alongside it don't reimplement it).
 *
 * The core rule: only a genuine 404 means "this record does not
 * exist" - every other failure (403 permission, 5xx server error,
 * a network failure, or anything unexpected) must never be presented
 * as "not found", since that implies something false about whether
 * the record exists. A 401 is not handled specially here - the
 * global response interceptor in api.js already redirects to /login
 * on 401 before this would meaningfully render, so labeling it
 * "not found" is the only thing that must be avoided for it, not a
 * distinct message of its own.
 */
export function classifyLoadError(err, label) {
  const status = err?.response?.status;

  if (status === 404) {
    return { message: `This ${label} could not be found.`, isNotFound: true };
  }
  if (status === 403) {
    return { message: `You do not have permission to view this ${label}.`, isNotFound: false };
  }
  if (status >= 500) {
    return { message: `Something went wrong loading this ${label}. Please try again.`, isNotFound: false };
  }
  if (!err?.response) {
    // No response at all (network failure, timeout, connection refused)
    // as distinct from a response that arrived with an error status.
    return { message: 'Unable to connect. Check your network and try again.', isNotFound: false };
  }
  return { message: `Unable to load this ${label}. Please try again.`, isNotFound: false };
}

// --- offlineQueue.js ---
/**
 * Offline resilience infrastructure for Woodful.
 *
 * SCOPE AND HONEST LIMITATIONS - read this before wiring a new mutation
 * into queueWrite() below:
 *
 * This deliberately does NOT attempt to solve general offline sync or
 * conflict resolution. For a business app with financial/inventory
 * data (payments, stock adjustments, order edits), blindly queuing
 * every failed write and silently replaying it later is genuinely
 * dangerous:
 *   - a payment submitted while offline, then retried by the user
 *     (who reasonably assumes it failed) becomes a duplicate once the
 *     queue also replays it
 *   - an order edited offline, replayed after someone else changed
 *     the same order on the server in the meantime, silently
 *     overwrites their change with no warning
 *
 * So this module only provides the INFRASTRUCTURE (detect
 * connectivity, persist a queue across a reload, replay in order when
 * back online, surface clear pending-count UI) - it does not decide
 * which mutations are safe to queue. That decision belongs with each
 * feature: only wrap a submit call in queueWrite() for an action that
 * is genuinely safe to replay later (e.g. idempotent by a client-
 * generated key, or something the user would want auto-retried rather
 * than resubmitted by hand) - not wired in globally here.
 *
 * "5-10 minutes" of continued local work: the queue is written to
 * localStorage on every change, so it survives a page reload during
 * that window, not just an in-memory blip. There is no time limit
 * enforced by this module itself - queued items simply wait until
 * connectivity returns, however long that takes.
 */

const QUEUE_KEY = 'woodful_offline_queue_v1';
const listeners = new Set();

function readQueue() {
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function writeQueue(queue) {
  try {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  } catch {
    // localStorage can genuinely fail (private browsing, quota) -
    // the queue then only lives in memory for this tab session,
    // which is a real, honest degradation, not a crash.
  }
  listeners.forEach((fn) => fn(queue));
}

/** Subscribe to queue-length changes, e.g. for a "3 changes pending" badge. */
export function onQueueChange(fn) {
  listeners.add(fn);
  fn(readQueue());
  return () => listeners.delete(fn);
}

export function getQueueLength() {
  return readQueue().length;
}

/**
 * Queues a write for later if it fails due to a genuine network
 * error (no response at all - offline, DNS failure, connection
 * refused). A real server response (4xx/5xx - validation error,
 * auth failure, business-rule rejection) is never queued - the
 * caller sees that error immediately and normally, exactly as
 * without this wrapper, since retrying a rejected request later
 * would just fail the same way again.
 *
 * label: short, human-readable description shown in the pending-
 * queue UI (e.g. "Record payment for WC-2026-014").
 */
export async function queueWrite(method, url, data, label) {
  try {
    return await client.request({ method, url, data });
  } catch (err) {
    const isNetworkError = err.isAxiosError && !err.response;
    if (!isNetworkError) {
      throw err;
    }
    const queue = readQueue();
    queue.push({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      method, url, data, label,
      queuedAt: new Date().toISOString(),
    });
    writeQueue(queue);
    // A distinct error type the caller can check for, so the UI can
    // show "saved locally - will send once you're back online"
    // instead of a normal failure message.
    const queuedError = new Error(`Queued offline: ${label}`);
    queuedError.isOfflineQueued = true;
    throw queuedError;
  }
}

let replaying = false;

/** Attempts every queued item in the order it was queued, stopping at
 * the first one that still fails with a network error (so a longer
 * outage doesn't reorder later items ahead of earlier ones). A queued
 * item that now gets a real server response - success OR a business
 * rejection - is removed from the queue either way; a rejection
 * means the underlying data has genuinely changed and blindly
 * retrying it forever would never succeed, so it is surfaced once
 * (via the returned failures list) rather than retried silently
 * forever. */
export async function replayQueue() {
  if (replaying) return { succeeded: [], failed: [] };
  replaying = true;
  const succeeded = [];
  const failed = [];
  try {
    let queue = readQueue();
    while (queue.length > 0) {
      const item = queue[0];
      try {
        await client.request({ method: item.method, url: item.url, data: item.data });
        succeeded.push(item);
      } catch (err) {
        const isNetworkError = err.isAxiosError && !err.response;
        if (isNetworkError) {
          break; // still offline - leave this and everything after it queued
        }
        failed.push({ item, error: err });
      }
      queue = queue.slice(1);
      writeQueue(queue);
    }
  } finally {
    replaying = false;
  }
  return { succeeded, failed };
}

/**
 * Wires window online/offline events plus a lightweight periodic
 * reachability check (navigator.onLine only reflects the network
 * interface, not real internet/server reachability - a Wi-Fi
 * connection with no actual internet still reports onLine=true) to a
 * callback, and automatically replays the queue when connectivity is
 * confirmed. Call this once near the app root; returns a cleanup
 * function.
 */
export function watchConnectivity(onStatusChange) {
  let isOnline = navigator.onLine;
  onStatusChange(isOnline);

  const checkReachability = async () => {
    try {
      // HEAD, not GET: the smallest possible real round-trip to the
      // actual backend, not just the network interface. /health (not
      // under /api - confirmed against the real route in main.py).
      await client.request({ method: 'head', url: '/health', timeout: 5000 });
      return true;
    } catch (err) {
      return !(err.isAxiosError && !err.response) ? true : false;
      // A real (even error) response still proves the server is
      // reachable - only a genuine network error means truly offline.
    }
  };

  const handleChange = async () => {
    const reachable = await checkReachability();
    if (reachable !== isOnline) {
      isOnline = reachable;
      onStatusChange(isOnline);
      if (isOnline) {
        replayQueue();
      }
    }
  };

  window.addEventListener('online', handleChange);
  window.addEventListener('offline', handleChange);
  const interval = setInterval(handleChange, 30000);

  return () => {
    window.removeEventListener('online', handleChange);
    window.removeEventListener('offline', handleChange);
    clearInterval(interval);
  };
}

// --- pageTitle.js ---
// Centralized page-title mapping. One place to look up/update titles,
// rather than each page setting document.title itself.
const SUFFIX = 'Woodful Creations';

// Static routes: exact pathname match.
const STATIC_TITLES = {
  '/': 'Dashboard',
  '/dashboard': 'Dashboard',
  '/analytics': 'Analytics',
  '/inventory': 'Inventory',
  '/materials': 'Materials',
  '/materials/import': 'Material Import',
  '/locations': 'Locations',
  '/purchases': 'Purchases',
  '/purchases/import': 'Purchase Import',
  '/suppliers': 'Suppliers',
  '/products': 'Products',
  '/products/import': 'Product Import',
  '/company-holidays': 'Company Holidays',
  '/company-holidays/import': 'Holiday Import',
  '/estimates': 'Estimates',
  '/estimates/import': 'Estimate Import',
  '/orders': 'Orders',
  '/orders/import': 'Order Import',
  '/rate-master': 'Rate Master',
  '/rate-master/import': 'Rate Card Import',
  '/issues': 'Issues',
  '/clients': 'Clients',
  '/clients/import': 'Client Import',
  '/payments': 'Payments',
  '/project-expenses': 'Project Expenses',
  '/employees': 'Employees',
  '/attendance': 'Attendance',
  '/leaves': 'Leaves',
  '/daily-tasks': 'Daily Tasks',
  '/production-jobs': 'Production Jobs',
  '/settings': 'Settings',
  '/learning-candidates': 'Learning Candidates',
  '/users': 'Users',
  '/audit-logs': 'Audit Logs',
  '/candidates': 'Candidates',
  '/interviews': 'Interviews',
  '/salary-slips': 'Salary Slips',
  '/mobile-app': 'Mobile App',
  '/login': 'Log In',
  '/forgot-password': 'Forgot Password',
  '/reset-password': 'Reset Password',
};

// Dynamic routes: prefix + a short label for the id segment.
const DYNAMIC_TITLES = [
  { prefix: '/materials/', label: 'Material' },
  { prefix: '/products/', label: 'Product' },
  { prefix: '/suppliers/', label: 'Supplier' },
  { prefix: '/purchases/', label: 'Purchase' },
  { prefix: '/clients/', label: 'Client' },
  { prefix: '/orders/', label: 'Order' },
  { prefix: '/employees/', label: 'Employee' },
  { prefix: '/daily-tasks/', label: 'Task' },
  { prefix: '/production-jobs/', label: 'Production Job' },
  { prefix: '/estimates/', label: 'Estimate' },
  { prefix: '/candidates/', label: 'Candidate' },
];

export function titleForPath(pathname) {
  if (STATIC_TITLES[pathname]) return `${STATIC_TITLES[pathname]} | ${SUFFIX}`;
  for (const { prefix, label } of DYNAMIC_TITLES) {
    if (pathname.startsWith(prefix) && pathname.length > prefix.length) {
      const id = pathname.slice(prefix.length).split('/')[0];
      if (id) return `${label} ${id} | ${SUFFIX}`;
    }
  }
  return SUFFIX;
}

export function setDocumentTitle(pathname) {
  document.title = titleForPath(pathname);
}

// --- theme.js ---
export const THEME_STORAGE_KEY = 'woodful-theme';

// Routes reachable before authentication - the only ones where theme
// should follow the system/browser preference rather than Woodful's
// own dark default. Kept in sync with App.jsx's own <Route path="...">
// list for these three pages (not derived from it programmatically,
// since this module must be importable and run before React Router
// itself initializes).
const UNAUTHENTICATED_PATHS = ['/login', '/forgot-password', '/reset-password'];

function systemPrefersLight() {
  try {
    return window.matchMedia('(prefers-color-scheme: light)').matches;
  } catch {
    // matchMedia unavailable (very old browser, or a test/SSR
    // environment) - Woodful's own dark default applies instead of
    // guessing at a system preference that can't be read.
    return false;
  }
}

/* Resolves which theme should be active on this exact page load.
 *
 * - An explicit, previously-saved user choice (from either the login
 *   page's own system-following default or a manual switch inside the
 *   authenticated app) always wins, on every route - a user who chose
 *   light once should keep seeing light everywhere, not have it
 *   silently overridden by whichever page they're on.
 * - With no saved choice yet: the login/forgot-password/reset-password
 *   pages follow the system/browser preference (never forced to dark);
 *   every other (authenticated) page defaults to Woodful's own dark
 *   theme regardless of system preference, per the standing design
 *   decision that the authenticated application has its own identity,
 *   distinct from the login screen.
 */
export function resolveInitialTheme(pathname) {
  let stored = null;
  try {
    stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    // localStorage unavailable (private browsing, disabled storage) -
    // fall through to the route-based default below.
  }
  if (stored === 'light' || stored === 'dark') return stored;

  if (UNAUTHENTICATED_PATHS.includes(pathname)) {
    return systemPrefersLight() ? 'light' : 'dark';
  }
  return 'dark';
}
