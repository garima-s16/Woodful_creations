import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { MenuIcon, LogoutIcon, ChevronIcon, CartIcon } from './icons';
import GlobalSearch from './GlobalSearch';
import '../styles/Navbar.css';

const ROLE_LABELS = { master: 'Master Admin', manager: 'Manager', user: 'Team Member' };

function Navbar({ user, onLogout, toggleSidebar, onOpenCart }) {
  const cartCount = useSelector((state) => state.cart.items.reduce((sum, i) => sum + i.quantity, 0));
  const navigate = useNavigate();
  const [showProfile, setShowProfile] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setShowProfile(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    onLogout();
    navigate('/');
  };

  const roleLabel = ROLE_LABELS[user?.role] || 'Team Member';

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-left">
          <button className="menu-toggle" onClick={toggleSidebar} title="Toggle menu">
            <MenuIcon />
          </button>
          <Link to="/dashboard" className="navbar-brand">
            <span className="brand-mark">
              <img src="/logo.png" alt="Woodful Creations" className="brand-logo-img" />
            </span>
            <span className="brand-text">
              <span className="brand-name">Woodful Creations</span>
              <span className="brand-tagline">Business Management</span>
            </span>
          </Link>
        </div>

        <GlobalSearch />

        <div className="navbar-right">
          <button className="cart-toggle" onClick={onOpenCart} title="Purchase cart" aria-label="Open purchase cart">
            <CartIcon width={19} height={19} />
            {cartCount > 0 && <span className="cart-toggle-badge">{cartCount}</span>}
          </button>
          <div className="user-menu" ref={menuRef}>
            <button
              className="profile-button"
              onClick={() => setShowProfile((v) => !v)}
              aria-expanded={showProfile}
            >
              <div className="profile-avatar">{user?.name?.[0]?.toUpperCase()}</div>
              <span className="profile-info">
                <span className="profile-name">{user?.name}</span>
                <span className="profile-role">{roleLabel}</span>
              </span>
              <ChevronIcon className={`profile-chevron ${showProfile ? 'open' : ''}`} />
            </button>

            {showProfile && (
              <div className="profile-dropdown">
                <div className="profile-header">
                  <p className="dropdown-name">{user?.name}</p>
                  <p className="user-email">{user?.email}</p>
                  <p className="user-role">{roleLabel}</p>
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
