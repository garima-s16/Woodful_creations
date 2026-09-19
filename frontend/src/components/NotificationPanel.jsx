// GlobalSearch and NotificationBell - split out of Navigation.jsx during the
// page-load performance hardening pass (area 23: frontend bundle size).
//
// Both are rendered ONLY inside Navbar.jsx, which is already
// React.lazy()-loaded in App.jsx (only mounted after a successful login,
// see App.jsx's comment above `const Navbar = React.lazy(...)`). They used
// to live in the same file as BrandLogo/BrandBackdrop/Footer, which
// AuthPages.jsx (the actual login screen) imports statically - so even
// though NotificationBell/GlobalSearch never render pre-login, webpack was
// forced to include their code (and, worse, the `motion/react` animation
// library NotificationBell pulls in for its panel's open/close transition)
// in the same synchronously-loaded module as the login page's own brand
// assets, putting all of it in the critical login bundle.
//
// Moving them here means this file - and the `motion/react` import inside
// it - is only ever reachable through Navbar's existing lazy chunk, not the
// login critical path. Nothing about their behavior changed, only which
// file they live in.

import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { SearchIcon } from './icons';
import { notificationsAPI, searchAPI } from '../utils/api';
import { AnimatePresence, motion } from 'motion/react';
import '../styles/components.css';

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
  // Guards against an overlapping in-flight fetch (e.g. the panel
  // closing and reopening again before the first request resolves) -
  // not against re-fetching on every open, which is intentional (see
  // the effect below).
  const fetchingNotificationsRef = useRef(false);

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

  // Fetches the full notification list exactly when the panel
  // transitions to open - not on every mouseenter while it's already
  // open (previously the hover handler called this directly, so
  // moving the mouse in and out of an already-open panel re-fetched
  // the whole list each time), and never overlapping a fetch already
  // in flight. Keyed on `open` alone, so it fires once per genuine
  // open transition regardless of what triggered it (click, hover, or
  // the openRequestCount effect below).
  useEffect(() => {
    if (!open) return;
    if (fetchingNotificationsRef.current) return;
    fetchingNotificationsRef.current = true;
    notificationsAPI.list()
      .then((res) => setNotifications(res.data))
      .catch(() => setNotifications([]))
      .finally(() => { fetchingNotificationsRef.current = false; });
  }, [open]);

  // Hover-intent delay: `open` is what triggers the fetch above, and
  // the bell wrapper's onMouseEnter below sets `open` - so without
  // this, simply passing the cursor over the bell on the way to
  // somewhere else fetched the full notification list every time, not
  // just a deliberate check. A brief delay before actually opening
  // means only a hover the user holds for a moment (real intent)
  // triggers it; a click still opens (and fetches) immediately via
  // handleToggle below, completely unaffected by this delay.
  const hoverIntentTimerRef = useRef(null);
  const handleBellMouseEnter = () => {
    if (hoverIntentTimerRef.current) return;
    hoverIntentTimerRef.current = setTimeout(() => {
      hoverIntentTimerRef.current = null;
      setOpen(true);
    }, 220);
  };
  const handleBellMouseLeave = () => {
    if (hoverIntentTimerRef.current) {
      clearTimeout(hoverIntentTimerRef.current);
      hoverIntentTimerRef.current = null;
    }
    setOpen(false);
  };
  useEffect(() => () => {
    if (hoverIntentTimerRef.current) clearTimeout(hoverIntentTimerRef.current);
  }, []);

  useEffect(() => {
    if (openRequestCount > 0) {
      setOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openRequestCount]);

  const handleToggle = () => {
    setOpen((v) => !v);
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
      onMouseEnter={handleBellMouseEnter}
      onMouseLeave={handleBellMouseLeave}
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

export { GlobalSearch, NotificationBell };
