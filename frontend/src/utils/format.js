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
