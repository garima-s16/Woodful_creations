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
