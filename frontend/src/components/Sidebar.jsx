import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Link, useLocation } from 'react-router-dom';
import {
  HomeIcon, MaterialIcon, PurchaseIcon, IssueIcon, SupplierIcon, ClientIcon, EstimateIcon, LocationIcon, MobileAppIcon,
  OrderIcon, PaymentIcon, TaskIcon, ProductionIcon, ExpenseIcon, EmployeeIcon, AttendanceIcon,
  LeaveIcon, SalaryIcon, CandidateIcon, InterviewIcon, SettingsIcon, UserIcon, AuditIcon, ChevronIcon,
} from './icons';
import '../styles/components/Sidebar.css';

function Sidebar({ isOpen, user }) {
  const location = useLocation();
  const isTrueMaster = user?.role === 'master';

  const groups = [
    {
      name: 'Home',
      items: [{ path: '/dashboard', label: 'Dashboard', icon: HomeIcon }],
    },
    {
      name: 'Inventory',
      items: [
        { path: '/materials', label: 'Materials', icon: MaterialIcon },
        { path: '/locations', label: 'Locations', icon: LocationIcon },
        ...(isTrueMaster ? [
          { path: '/purchases', label: 'Purchases', icon: PurchaseIcon },
          { path: '/purchases/import', label: 'Import from Excel', icon: PurchaseIcon },
        ] : []),
        { path: '/issues', label: 'Material Issues', icon: IssueIcon },
        { path: '/suppliers', label: 'Suppliers', icon: SupplierIcon },
      ],
    },
    {
      name: 'Sales',
      items: [
        { path: '/clients', label: 'Clients', icon: ClientIcon },
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

  // openGroups is the single source of truth for expand/collapse state.
  // It is initialized from the current route, and re-synced whenever the
  // route changes so client-side navigation (which does not remount this
  // component) always auto-expands the section that owns the active page.
  const [openGroups, setOpenGroups] = useState(() => {
    const initial = new Set();
    const activeGroup = groups.find(groupHasActive);
    if (activeGroup) initial.add(activeGroup.name);
    return initial;
  });

  useEffect(() => {
    const activeGroup = groups.find(groupHasActive);
    if (!activeGroup) return;
    setOpenGroups((prev) => {
      if (prev.has(activeGroup.name)) return prev; // already open, avoid extra renders
      const next = new Set(prev);
      next.add(activeGroup.name);
      return next;
    });
    // Re-run whenever the route changes; group definitions are stable per render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const toggleGroup = (name) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  return (
    <aside className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      <div className="sidebar-content">
        <nav className="sidebar-nav">
          {groups.map((group) => {
            const isCollapsed = !openGroups.has(group.name);
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
  );
}

export default Sidebar;
