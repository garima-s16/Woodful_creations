import React from 'react';
import { useNavigate } from 'react-router-dom';
import './Navbar.css';

function Navbar({ user, onLogout, toggleSidebar }) {
  const navigate = useNavigate();
  
  const handleLogout = () => {
    onLogout();
    navigate('/login');
  };
  
  return (
    <nav className="navbar">
      <div className="navbar-left">
        <button className="hamburger" onClick={toggleSidebar}>
          MENU
        </button>
        <div className="logo">
          <span className="logo-text">WOODFUL</span>
        </div>
      </div>
      
      <div className="navbar-right">
        <div className="user-info">
          <span className="user-name">{user?.full_name || 'User'}</span>
          <span className={`user-role ${user?.is_master ? 'master' : 'regular'}`}>
            {user?.is_master ? 'Master' : 'User'}
          </span>
        </div>
        <button className="logout-btn" onClick={handleLogout}>
          Logout
        </button>
      </div>
    </nav>
  );
}

export default Navbar;