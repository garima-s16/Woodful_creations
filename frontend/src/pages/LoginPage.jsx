import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence, MotionConfig } from 'motion/react';
import { Link, useNavigate } from 'react-router-dom';
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
  const [parallaxOffset, setParallaxOffset] = useState({ x: 0, y: 0 });
  const brandPanelRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) return undefined; // parallax is a decorative extra, never shown to users who asked for less motion

    const MAX_OFFSET = 10; // px - subtle, "this has depth", never "this is showing off"

    const handlePointerMove = (e) => {
      if (rafRef.current) return; // already have a frame queued - drop this event rather than queue more work
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        const panel = brandPanelRef.current;
        if (!panel) return;
        const rect = panel.getBoundingClientRect();
        const relX = (e.clientX - rect.left) / rect.width - 0.5; // -0.5..0.5
        const relY = (e.clientY - rect.top) / rect.height - 0.5;
        setParallaxOffset({ x: relX * MAX_OFFSET * 2, y: relY * MAX_OFFSET * 2 });
      });
    };

    const panel = brandPanelRef.current;
    const handlePointerLeave = () => setParallaxOffset({ x: 0, y: 0 });
    if (panel) {
      panel.addEventListener('mousemove', handlePointerMove);
      panel.addEventListener('mouseleave', handlePointerLeave);
    }
    return () => {
      if (panel) {
        panel.removeEventListener('mousemove', handlePointerMove);
        panel.removeEventListener('mouseleave', handlePointerLeave);
      }
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

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
    <MotionConfig reducedMotion="user">
    <div className="login-page">
      <div className="login-container">
        <div className="login-brand-panel" ref={brandPanelRef}>
          <motion.div
            initial={{ opacity: 0, scale: 1.04 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            style={{ position: 'absolute', inset: 0 }}
          >
            <BrandBackdrop offset={parallaxOffset} />
          </motion.div>
          <motion.div
            className="login-brand-top"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          >
            <img src="/logo-transparent.png" alt="Woodful Creations" className="login-logo-mark" />
          </motion.div>
          <motion.div
            className="login-brand-content"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.28, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="login-brand-statement">Precision crafted, order by order.</p>
            <p className="login-brand-descriptor">Furniture &middot; Materials &middot; Production &middot; Projects</p>
          </motion.div>
        </div>

        <div className="login-form-panel">
          <motion.div
            className="login-form-wrap"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <h1>Sign in to Woodful</h1>
            <p className="login-form-subtitle">Welcome back — let's get to work.</p>

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
                <div className="form-label-row">
                  <label htmlFor="password">Password</label>
                  <Link to="/forgot-password" className="forgot-link">Forgot password?</Link>
                </div>
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
                whileHover={loading ? {} : { y: -1 }}
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
    </MotionConfig>
  );
}

export default LoginPage;
