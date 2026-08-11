import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { MenuIcon, LogoutIcon } from './icons';
import '../styles/Navbar.css';

function Navbar({ user, onLogout, toggleSidebar }) {
  const navigate = useNavigate();
  const [showProfile, setShowProfile] = useState(false);

  const handleLogout = () => {
    onLogout();
    navigate('/');
  };

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-left">
          <button className="menu-toggle" onClick={toggleSidebar} title="Toggle menu">
            <MenuIcon />
          </button>
          {/* Brand treatment: typography-led wordmark, not a designed logo -
              swap the mark span for an <img> once a real logo asset exists. */}
          <Link to="/dashboard" className="navbar-brand">
            <span className="brand-mark">W</span>
            <span className="brand-text">
              <span className="brand-name">Woodful Creations</span>
              <span className="brand-tagline">Business Management</span>
            </span>
          </Link>
        </div>

        <div className="navbar-right">
          <div className="user-menu">
            <button
              className="profile-button"
              onClick={() => setShowProfile(!showProfile)}
            >
              <div className="profile-avatar">{user?.name?.[0]?.toUpperCase()}</div>
              <span className="profile-name">{user?.name}</span>
            </button>

            {showProfile && (
              <div className="profile-dropdown">
                <div className="profile-header">
                  <p className="user-email">{user?.email}</p>
                  <p className="user-role">{user?.role === 'master' ? 'Master Admin' : user?.role === 'manager' ? 'Manager' : 'User'}</p>
                </div>
                <hr />
                <button onClick={handleLogout} className="logout-button">
                  <LogoutIcon width={16} height={16} />
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
