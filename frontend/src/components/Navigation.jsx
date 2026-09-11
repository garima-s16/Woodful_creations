// Navigation components: mobile bottom nav, global search, notification
// bell, footer, and the auth-page brand backdrop. Combines the former
// MobileBottomNav.jsx, GlobalSearch.jsx, NotificationBell.jsx, Footer.jsx,
// and BrandBackdrop.jsx.

import React, { useEffect, useRef, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { BellIcon, ChatIcon, HomeIcon, MenuIcon, SearchIcon, TaskIcon } from './icons';
import { openWithMessage } from '../redux/slices';
import { requestOpen } from '../redux/slices';
import { notificationsAPI, searchAPI } from '../utils/api';
import { AnimatePresence, motion } from 'motion/react';
import '../styles/components.css';

// --- MobileBottomNav.jsx ---
/* Mobile-only bottom navigation - a real mobile-first pattern, not the
 * desktop sidebar squeezed into a smaller space. Chat and Notifications
 * don't have their own routes (they're floating widgets), so they
 * dispatch through the same sibling-coordination slices those widgets
 * already watch, rather than duplicating their logic here. */
function MobileBottomNav({ onOpenMenu }) {
  const dispatch = useDispatch();

  return (
    <nav className="mobile-bottom-nav">
      <NavLink to="/dashboard" className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}>
        <HomeIcon className="mobile-nav-icon" />
        <span>Home</span>
      </NavLink>
      <NavLink to="/daily-tasks" className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}>
        <TaskIcon className="mobile-nav-icon" />
        <span>Work</span>
      </NavLink>
      <button type="button" className="mobile-nav-item" onClick={() => dispatch(openWithMessage(' '))}>
        <ChatIcon className="mobile-nav-icon" />
        <span>Chat</span>
      </button>
      <button type="button" className="mobile-nav-item" onClick={() => dispatch(requestOpen())}>
        <BellIcon className="mobile-nav-icon" />
        <span>Alerts</span>
      </button>
      <button type="button" className="mobile-nav-item" onClick={onOpenMenu}>
        <MenuIcon className="mobile-nav-icon" />
        <span>More</span>
      </button>
    </nav>
  );
}

