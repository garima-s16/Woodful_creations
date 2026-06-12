import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import './Navigation.css';

function Navigation({ onLogout, userRole }) {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();

  const menuItems = [
    { label: 'Dashboard', path: '/', icon: 'dashboard' },
    { label: 'Stock Inventory', path: '/inventory', icon: 'inventory' },
    { label: 'Estimates', path: '/estimates', icon: 'estimates' },
    { label: 'Attendance', path: '/attendance', icon: 'attendance' },
    { label: 'Interviews', path: '/interviews', icon: 'interviews' },
    { label: 'Clients', path: '/clients', icon: 'clients' },
  ];

  const masterItems = [
    { label: 'Payments', path: '/payments', icon: 'payments' },
    { label: 'Analytics', path: '/analytics', icon: 'analytics' },
  ];

  const isMaster = userRole === 'master';

  const isActive = (path) => location.pathname === path;

  return (
    <>
      <nav className="navbar">
        <div className="navbar-container">
          <div className="navbar-brand">
            <span className="brand-text">Woodful</span>
          </div>
          <button className="menu-toggle" onClick={() => setIsOpen(!isOpen)}>
            <span></span>
            <span></span>
            <span></span>
          </button>
          <button className="logout-btn" onClick={onLogout}>Logout</button>
        </div>
      </nav>

      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-content">
          <div className="sidebar-header">
            <h2>Woodful Creations</h2>
            <p className="user-role">{isMaster ? 'Master Admin' : 'User'}</p>
          </div>

          <nav className="sidebar-nav">
            <div className="nav-section">
              <h3 className="section-title">Main</h3>
              {menuItems.map(item => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                  onClick={() => setIsOpen(false)}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                </Link>
              ))}
            </div>

            {isMaster && (
              <div className="nav-section">
                <h3 className="section-title">Master Controls</h3>
                {masterItems.map(item => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                    onClick={() => setIsOpen(false)}
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

      {isOpen && <div className="sidebar-overlay" onClick={() => setIsOpen(false)}></div>}
    </>
  );
}

export default Navigation;