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

  if (['completed', 'paid', 'stock ok', 'in stock', 'approved', 'active', 'done', 'received'].includes(s)) return 'status-ok';
  if (s === 'in progress' || s === 'doing') return 'status-gold';
  if (['pending', 'not started', 'low stock', 'partially paid', 'to do', 'ordered', 'partially received'].includes(s)) return 'status-warning';
  if (s === 'on hold' || s === 'blocked') return 'status-neutral';
  if (s === 'cancelled') return 'status-muted';
  if (['overdue', 'out of stock', 'rejected', 'unpaid', 'inactive'].includes(s)) return 'status-danger';

  return 'status-info';
}
