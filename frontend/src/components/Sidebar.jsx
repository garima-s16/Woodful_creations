import React, { useState } from 'react';
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

  const [collapsed, setCollapsed] = useState(() => {
    const initial = {};
    groups.forEach((group) => {
      if (!groupHasActive(group)) initial[group.name] = true;
    });
    return initial;
  });
  const toggleGroup = (name) => setCollapsed((prev) => ({ ...prev, [name]: !prev[name] }));

  return (
    <aside className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      <div className="sidebar-content">
        <nav className="sidebar-nav">
          {groups.map((group) => {
            const isCollapsed = collapsed[group.name] && !groupHasActive(group);
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
