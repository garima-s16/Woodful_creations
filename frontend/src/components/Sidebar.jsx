import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import '../styles/components/Sidebar.css';

function Sidebar({ isOpen, user }) {
  const location = useLocation();

  const menuItems = [
    { path: '/dashboard', label: 'Dashboard', icon: 'D' },
    { path: '/materials', label: 'Materials', icon: 'M' },
    { path: '/suppliers', label: 'Suppliers', icon: 'S' },
    { path: '/purchases', label: 'Purchases', icon: 'P' },
    { path: '/issues', label: 'Issues', icon: 'I' },
    { path: '/clients', label: 'Clients', icon: 'C' },
    { path: '/orders', label: 'Orders', icon: 'O' },
    { path: '/estimates', label: 'Estimates', icon: 'Q' },
    { path: '/employees', label: 'Employees', icon: 'E' },
    { path: '/attendance', label: 'Attendance', icon: 'T' },
    { path: '/daily-tasks', label: 'Daily Tasks', icon: 'K' },
    { path: '/chat', label: 'Assistant', icon: 'A' },
  ];

  const masterItems = [
    { path: '/payments', label: 'Payments', icon: '$' },
    { path: '/project-expenses', label: 'Project Expenses', icon: 'X' },
    { path: '/salary-slips', label: 'Salary Slips', icon: 'R' },
    { path: '/candidates', label: 'Candidates', icon: 'N' },
    { path: '/interviews', label: 'Interviews', icon: 'V' },
    { path: '/settings', label: 'Settings', icon: 'G' },
  ];

  const isMaster = user?.role === 'master' || user?.role === 'manager';
  const isActive = (path) => location.pathname === path;

  return (
    <aside className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      <div className="sidebar-content">
        <div className="sidebar-header">
          <h2>Menu</h2>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section">
            <h3 className="section-title">Main</h3>
            {menuItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </Link>
            ))}
          </div>

          {isMaster && (
            <div className="nav-section">
              <h3 className="section-title">Master Controls</h3>
              {masterItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                </Link>
              ))}
            </div>
          )}
        </nav>
      </div>
    </aside>
  );
}

export default Sidebar;
