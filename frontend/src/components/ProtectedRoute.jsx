import React from 'react';
import { useSelector } from 'react-redux';
import { Navigate } from 'react-router-dom';

function ProtectedRoute({ children }) {
  const { isAuthenticated, checkingSession } = useSelector((state) => state.auth);

  if (checkingSession) {
    return null; // wait for the initial /api/auth/me check before deciding
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

export default ProtectedRoute;
