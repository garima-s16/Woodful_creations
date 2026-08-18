import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { authAPI } from '../utils/api';
import { loginStart, loginSuccess, loginFailure } from '../redux/slices/authSlice';
import BrandBackdrop from '../components/BrandBackdrop';
import Footer from '../components/Footer';
import '../styles/LoginPage.css';

function EyeIcon({ visible }) {
  return visible ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3l18 18" /><path d="M10.6 10.6a3 3 0 004.2 4.2" />
      <path d="M9.5 5.2A9.8 9.8 0 0112 5c6.5 0 10 7 10 7a13.6 13.6 0 01-3.1 3.9M6.6 6.6C4 8.3 2 12 2 12a13.6 13.6 0 004.1 4.6" />
    </svg>
  );
}

function LoginPage() {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const performLogin = async (loginIdentifier, loginPassword) => {
    setError('');
    setLoading(true);
    dispatch(loginStart());

    try {
      const response = await authAPI.login(loginIdentifier, loginPassword);
      // The auth token itself lives in an HttpOnly cookie the browser now
      // holds automatically - we never touch it here or store it ourselves.
      dispatch(loginSuccess(response.data));
      navigate('/', { replace: true });
    } catch (err) {
      // The backend distinguishes "no account with that email/username", "incorrect
      // password", and "account deactivated" - this just passes that
      // message straight through. A network/server-level failure (no
      // response at all) falls back to a distinct generic message.
      const message = err.response?.data?.detail || 'Unable to reach the server. Please check your connection and try again.';
      setError(message);
      dispatch(loginFailure(message));
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (e) => {
    e.preventDefault();
    performLogin(identifier, password);
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
          </div>
        </div>

        <div className="login-form-panel">
          <motion.div
            className="login-form-wrap"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
          >
            <h1>Sign in to Woodful</h1>
            <p className="login-form-subtitle">Enter your credentials to continue.</p>

            <form onSubmit={handleLogin} className="login-form">
              <div className="form-group">
                <label htmlFor="identifier">Email or Username</label>
                <input
                  id="identifier"
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="your@email.com or username"
                  required
                  disabled={loading}
                  autoComplete="username"
                />
              </div>

              <div className="form-group">
                <label htmlFor="password">Password</label>
                <div className="password-input-row">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    required
                    disabled={loading}
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    <EyeIcon visible={showPassword} />
                  </button>
                </div>
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
                {loading ? 'Signing in...' : 'Sign In'}
              </motion.button>
            </form>
          </motion.div>
        </div>
      </div>
      <Footer />
    </div>
  );
}

export default LoginPage;
