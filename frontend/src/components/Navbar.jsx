import React, { useState } from 'react';
import '../styles/components/Navbar.css';

function Navbar({ user, onLogout, toggleSidebar }) {
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  const handleLogout = () => {
    setShowProfileMenu(false);
    onLogout();
  };

  return (
    <nav className="navbar">
      <div className="navbar-left">
        <button className="sidebar-toggle" onClick={toggleSidebar}>
          <span></span>
          <span></span>
          <span></span>
        </button>
        <div className="navbar-logo">
          <span className="logo-text">Woodful Creations</span>
        </div>
      </div>

      <div className="navbar-right">
        <div className="navbar-user">
          <button 
            className="profile-button"
            onClick={() => setShowProfileMenu(!showProfileMenu)}
          >
            <div className="user-avatar">
              {user?.name?.charAt(0).toUpperCase()}
            </div>
            <span className="user-name">{user?.name}</span>
            <span className="user-role">({user?.role})</span>
          </button>

          {showProfileMenu && (
            <div className="profile-menu">
              <div className="profile-menu-item">
                <strong>{user?.email}</strong>
              </div>
              <div className="profile-menu-item">
                Role: {user?.role === 'master' ? 'Master User' : 'Regular User'}
              </div>
              <div className="profile-menu-divider"></div>
              <button 
                className="profile-menu-item logout"
                onClick={handleLogout}
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}

export default Navbar;