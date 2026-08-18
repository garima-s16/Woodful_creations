import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { notificationsAPI } from '../utils/api';
import '../styles/components/NotificationBell.css';

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

export default NotificationBell;
