import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import '../styles/components/Navbar.css';

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
          <button className="menu-toggle" onClick={toggleSidebar} aria-label="Toggle navigation">
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
                  <p className="user-role">{user?.role === 'master' ? 'Master Admin' : 'User'}</p>
                </div>
                <hr />
                <button onClick={handleLogout} className="logout-button">
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