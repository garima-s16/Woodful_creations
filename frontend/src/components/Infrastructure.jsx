// Infrastructure components: route protection, loading shell, and
// offline banner. Combines the former ProtectedRoute.jsx,
// LoadingShell.jsx, and OfflineBanner.jsx.
import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { Navigate } from 'react-router-dom';
import { onQueueChange, replayQueue, watchConnectivity } from '../utils/utils';
import '../styles/components.css';

// --- ProtectedRoute.jsx ---
function ProtectedRoute({ children }) {
  const { isAuthenticated, checkingSession, connectionError } = useSelector((state) => state.auth);

  if (checkingSession) {
    return <LoadingShell />; // show the app shell while the initial /api/auth/me check resolves, instead of a blank screen
  }

  if (connectionError) {
    // The initial session check never reached the server at all - a
    // genuinely different situation from "not logged in", and one
    // that redirecting silently to /login would only make more
    // confusing (a login attempt would just fail the same way).
    return (
      <div className="connection-error-shell" role="alert">
        <h2>Unable to connect to Woodful server</h2>
        <p>Please check that the backend is running, then reload this page.</p>
        <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
          Retry
        </button>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

// --- LoadingShell.jsx ---
/**
 * Shown in two places, both of which previously rendered nothing at
 * all (Suspense fallback={null} in App.jsx, and `return null` in
 * ProtectedRoute.jsx while checkingSession is true) - leaving the
 * browser looking frozen with no feedback during route-chunk loading
 * or the initial auth check. This component performs no API calls of
 * its own; it is purely a visual placeholder that resolves the moment
 * the real content is ready.
 */
function LoadingShell() {
  return (
    <div className="loading-shell" role="status" aria-live="polite" aria-label="Loading Woodful">
      <div className="loading-shell-navbar">
        <div className="loading-shell-bar loading-shell-logo" />
        <div className="loading-shell-bar loading-shell-icon" />
      </div>
      <div className="loading-shell-body">
        <div className="loading-shell-sidebar">
          {Array.from({ length: 6 }).map((_, i) => (
            <div className="loading-shell-bar loading-shell-nav-item" key={i} />
          ))}
        </div>
        <div className="loading-shell-content">
          <div className="loading-shell-bar loading-shell-title" />
          <div className="loading-shell-cards">
            {Array.from({ length: 3 }).map((_, i) => (
              <div className="loading-shell-card" key={i} />
            ))}
          </div>
          <div className="loading-shell-bar loading-shell-table" />
        </div>
      </div>
      <span className="sr-only">Loading Woodful, please wait...</span>
    </div>
  );
}

// --- OfflineBanner.jsx ---
function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(true);
  const [queueLength, setQueueLength] = useState(0);
  const [justReconnected, setJustReconnected] = useState(false);

  useEffect(() => {
    const unsubscribeQueue = onQueueChange((queue) => setQueueLength(queue.length));
    const stopWatching = watchConnectivity((online) => {
      setIsOnline((wasOnline) => {
        if (!wasOnline && online) {
          setJustReconnected(true);
          setTimeout(() => setJustReconnected(false), 4000);
        }
        return online;
      });
      if (online) {
        replayQueue();
      }
    });
    return () => {
      unsubscribeQueue();
      stopWatching();
    };
  }, []);

  if (isOnline && !justReconnected && queueLength === 0) {
    return null;
  }

  return (
    <div className={`offline-banner ${isOnline ? 'offline-banner-ok' : 'offline-banner-warn'}`} role="status">
      {!isOnline && (
        <span>
          You're offline. You can keep working - changes will be saved locally and sent once you're back online.
          {queueLength > 0 && ` (${queueLength} change${queueLength === 1 ? '' : 's'} waiting)`}
        </span>
      )}
      {isOnline && justReconnected && (
        <span>Back online{queueLength > 0 ? ` - sending ${queueLength} saved change${queueLength === 1 ? '' : 's'}...` : '.'}</span>
      )}
      {isOnline && !justReconnected && queueLength > 0 && (
        <span>{queueLength} change{queueLength === 1 ? '' : 's'} still pending - retrying...</span>
      )}
    </div>
  );
}

export { ProtectedRoute, LoadingShell, OfflineBanner };
