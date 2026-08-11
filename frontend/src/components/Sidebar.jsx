import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  HomeIcon, MaterialIcon, PurchaseIcon, IssueIcon, SupplierIcon, ClientIcon, EstimateIcon,
  OrderIcon, PaymentIcon, TaskIcon, ProductionIcon, ExpenseIcon, EmployeeIcon, AttendanceIcon,
  LeaveIcon, SalaryIcon, CandidateIcon, InterviewIcon, SettingsIcon, UserIcon, AuditIcon, ChevronIcon,
} from './icons';
import '../styles/components/Sidebar.css';

function Sidebar({ isOpen, user }) {
  const location = useLocation();
  const isMaster = user?.role === 'master' || user?.role === 'manager';
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
        { path: '/purchases', label: 'Purchases', icon: PurchaseIcon },
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
        ...(isMaster ? [{ path: '/payments', label: 'Payments', icon: PaymentIcon }] : []),
      ],
    },
    {
      name: 'Projects & Production',
      items: [
        { path: '/daily-tasks', label: 'Tasks', icon: TaskIcon },
        { path: '/production-jobs', label: 'Production Jobs', icon: ProductionIcon },
        ...(isMaster ? [{ path: '/project-expenses', label: 'Project Expenses', icon: ExpenseIcon }] : []),
      ],
    },
    {
      name: 'People',
      items: [
        { path: '/employees', label: 'Employees', icon: EmployeeIcon },
        { path: '/attendance', label: 'Attendance', icon: AttendanceIcon },
        { path: '/leaves', label: 'Leave', icon: LeaveIcon },
        ...(isMaster ? [
          { path: '/salary-slips', label: 'Salary', icon: SalaryIcon },
          { path: '/candidates', label: 'Candidates', icon: CandidateIcon },
          { path: '/interviews', label: 'Interviews', icon: InterviewIcon },
        ] : []),
      ],
    },
    ...(isMaster ? [{
      name: 'Administration',
      items: [
        { path: '/settings', label: 'Settings', icon: SettingsIcon },
        ...(isTrueMaster ? [
          { path: '/users', label: 'Users', icon: UserIcon },
          { path: '/audit-logs', label: 'Audit Logs', icon: AuditIcon },
        ] : []),
      ],
    }] : []),
  ];

  const isActive = (path) => location.pathname === path || location.pathname.startsWith(path + '/');
  const groupHasActive = (group) => group.items.some((item) => isActive(item.path));

  const [collapsed, setCollapsed] = useState({});
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
                {!isCollapsed && (
                  <div className="nav-group-items">
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
                  </div>
                )}
              </div>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}

export default Sidebar;
