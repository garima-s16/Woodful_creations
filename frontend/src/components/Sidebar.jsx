import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import '../styles/Sidebar.css';

function Sidebar({ isOpen, user }) {
  const location = useLocation();
  const isMaster = user?.role === 'master' || user?.role === 'manager';
  const isTrueMaster = user?.role === 'master';

  const groups = [
    {
      name: 'Home',
      items: [{ path: '/dashboard', label: 'Dashboard' }],
    },
    {
      name: 'Inventory',
      items: [
        { path: '/materials', label: 'Materials' },
        { path: '/purchases', label: 'Purchases' },
        { path: '/issues', label: 'Material Issues' },
        { path: '/suppliers', label: 'Suppliers' },
      ],
    },
    {
      name: 'Sales',
      items: [
        { path: '/clients', label: 'Clients' },
        { path: '/estimates', label: 'Estimates' },
        { path: '/orders', label: 'Orders' },
        ...(isMaster ? [{ path: '/payments', label: 'Payments' }] : []),
      ],
    },
    {
      name: 'Projects & Production',
      items: [
        { path: '/daily-tasks', label: 'Tasks' },
        { path: '/production-jobs', label: 'Production Jobs' },
        ...(isMaster ? [{ path: '/project-expenses', label: 'Project Expenses' }] : []),
      ],
    },
    {
      name: 'People',
      items: [
        { path: '/employees', label: 'Employees' },
        { path: '/attendance', label: 'Attendance' },
        ...(isMaster ? [
          { path: '/salary-slips', label: 'Salary' },
          { path: '/candidates', label: 'Candidates' },
          { path: '/interviews', label: 'Interviews' },
        ] : []),
      ],
    },
    ...(isMaster ? [{
      name: 'Administration',
      items: [
        { path: '/settings', label: 'Settings' },
        ...(isTrueMaster ? [
          { path: '/users', label: 'Users' },
          { path: '/audit-logs', label: 'Audit Logs' },
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
                  <span className={`nav-chevron ${isCollapsed ? 'collapsed' : ''}`}>&#9662;</span>
                </button>
                {!isCollapsed && (
                  <div className="nav-group-items">
                    {group.items.map((item) => (
                      <Link
                        key={item.path}
                        to={item.path}
                        className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                      >
                        {item.label}
                      </Link>
                    ))}
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
