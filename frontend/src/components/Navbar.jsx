import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import '../styles/components/Navbar.css';

function Navbar({ isSidebarOpen, user, onLogout, toggleSidebar }) {
  const navigate = useNavigate();
  const [showProfile, setShowProfile] = useState(false);

  const handleLogout = () => {
    onLogout();
    navigate('/');
  };

  return (
    <nav aria-label="Main navigation" className="navbar">
      <div className="navbar-container">
        <div className="navbar-left">
          <button
            aria-controls="sidebar-navigation"
            aria-expanded={isSidebarOpen}
            aria-label="Toggle navigation menu"
            className="menu-toggle"
            onClick={toggleSidebar}
            title="Toggle menu"
            type="button"
          >
            <span></span>
            <span></span>
            <span></span>
          </button>
          <Link to="/dashboard" className="navbar-brand">
            <span className="brand-icon">W</span>
            <span className="brand-text">Woodful Creations</span>
          </Link>
        </div>

        <div className="navbar-right">
          <div className="user-menu">
            <button
              aria-expanded={showProfile}
              aria-label="User profile menu"
              className="profile-button"
              onClick={() => setShowProfile(!showProfile)}
              type="button"
            >
              <div className="profile-avatar">{user?.name?.[0]?.toUpperCase()}</div>
              <span className="profile-name">{user?.name}</span>
            </button>

            {showProfile && (
              <div className="profile-dropdown">
                <div className="profile-header">
                  <p className="user-email">{user?.email}</p>
                  <p className="user-role">{user?.role === 'master' ? 'Master Admin' : 'User'}</p>
                </div>
                <hr />
                <button className="logout-button" onClick={handleLogout} type="button">
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;