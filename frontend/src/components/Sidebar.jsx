import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Link, useLocation } from 'react-router-dom';
import {
  HomeIcon, MaterialIcon, ProductIcon, PurchaseIcon, ClientIcon, EstimateIcon, MobileAppIcon,
  OrderIcon, PaymentIcon, TaskIcon, ProductionIcon, EmployeeIcon, AttendanceIcon,
  CandidateIcon, SettingsIcon, UserIcon, AuditIcon, ChevronIcon, InventoryIcon,
} from './icons';
import '../styles/layout.css';

function Sidebar({ isOpen, user, onClose }) {
  const location = useLocation();
  const isTrueMaster = user?.role === 'master';

  const groups = [
    {
      name: 'Home',
      items: [
        // Dashboard -> Home rename: same existing DashboardPage
        // implementation, now the single Home/Command Centre nav
        // destination at /home (see App.jsx - /dashboard still
        // exists only as a redirect to /home for old links).
        //
        // Business Attention (/business-decisions), Analytics
        // (/analytics), and Owner Briefing (/owner-briefing) are no
        // longer separate Sidebar destinations - Home is the single
        // command centre now. Their pages, routes, and backend APIs
        // are untouched and still reachable directly; only these
        // three nav entries are removed.
        { path: '/home', label: 'Home', icon: HomeIcon },
      ],
    },
    {
      // IA consolidation (Woodful navigation/module-structure task):
      // Locations, Material Issues, and Suppliers are no longer
      // separate primary nav items here. Locations and Material Issues
      // are already full tabs inside this same InventoryPage workspace
      // ("Locations"/"Issues" tabs, ALL_TABS in InventoryPages.jsx) -
      // no new page, no new API, no duplicate data. Suppliers is
      // reached from Purchases (a "Suppliers" quick-link was added to
      // PurchasesPage). None of the underlying pages/routes/models
      // were deleted - /locations, /issues, /suppliers still work
      // directly.
      name: 'Inventory',
      items: [
        { path: '/inventory', label: 'Inventory', icon: InventoryIcon },
        { path: '/materials', label: 'Materials', icon: MaterialIcon },
        ...(isTrueMaster ? [
          { path: '/purchases', label: 'Purchases', icon: PurchaseIcon },
          { path: '/procurement-requirements', label: 'Procurement', icon: PurchaseIcon },
        ] : []),
      ],
    },
    {
      // Rate Master is no longer a separate primary nav item - it
      // supports Products/Estimates pricing (a "Rates" quick-link was
      // added to ProductsPage) and /rate-master still works directly.
      name: 'Sales',
      items: [
        { path: '/clients', label: 'Clients', icon: ClientIcon },
        { path: '/products', label: 'Products', icon: ProductIcon },
        { path: '/estimates', label: 'Estimates', icon: EstimateIcon },
        { path: '/orders', label: 'Orders', icon: OrderIcon },
        ...(isTrueMaster ? [{ path: '/payments', label: 'Payments', icon: PaymentIcon }] : []),
      ],
    },
    {
      // Project Expenses is no longer a separate primary nav item - it
      // already lives inside every Order's own "Expenses" tab
      // (OrderDetailPage); /project-expenses still works directly for
      // a full cross-order list.
      name: 'Projects & Production',
      items: [
        { path: '/daily-tasks', label: 'Tasks', icon: TaskIcon },
        { path: '/production-jobs', label: 'Production Jobs', icon: ProductionIcon },
      ],
    },
    {
      name: 'People',
      items: [
        { path: '/employees', label: 'Employees', icon: EmployeeIcon },
        // Attendance, Leave, and Company Holidays combined into one
        // workspace (see AttendanceLeaveHub in WorkforcePages.jsx) -
        // the same three existing pages, unchanged, switched between
        // by one internal tab bar. /attendance, /leaves, and
        // /company-holidays still work directly too. Salary Slips and
        // Salary Advances are reached from each Employee's own
        // "Salary" tab (already built into EmployeeDetailPage) rather
        // than a standalone nav item; /salary-slips and
        // /salary-advances still work directly.
        { path: '/attendance-leave', label: 'Attendance & Leave', icon: AttendanceIcon },
        // Candidates and Interviews combined the same way (see
        // RecruitmentHub in RecruitmentPages.jsx). Master-only,
        // matching the require_role("master") gate already on every
        // candidates/interviews backend endpoint.
        ...(isTrueMaster ? [{ path: '/recruitment', label: 'Recruitment', icon: CandidateIcon }] : []),
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
