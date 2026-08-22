import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { authAPI } from '../utils/api';
import BrandBackdrop from '../components/BrandBackdrop';
import Footer from '../components/Footer';
import '../styles/LoginPage.css';

function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (newPassword !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }
    setLoading(true);
    try {
      await authAPI.resetPassword(token, newPassword);
      setDone(true);
      setTimeout(() => navigate('/login', { replace: true }), 2500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to reach the server. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-brand-panel">
          <BrandBackdrop />
          <div className="login-brand-top">
            <img src="/logo-transparent.png" alt="Woodful Creations" className="login-logo-small" />
          </div>
          <div className="login-brand-content">
            <p className="login-brand-statement">Precision crafted, order by order.</p>
            <p className="login-brand-descriptor">Furniture &middot; Materials &middot; Production &middot; Projects</p>
          </div>
        </div>

        <div className="login-form-panel">
          <motion.div
            className="login-form-wrap"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
          >
            {!token ? (
              <>
                <h1>Invalid reset link</h1>
                <p className="login-form-subtitle">This link is missing its reset token. Please request a new one.</p>
                <Link to="/forgot-password" className="login-button" style={{ display: 'block', textAlign: 'center', textDecoration: 'none', marginTop: 'var(--space-5)' }}>
                  Request New Link
                </Link>
              </>
            ) : done ? (
              <>
                <h1>Password reset</h1>
                <p className="login-form-subtitle">Your password has been changed. Redirecting you to sign in...</p>
              </>
            ) : (
              <>
                <h1>Set a new password</h1>
                <p className="login-form-subtitle">Choose a new password for your account.</p>

                <form onSubmit={handleSubmit} className="login-form">
                  <div className="form-group">
                    <label htmlFor="newPassword">New Password</label>
                    <input
                      id="newPassword"
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="At least 8 characters"
                      required
                      minLength={8}
                      disabled={loading}
                      autoComplete="new-password"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="confirmPassword">Confirm New Password</label>
                    <input
                      id="confirmPassword"
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter your new password"
                      required
                      minLength={8}
                      disabled={loading}
                      autoComplete="new-password"
                    />
                  </div>

                  <AnimatePresence>
                    {error && (
                      <motion.div
                        className="error-message"
                        initial={{ opacity: 0, y: -6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.18 }}
                      >
                        {error}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <motion.button
                    type="submit" className="login-button" disabled={loading}
                    whileTap={{ scale: 0.98 }}
                  >
                    {loading ? 'Resetting...' : 'Reset Password'}
                  </motion.button>
                </form>
              </>
            )}
          </motion.div>
        </div>
      </div>
      <Footer />
    </div>
  );
}

export default ResetPasswordPage;