// --- GlobalSearch.jsx ---
function GlobalSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef(null);

  // A live-search-as-you-type field genuinely needs debouncing (unlike
  // the page-level submit-triggered searches elsewhere in the app) -
  // without it, every keystroke would fire its own request.
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    const timer = setTimeout(() => {
      searchAPI.query(query.trim())
        .then((res) => setResults(res.data))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (result) => {
    setQuery('');
    setResults([]);
    setOpen(false);
    navigate(result.path);
  };

  return (
    <div className="global-search" ref={containerRef}>
      <SearchIcon className="global-search-icon" width={16} height={16} />
      <input
        type="text"
        className="global-search-input"
        placeholder="Search clients, orders, materials..."
        aria-label="Global search"
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
      />
      {open && query.trim() && (
        <div className="global-search-results">
          {loading && <div className="global-search-status">Searching...</div>}
          {!loading && results.length === 0 && (
            <div className="global-search-status">No matches for &ldquo;{query}&rdquo;.</div>
          )}
          {!loading && results.map((r) => (
            <button
              key={`${r.type}-${r.id}`}
              className="global-search-result"
              onClick={() => handleSelect(r)}
            >
              <span className="global-search-result-type">{r.type}</span>
              <span className="global-search-result-label">{r.label}</span>
              {r.sublabel && <span className="global-search-result-sublabel">{r.sublabel}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// --- NotificationBell.jsx ---
const SEVERITY_DOT = { CRITICAL: 'notif-dot-critical', WARNING: 'notif-dot-warning', SUCCESS: 'notif-dot-success', INFO: 'notif-dot-info' };

function timeGroup(dateStr) {
  const date = new Date(dateStr);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  if (date >= startOfToday) return 'Today';
  if (date >= startOfYesterday) return 'Yesterday';
  return 'Earlier';
}

function NotificationBell() {
  const navigate = useNavigate();
  const openRequestCount = useSelector((state) => state.notificationUi.openRequestCount);
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const panelRef = useRef(null);

  const loadCount = () => {
    notificationsAPI.unreadCount().then((res) => setUnreadCount(res.data.count)).catch(() => {});
  };

  useEffect(() => {
    loadCount();
    const interval = setInterval(loadCount, 60000); // periodic refresh, not just on open
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const handleClickOutside = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const fetchNotifications = () => {
    notificationsAPI.list().then((res) => setNotifications(res.data)).catch(() => setNotifications([]));
  };

  useEffect(() => {
    if (openRequestCount > 0) {
      setOpen(true);
      fetchNotifications();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openRequestCount]);

  const handleToggle = () => {
    const next = !open;
    setOpen(next);
    if (next) fetchNotifications();
  };

  const handleItemClick = async (notif) => {
    if (!notif.is_read) {
      try {
        await notificationsAPI.markRead(notif.id);
        setNotifications((prev) => prev.map((n) => (n.id === notif.id ? { ...n, is_read: true } : n)));
        loadCount();
      } catch {
        // Non-fatal - still navigate even if marking read failed.
      }
    }
    if (notif.action_path) {
      navigate(notif.action_path);
      setOpen(false);
    }
  };

  const handleMarkAllRead = async () => {
    await notificationsAPI.markAllRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
  };

  const grouped = notifications.reduce((acc, n) => {
    const g = timeGroup(n.created_at);
    (acc[g] = acc[g] || []).push(n);
    return acc;
  }, {});
  const groupOrder = ['Today', 'Yesterday', 'Earlier'].filter((g) => grouped[g]?.length);

  return (
    <div
      className="notification-bell" ref={panelRef}
      onMouseEnter={() => { setOpen(true); fetchNotifications(); }}
      onMouseLeave={() => setOpen(false)}
    >
      <button className="notification-bell-toggle" onClick={handleToggle} aria-label="Notifications">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 01-3.46 0" />
        </svg>
        {unreadCount > 0 && <span className="notification-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="notification-panel"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="notification-panel-header">
              <span>Notifications</span>
              {unreadCount > 0 && <button className="btn-link" onClick={handleMarkAllRead}>Mark all as read</button>}
            </div>
            <div className="notification-panel-body">
              {notifications.length === 0 ? (
                <div className="notification-empty">Nothing needs your attention right now.</div>
              ) : (
                groupOrder.map((group) => (
                  <div key={group}>
                    <div className="notification-group-label">{group}</div>
                    {grouped[group].map((n, ni) => (
                      <motion.button
                        key={n.id}
                        className={`notification-item ${n.is_read ? 'notification-item-read' : ''}`}
                        onClick={() => handleItemClick(n)}
                        initial={{ opacity: 0, x: -4 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.14, delay: Math.min(ni, 6) * 0.03 }}
                      >
                        <span className={`notification-dot ${SEVERITY_DOT[n.severity] || 'notif-dot-info'}`} />
                        <span className="notification-item-text">
                          <strong>{n.title}</strong>
                          <span>{n.message}</span>
                        </span>
                      </motion.button>
                    ))}
                  </div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// --- Footer.jsx ---
function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="app-footer">
      <div className="app-footer-inner">
        <p>&copy; {year} Woodful Creations. All rights reserved. Founded by Nikhil Soni.</p>
      </div>
    </footer>
  );
}

// --- BrandBackdrop.jsx ---
/**
 * Login brand-panel backdrop.
 *
 * Composed from Woodful's actual visual vocabulary rather than generic
 * decoration: a cabinet/drawer-front elevation (proportions a cabinetmaker
 * would actually draw), a finger-joint seam, corner joinery notches, and
 * fine architectural dimension lines. No photography exists for the
 * product, so this is original vector art, not a stock substitute.
 */
function BrandBackdrop() {
  return (
    <svg className="brand-backdrop" viewBox="0 0 800 1000" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="focalGlow" cx="50%" cy="50%" r="60%">
          <stop offset="0%" stopColor="var(--color-gold)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--color-gold)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Soft glow grounding the focal composition, upper-left */}
      <circle cx="300" cy="330" r="320" fill="url(#focalGlow)" />

      {/* Focal piece: a cabinet/drawer-front elevation, drawn the way a
          joiner would spec it - carcass, reveals, pulls, joinery marks */}
      <g transform="translate(130,150)" opacity="0.85">
        {/* Outer carcass */}
        <rect x="0" y="0" width="320" height="420" rx="2" fill="none" stroke="var(--color-tan)" strokeWidth="1.25" opacity="0.55" />

        {/* Corner joinery notches (mortise-and-tenon reference) */}
        <path d="M0,0 L18,0 L18,7 L7,7 L7,18 L0,18 Z" fill="var(--color-gold)" opacity="0.28" />
        <path d="M320,420 L302,420 L302,413 L313,413 L313,402 L320,402 Z" fill="var(--color-gold)" opacity="0.28" />

        {/* Three drawer fronts with reveal gaps */}
        {[0, 1, 2].map((i) => {
          const gap = 16;
          const h = (420 - gap * 4) / 3;
          const y = gap + i * (h + gap);
          return (
            <g key={i}>
              <rect x={gap} y={y} width={320 - gap * 2} height={h} rx="1.5"
                fill="var(--color-wood)" opacity={0.1 + i * 0.03}
                stroke="rgba(243, 237, 225, 0.10)" strokeWidth="1" />
              {/* pull */}
              <circle cx={320 - gap * 2 - 22} cy={y + h / 2} r="4.5" fill="var(--color-gold-soft)" opacity="0.55" />
              {/* faint grain lines for material texture */}
              <path d={`M${gap + 14},${y + h * 0.35} q ${(320 - gap * 2 - 28) / 2} 10 ${320 - gap * 2 - 28} 0`}
                fill="none" stroke="var(--color-tan)" strokeWidth="0.6" opacity="0.18" />
              <path d={`M${gap + 14},${y + h * 0.65} q ${(320 - gap * 2 - 28) / 2} -8 ${320 - gap * 2 - 28} 0`}
                fill="none" stroke="var(--color-tan)" strokeWidth="0.6" opacity="0.14" />
            </g>
          );
        })}

        {/* Finger-joint seam running along the base, connecting the piece
            to the copy below */}
        <g transform="translate(0,442)">
          <path
            d="M0,0 L20,0 L20,10 L40,10 L40,0 L60,0 L60,10 L80,10 L80,0 L100,0 L100,10 L120,10 L120,0 L140,0 L140,10 L160,10 L160,0 L180,0 L180,10 L200,10 L200,0 L220,0 L220,10 L240,10 L240,0 L260,0 L260,10 L280,10 L280,0 L300,0 L300,10 L320,10"
            fill="none" stroke="var(--color-gold-soft)" strokeWidth="1" opacity="0.35" />
        </g>
      </g>

      {/* Fine architectural dimension lines - precision cue */}
      <g stroke="var(--color-tan)" strokeWidth="0.6" opacity="0.16">
        <line x1="0" y1="70" x2="800" y2="20" />
        <line x1="0" y1="640" x2="800" y2="600" />
        <line x1="0" y1="900" x2="800" y2="960" />
      </g>

      {/* Precision tick marks, like a cutting guide, anchoring the bottom copy */}
      <g stroke="var(--color-gold)" strokeWidth="1" opacity="0.28">
        {Array.from({ length: 14 }).map((_, i) => (
          <line key={i} x1={40 + i * 55} y1="960" x2={40 + i * 55} y2={i % 2 === 0 ? 980 : 972} />
        ))}
      </g>
    </svg>
  );
}

export { MobileBottomNav, GlobalSearch, NotificationBell, Footer, BrandBackdrop };
