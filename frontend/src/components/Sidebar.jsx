import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import './Sidebar.css';

function Sidebar({ isOpen, user }) {
  const location = useLocation();
  
  const menuItems = [
    { label: 'Dashboard', path: '/dashboard', icon: 'D' },
    { label: 'Stock Inventory', path: '/stock-inventory', icon: 'I' },
    { label: 'AI Chat', path: '/ai-chat', icon: 'A' },
    { label: 'Clients', path: '/clients', icon: 'C' },
    { label: 'Estimates', path: '/estimates', icon: 'E' },
    { label: 'Attendance', path: '/attendance', icon: 'T' },
    { label: 'Interviews', path: '/interviews', icon: 'R' },
    { label: 'Analytics', path: '/analytics', icon: 'N' },
  ];
  
  if (user?.is_master) {
    menuItems.push({ label: 'Payments', path: '/payments', icon: 'P' });
  }
  
  return (
    <aside className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </Link>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;