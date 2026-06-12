import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import '../styles/components/Sidebar.css';

function Sidebar({ isOpen, user }) {
  const location = useLocation();

  const menuItems = [
    { path: '/dashboard', label: 'Dashboard', icon: 'grid' },
    { path: '/stock-inventory', label: 'Stock Inventory', icon: 'box' },
    { path: '/ai-chat', label: 'AI Chat', icon: 'message' },
    { path: '/clients', label: 'Clients', icon: 'users' },
    { path: '/estimates', label: 'Estimates', icon: 'file' },
    { path: '/attendance', label: 'Attendance', icon: 'calendar' },
    { path: '/interviews', label: 'Interviews', icon: 'briefcase' },
  ];

  const masterOnlyItems = [
    { path: '/payments', label: 'Payments', icon: 'credit-card' },
    { path: '/analytics', label: 'Analytics', icon: 'chart' },
  ];

  const allItems = user?.role === 'master' ? [...menuItems, ...masterOnlyItems] : menuItems;

  return (
    <aside className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      <div className="sidebar-content">
        <ul className="sidebar-menu">
          {allItems.map(item => (
            <li key={item.path}>
              <Link 
                to={item.path}
                className={`sidebar-link ${location.pathname === item.path ? 'active' : ''}`}
              >
                <span className="sidebar-icon">{item.icon}</span>
                <span className="sidebar-label">{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

export default Sidebar;