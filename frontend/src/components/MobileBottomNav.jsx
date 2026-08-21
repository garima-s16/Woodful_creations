import React from 'react';
import { NavLink } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { HomeIcon, TaskIcon, ChatIcon, BellIcon, MenuIcon } from './icons';
import { openWithMessage } from '../redux/slices/chatUiSlice';
import { requestOpen } from '../redux/slices/notificationUiSlice';
import '../styles/components/MobileBottomNav.css';

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

export default MobileBottomNav;
