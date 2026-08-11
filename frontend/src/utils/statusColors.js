/**
 * Single canonical status → badge-class mapping used across the whole
 * app, so the same status word always gets the same color no matter
 * which page it appears on.
 *
 * COMPLETED / PAID / STOCK OK / APPROVED -> green
 * IN PROGRESS                            -> gold
 * PENDING / NOT STARTED                  -> amber
 * ON HOLD                                -> neutral
 * OVERDUE / OUT OF STOCK / LOW STOCK / REJECTED -> red
 * CANCELLED                              -> muted
 */
export function statusClass(status) {
  const s = (status || '').toLowerCase().trim();

  if (['completed', 'paid', 'stock ok', 'in stock', 'approved', 'active'].includes(s)) return 'status-ok';
  if (s === 'in progress') return 'status-gold';
  if (['pending', 'not started', 'low stock'].includes(s)) return 'status-warning';
  if (s === 'on hold') return 'status-neutral';
  if (s === 'cancelled') return 'status-muted';
  if (['overdue', 'out of stock', 'rejected'].includes(s)) return 'status-danger';

  return 'status-info';
}
