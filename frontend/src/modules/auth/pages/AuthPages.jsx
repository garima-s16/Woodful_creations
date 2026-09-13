// Auth pages: login, forgot/reset password.
// Combines the former LoginPage.jsx, ForgotPasswordPage.jsx, and
// ResetPasswordPage.jsx.
//
// Defect repair (F138 P1): UsersPage.jsx used to live in this same
// file/module. LoginPage/ForgotPasswordPage/ResetPasswordPage are
// deliberately imported EAGERLY (statically) at the top of App.jsx so
// the login screen renders without waiting on a dynamic import - but
// that meant UsersPage's code (a master-only admin page, never needed
// before authentication) rode along in the same webpack chunk purely
// because it shared this file, silently defeating the
// `React.lazy(() => import('.../AuthPages').then(m => m.UsersPage))`
// wrapper App.jsx had around it (a lazy import of a module already
// forced into the main bundle by a sibling static import produces no
// real code-splitting). UsersPage now lives in its own file
// (./UsersPage.jsx) so it genuinely splits out of the login-critical
// path; this file keeps only what the public, pre-authentication
// pages actually need.
import React, { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { authAPI, resetSessionInvalidationGuard } from '../../../utils/api';
import { loginFailure, loginStart, loginSuccess } from '../../../redux/slices';
import { BrandBackdrop, Footer } from '../../../components/Navigation';
import '../../../styles/modules.css';

// --- LoginPage.jsx ---
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
      // This login just started a brand new session - the interceptor's
      // single-flight "session invalid" guard (see utils/api.js) must be
      // able to fire again for THIS session's own future expiry/
      // invalidation, not stay permanently tripped by whatever the
      // previous session (or the pre-login "not authenticated yet"
      // state) last did with it.
      resetSessionInvalidationGuard();
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
            <p className="login-brand-descriptor">From the first estimate to the finished piece, every order lives here.</p>
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
            <p className="login-form-subtitle">Good to see you. Sign in to continue.</p>

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
            <p className="login-form-subtitle" style={{ marginTop: 'var(--space-5)' }}>
              <Link to="/forgot-password">Forgot your password?</Link>
            </p>
          </motion.div>
        </div>
      </div>
      <Footer />
    </div>
  );
}

// --- ForgotPasswordPage.jsx ---
function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authAPI.forgotPassword(identifier);
      // Always show the same confirmation regardless of whether an
      // account actually exists for this identifier - the backend
      // deliberately returns the same response either way, and this
      // page must not undo that by branching on the result.
      setSubmitted(true);
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
            {submitted ? (
              <>
                <h1>Check your email</h1>
                <p className="login-form-subtitle">
                  If an account exists for that email or username, a password reset link has been sent.
                  It expires in 30 minutes and can only be used once.
                </p>
                <Link to="/login" className="login-button" style={{ display: 'block', textAlign: 'center', textDecoration: 'none', marginTop: 'var(--space-5)' }}>
                  Back to Sign In
                </Link>
              </>
            ) : (
              <>
                <h1>Forgot your password?</h1>
                <p className="login-form-subtitle">Enter your email or username and we'll send you a reset link.</p>

                <form onSubmit={handleSubmit} className="login-form">
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
                    {loading ? 'Sending...' : 'Send Reset Link'}
                  </motion.button>
                </form>

                <p className="login-form-subtitle" style={{ marginTop: 'var(--space-5)' }}>
                  <Link to="/login">Back to Sign In</Link>
                </p>
              </>
            )}
          </motion.div>
        </div>
      </div>
      <Footer />
    </div>
  );
}

// --- ResetPasswordPage.jsx ---
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
export { LoginPage, ForgotPasswordPage, ResetPasswordPage };
