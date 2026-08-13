/**
 * Woodful's icon system: consistent 20x20 stroke-based line icons, one
 * style throughout the app. Deliberately not an external dependency
 * (e.g. lucide-react) - avoids adding a package.json entry we can't
 * properly lock (no network access to regenerate package-lock.json's
 * integrity hashes here), which would silently break `npm ci` in Docker.
 */
import React from 'react';

const base = {
  width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', strokeWidth: 1.75, strokeLinecap: 'round', strokeLinejoin: 'round',
};

export const DashboardIcon = (p) => <svg {...base} {...p}><rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" /></svg>;
export const MaterialIcon = (p) => <svg {...base} {...p}><path d="M12 2 21 7v10l-9 5-9-5V7z" /><path d="M3 7l9 5 9-5" /><path d="M12 12v9" /></svg>;
export const SupplierIcon = (p) => <svg {...base} {...p}><rect x="3" y="8" width="13" height="11" rx="1" /><path d="M16 11h3l2 3v5h-5" /><circle cx="7.5" cy="19" r="1.5" /><circle cx="17.5" cy="19" r="1.5" /></svg>;
export const LocationIcon = (p) => <svg {...base} {...p}><path d="M12 21s-7-6.1-7-11.5A7 7 0 0119 9.5C19 14.9 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></svg>;
export const PurchaseIcon = (p) => <svg {...base} {...p}><path d="M3 6h18" /><path d="M5 6l1 13a2 2 0 002 2h8a2 2 0 002-2l1-13" /><path d="M9 10v4M15 10v4" /></svg>;
export const IssueIcon = (p) => <svg {...base} {...p}><path d="M4 4h11l5 5v11H4z" /><path d="M15 4v5h5" /><path d="M9 15l3-3 3 3" /></svg>;
export const ClientIcon = (p) => <svg {...base} {...p}><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0113 0" /><path d="M16 9a3 3 0 100-6" /><path d="M15 14a5.5 5.5 0 016.5 5.5" /></svg>;
export const OrderIcon = (p) => <svg {...base} {...p}><rect x="4" y="3" width="16" height="18" rx="1" /><path d="M8 8h8M8 12h8M8 16h5" /></svg>;
export const EstimateIcon = (p) => <svg {...base} {...p}><path d="M6 2h9l5 5v15H6z" /><path d="M15 2v5h5" /><path d="M9 13l2 2 4-4" /></svg>;
export const PaymentIcon = (p) => <svg {...base} {...p}><rect x="2" y="6" width="20" height="13" rx="2" /><path d="M2 10h20" /><path d="M6 15h4" /></svg>;
export const ExpenseIcon = (p) => <svg {...base} {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v10M9 9.5c0-1.4 1.3-2.5 3-2.5s3 1 3 2.2c0 3-6 1.3-6 4.2 0 1.4 1.3 2.6 3 2.6s3-1 3-2.4" /></svg>;
export const TaskIcon = (p) => <svg {...base} {...p}><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 12l2.5 2.5L16 9" /></svg>;
export const ProductionIcon = (p) => <svg {...base} {...p}><circle cx="7" cy="17" r="3" /><circle cx="17" cy="17" r="3" /><path d="M7 14V6h6l4 5v3" /><path d="M13 6v5h7" /></svg>;
export const EmployeeIcon = (p) => <svg {...base} {...p}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0116 0" /></svg>;
export const AttendanceIcon = (p) => <svg {...base} {...p}><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18" /><path d="M8 2v4M16 2v4" /><path d="M8.5 14.5l2 2 4.5-4.5" /></svg>;
export const LeaveIcon = (p) => <svg {...base} {...p}><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18" /><path d="M8 2v4M16 2v4" /><path d="M9 14h6M9 17h4" /></svg>;
export const SalaryIcon = (p) => <svg {...base} {...p}><rect x="2" y="5" width="20" height="14" rx="2" /><circle cx="12" cy="12" r="3" /><path d="M6 9v.01M18 15v.01" /></svg>;
export const CandidateIcon = (p) => <svg {...base} {...p}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0116 0" /><path d="M16 4l2 2 3-3" /></svg>;
export const InterviewIcon = (p) => <svg {...base} {...p}><path d="M4 4h16v12H8l-4 4z" /><path d="M8 9h8M8 12h5" /></svg>;
export const SettingsIcon = (p) => <svg {...base} {...p}><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" /></svg>;
export const UserIcon = (p) => <svg {...base} {...p}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0116 0" /></svg>;
export const AuditIcon = (p) => <svg {...base} {...p}><path d="M6 2h9l5 5v15H6z" /><path d="M15 2v5h5" /><path d="M9 12h6M9 16h6" /></svg>;
export const HomeIcon = (p) => <svg {...base} {...p}><path d="M3 11l9-7 9 7" /><path d="M5 10v10h14V10" /></svg>;

export const ChevronIcon = (p) => <svg {...base} width={14} height={14} {...p}><path d="M6 9l6 6 6-6" /></svg>;
export const MenuIcon = (p) => <svg {...base} {...p}><path d="M3 6h18M3 12h18M3 18h18" /></svg>;
export const CloseIcon = (p) => <svg {...base} {...p}><path d="M6 6l12 12M18 6L6 18" /></svg>;
export const SearchIcon = (p) => <svg {...base} {...p}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>;
export const LogoutIcon = (p) => <svg {...base} {...p}><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" /></svg>;
export const BellIcon = (p) => <svg {...base} {...p}><path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 01-3.4 0" /></svg>;
export const CartIcon = (p) => <svg {...base} {...p}><circle cx="9" cy="20" r="1.5" /><circle cx="18" cy="20" r="1.5" /><path d="M2 3h2l2.6 12.6a2 2 0 002 1.6h8.8a2 2 0 002-1.7L21 8H6" /></svg>;
export const GridIcon = (p) => <svg {...base} {...p}><rect x="3" y="3" width="8" height="8" rx="1" /><rect x="13" y="3" width="8" height="8" rx="1" /><rect x="3" y="13" width="8" height="8" rx="1" /><rect x="13" y="13" width="8" height="8" rx="1" /></svg>;
export const ListIcon = (p) => <svg {...base} {...p}><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3 6h.01M3 12h.01M3 18h.01" /></svg>;
export const PlusIcon = (p) => <svg {...base} {...p}><path d="M12 5v14M5 12h14" /></svg>;
export const SlidersIcon = (p) => <svg {...base} {...p}><path d="M4 6h10M17 6h3M4 18h3M10 18h10M4 12h16" /><circle cx="16" cy="6" r="2" /><circle cx="7" cy="18" r="2" /></svg>;
