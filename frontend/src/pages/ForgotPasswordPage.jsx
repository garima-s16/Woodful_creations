import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Link } from 'react-router-dom';
import { authAPI } from '../utils/api';
import BrandBackdrop from '../components/BrandBackdrop';
import Footer from '../components/Footer';
import '../styles/LoginPage.css';

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

export default ForgotPasswordPage;
