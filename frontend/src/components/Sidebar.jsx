import React, { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import '../styles/components/Sidebar.css';

function Sidebar({ isOpen, onClose, user }) {
  const location = useLocation();

  const menuItems = [
    { path: '/dashboard', label: 'Dashboard', icon: 'D' },
    { path: '/stock-inventory', label: 'Stock Inventory', icon: 'I' },
    { path: '/ai-chat', label: 'AI Chat', icon: 'A' },
    { path: '/clients', label: 'Clients', icon: 'C' },
    { path: '/estimates', label: 'Estimates', icon: 'E' },
    { path: '/attendance', label: 'Attendance', icon: 'T' },
    { path: '/interviews', label: 'Interviews', icon: 'V' },
  ];

  const masterItems = [
    { path: '/payments', label: 'Payments', icon: 'P' },
    { path: '/analytics', label: 'Analytics', icon: 'L' },
  ];

  const isMaster = user?.role === 'master';
  const isActive = (path) => location.pathname === path;
  const isMobileView = () =>
    typeof window !== 'undefined' && window.innerWidth <= 768;

  useEffect(() => {
    if (isMobileView()) {
      onClose?.();
    }
  }, [location.pathname, onClose]);

  const handleNavigation = () => {
    if (isMobileView()) {
      onClose?.();
    }
  };

  return (
    <>
      {isOpen && (
        <button
          aria-label="Close navigation menu"
          className="sidebar-backdrop"
          onClick={onClose}
          type="button"
        />
      )}
      <aside
        className={`sidebar ${isOpen ? 'open' : 'closed'}`}
        id="sidebar-navigation"
      >
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
                  className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                  onClick={handleNavigation}
                  to={item.path}
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
                    className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                    onClick={handleNavigation}
                    to={item.path}
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
    </>
  );
}

export default Sidebar;