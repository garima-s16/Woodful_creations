import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Link, useLocation } from 'react-router-dom';
import {
  HomeIcon, MaterialIcon, ProductIcon, PurchaseIcon, IssueIcon, SupplierIcon, ClientIcon, EstimateIcon, LocationIcon, MobileAppIcon,
  OrderIcon, PaymentIcon, TaskIcon, ProductionIcon, ExpenseIcon, EmployeeIcon, AttendanceIcon,
  LeaveIcon, SalaryIcon, CandidateIcon, InterviewIcon, SettingsIcon, UserIcon, AuditIcon, ChevronIcon, AnalyticsIcon, InventoryIcon,
} from './icons';
import '../styles/components/Sidebar.css';

function Sidebar({ isOpen, user, onClose }) {
  const location = useLocation();
  const isTrueMaster = user?.role === 'master';

  const groups = [
    {
      name: 'Home',
      items: [
        { path: '/dashboard', label: 'Dashboard', icon: HomeIcon },
        { path: '/analytics', label: 'Analytics', icon: AnalyticsIcon },
      ],
    },
    {
      name: 'Inventory',
      items: [
        // The single operational home for inventory. The
        // existing Materials/Locations/Purchases/Issues pages stay put
        // for direct navigation; this is just the new
        // unified entry point that sits above them.
        { path: '/inventory', label: 'Inventory', icon: InventoryIcon },
        { path: '/materials', label: 'Materials', icon: MaterialIcon },
        { path: '/locations', label: 'Locations', icon: LocationIcon },
        ...(isTrueMaster ? [
          { path: '/purchases', label: 'Purchases', icon: PurchaseIcon },
        ] : []),
        { path: '/issues', label: 'Material Issues', icon: IssueIcon },
        { path: '/suppliers', label: 'Suppliers', icon: SupplierIcon },
      ],
    },
    {
      name: 'Sales',
      items: [
        { path: '/clients', label: 'Clients', icon: ClientIcon },
        { path: '/products', label: 'Products', icon: ProductIcon },
        ...(isTrueMaster ? [{ path: '/rate-master', label: 'Rate Master', icon: ProductIcon }] : []),
        { path: '/estimates', label: 'Estimates', icon: EstimateIcon },
        { path: '/orders', label: 'Orders', icon: OrderIcon },
        ...(isTrueMaster ? [{ path: '/payments', label: 'Payments', icon: PaymentIcon }] : []),
      ],
    },
    {
      name: 'Projects & Production',
      items: [
        { path: '/daily-tasks', label: 'Tasks', icon: TaskIcon },
        { path: '/production-jobs', label: 'Production Jobs', icon: ProductionIcon },
        ...(isTrueMaster ? [{ path: '/project-expenses', label: 'Project Expenses', icon: ExpenseIcon }] : []),
      ],
    },
    {
      name: 'People',
      items: [
        { path: '/employees', label: 'Employees', icon: EmployeeIcon },
        { path: '/attendance', label: 'Attendance', icon: AttendanceIcon },
        { path: '/leaves', label: 'Leave', icon: LeaveIcon },
        { path: '/company-holidays', label: 'Company Holidays', icon: LeaveIcon },
        { path: '/salary-slips', label: 'Salary', icon: SalaryIcon },
        ...(isTrueMaster ? [
          { path: '/candidates', label: 'Candidates', icon: CandidateIcon },
          { path: '/interviews', label: 'Interviews', icon: InterviewIcon },
        ] : []),
      ],
    },
    ...(isTrueMaster ? [{
      name: 'Administration',
      items: [
        { path: '/settings', label: 'Settings', icon: SettingsIcon },
        { path: '/learning-candidates', label: 'Chatbot Learning', icon: AuditIcon },
        ...(isTrueMaster ? [
          { path: '/users', label: 'Users', icon: UserIcon },
          { path: '/audit-logs', label: 'Audit Logs', icon: AuditIcon },
          { path: '/mobile-app', label: 'Get Mobile App', icon: MobileAppIcon },
        ] : []),
      ],
    }] : []),
  ];

  const isActive = (path) => location.pathname === path || location.pathname.startsWith(path + '/');
  const groupHasActive = (group) => group.items.some((item) => isActive(item.path));

  // openGroup (a single value, not a Set) is the source of truth for
  // which one section is expanded - true accordion behavior, only one
  // open at a time (see toggleGroup below).
  // It is initialized from the current route, and re-synced whenever the
  // route changes so client-side navigation (which does not remount this
  // component) always auto-expands the section that owns the active page.
  const [openGroup, setOpenGroup] = useState(() => {
    const activeGroup = groups.find(groupHasActive);
    return activeGroup ? activeGroup.name : null;
  });

  useEffect(() => {
    const activeGroup = groups.find(groupHasActive);
    if (!activeGroup) return;
    // Auto-expand the section owning the newly-active route - and, per
    // the accordion requirement, this REPLACES whatever was open
    // before rather than adding to it, so direct navigation to a page
    // in a different section correctly collapses the previous one too.
    setOpenGroup((prev) => (prev === activeGroup.name ? prev : activeGroup.name));
    // Re-run whenever the route changes; group definitions are stable per render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const toggleGroup = (name) => {
    // True accordion: opening a section always closes whichever other
    // section was open - only one can ever be expanded at a time.
    // Clicking the already-open section's own header collapses it.
    setOpenGroup((prev) => (prev === name ? null : name));
  };

  return (
    <>
      {isOpen && (
        <div className="sidebar-backdrop" onClick={onClose} aria-hidden="true" />
      )}
      <aside className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      <div className="sidebar-content">
        <nav className="sidebar-nav">
          {groups.map((group) => {
            const isCollapsed = openGroup !== group.name;
            return (
              <div className="nav-group" key={group.name}>
                <button
                  className="nav-group-header"
                  onClick={() => toggleGroup(group.name)}
                  type="button"
                >
                  <span>{group.name}</span>
                  <ChevronIcon className={`nav-chevron ${isCollapsed ? 'collapsed' : ''}`} />
                </button>
                <AnimatePresence initial={false}>
                  {!isCollapsed && (
                    <motion.div
                      className="nav-group-items"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                      style={{ overflow: 'hidden' }}
                    >
                      {group.items.map((item) => {
                        const Icon = item.icon;
                        return (
                          <Link
                            key={item.path}
                            to={item.path}
                            className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                            onClick={() => {
                              if (onClose && window.innerWidth <= 768) onClose();
                            }}
                          >
                            <Icon className="nav-item-icon" />
                            <span>{item.label}</span>
                          </Link>
                        );
                      })}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </nav>
      </div>
    </aside>
    </>
  );
}

export default Sidebar;
