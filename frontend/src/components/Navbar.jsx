import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { MenuIcon, LogoutIcon, ChevronIcon, CartIcon, SearchIcon, SunIcon, MoonIcon } from './icons';
import { toggleTheme } from '../redux/slices/themeSlice';
import GlobalSearch from './GlobalSearch';
import NotificationBell from './NotificationBell';
import '../styles/Navbar.css';

/**
 * Woodful's icon set (./icons) is used throughout the navbar rather than
 * lucide-react. The project intentionally does not depend on lucide-react
 * (see components/icons/index.jsx) since this environment has no network
 * access to regenerate package-lock.json's integrity hashes, and an
 * unlocked dependency would silently break `npm ci` in Docker. The
 * existing icon set already covers every control used here.
 */

const ROLE_LABELS = { master: 'Master Admin', user: 'Team Member' };

function Navbar({ user, onLogout, toggleSidebar, onOpenCart }) {
  const cartCount = useSelector((state) => state.cart.items.reduce((sum, i) => sum + i.quantity, 0));
  const themeMode = useSelector((state) => state.theme.mode);
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [showProfile, setShowProfile] = useState(false);
  const [showMobileSearch, setShowMobileSearch] = useState(false);
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
          <Link to="/dashboard" className="navbar-brand" aria-label="Woodful Creations — go to dashboard">
            <span className="brand-mark">
              <img src="/logo-transparent.png" alt="Woodful Creations" className="brand-logo-img" />
            </span>
          </Link>
        </div>

        <div className="navbar-center">
          <GlobalSearch />
        </div>

        <div className="navbar-right">
          <button
            className="mobile-search-toggle"
            onClick={() => setShowMobileSearch((v) => !v)}
            title="Search"
            aria-label="Toggle search"
            aria-expanded={showMobileSearch}
          >
            <SearchIcon width={19} height={19} />
          </button>
          <button className="cart-toggle" onClick={onOpenCart} title="Purchase cart" aria-label="Open purchase cart">
            <CartIcon width={19} height={19} />
            {cartCount > 0 && <span className="cart-toggle-badge">{cartCount}</span>}
          </button>
          <button
            className="theme-toggle"
            onClick={() => dispatch(toggleTheme())}
            title={themeMode === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            aria-label={themeMode === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          >
            {themeMode === 'dark' ? <SunIcon width={18} height={18} /> : <MoonIcon width={18} height={18} />}
          </button>
          <NotificationBell />
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
      {showMobileSearch && (
        <div className="mobile-search-row">
          <GlobalSearch />
        </div>
      )}
    </nav>
  );
}

export default Navbar;
