// Auth pages: login, forgot/reset password, and user management.
// Combines the former LoginPage.jsx, ForgotPasswordPage.jsx,
// ResetPasswordPage.jsx, and UsersPage.jsx.
import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { authAPI, usersAPI } from '../../../utils/api';
import { loginFailure, loginStart, loginSuccess } from '../../../redux/slices';
import { BrandBackdrop, Footer } from '../../../components/Navigation';
import { Alert, ConfirmDialog, Form, Modal, Table } from '../../../components/common/UI';
import { statusClass } from '../../../utils/utils';
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

// --- UsersPage.jsx ---
function UsersPage() {
  const { user } = useSelector((state) => state.auth);
  const isStrictlyMaster = user?.role === 'master';
  const [users, setUsers] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    usersAPI.list().then((res) => setUsers(res.data)).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to manage users.' : 'Unable to load users. Please try again.');
    }).finally(() => setPageLoading(false));
  };
  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await usersAPI.create(formData);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await usersAPI.update(editingUser.id, {
        full_name: formData.full_name, phone: formData.phone, role: formData.role,
        is_active: formData.is_active === 'true' || formData.is_active === true,
      });
      setEditingUser(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update user');
    } finally {
      setLoading(false);
    }
  };

  const [pendingDeactivate, setPendingDeactivate] = useState(null);
  const [deactivating, setDeactivating] = useState(false);
  const handleDeactivate = (user) => setPendingDeactivate(user);
  const confirmDeactivate = async () => {
    setError('');
    setDeactivating(true);
    try {
      await usersAPI.remove(pendingDeactivate.id);
      setPendingDeactivate(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove user');
      setPendingDeactivate(null);
    } finally {
      setDeactivating(false);
    }
  };

  const columns = [
    { key: 'username', label: 'Username' }, { key: 'full_name', label: 'Full Name' },
    { key: 'email', label: 'Email' }, { key: 'role', label: 'Role' },
    { key: 'is_active', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v ? 'Active' : 'Inactive')}`}>{v ? 'Active' : 'Inactive'}</span> },
    { key: 'cannot_be_deleted', label: 'Protected', render: (v) => v ? 'Yes' : 'No' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isStrictlyMaster ? <button className="btn-link" onClick={() => setEditingUser(row)}>Edit</button> : null
      ),
    },
    {
      key: 'remove_action', label: '', render: (v, row) => (
        !row.cannot_be_deleted && row.role !== 'master' && <button className="btn-link" onClick={() => handleDeactivate(row)} style={{ color: 'var(--danger)' }}>Remove</button>
      ),
    },
  ];

  const createFields = [
    { name: 'username', label: 'Username', required: true },
    { name: 'full_name', label: 'Full Name', required: true },
    { name: 'email', label: 'Email', type: 'email', required: true },
    { name: 'phone', label: 'Phone' },
    { name: 'password', label: 'Temporary Password', type: 'password', required: true, hint: 'The user should change this after first login.' },
    { name: 'role', label: 'Role', type: 'select', required: true, options: [
      { value: 'user', label: 'Employee (Limited Access)' }, { value: 'master', label: 'Master (Full Access)' },
    ] },
  ];

  const editFields = [
    { name: 'full_name', label: 'Full Name', required: true },
    { name: 'phone', label: 'Phone' },
    { name: 'role', label: 'Role', type: 'select', required: true, options: [
      { value: 'user', label: 'Employee (Limited Access)' }, { value: 'master', label: 'Master (Full Access)' },
    ] },
    { name: 'is_active', label: 'Status', type: 'select', options: [
      { value: 'true', label: 'Active' }, { value: 'false', label: 'Inactive' },
    ] },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Users</h1>
          <p className="page-summary">Manage login accounts and their Master/User access level.</p>
        </div>
        {isStrictlyMaster && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add User</button>}
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={users} loading={pageLoading} error={loadError} onRetry={load} emptyMessage="No users found." />

      <Modal isOpen={showAdd} title="Add User" onClose={() => setShowAdd(false)}>
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Create User" />
      </Modal>

      <Modal isOpen={!!editingUser} title={`Edit ${editingUser?.username || ''}`} onClose={() => setEditingUser(null)}>
        {editingUser && (
          <Form
            fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
            initialValues={{
              full_name: editingUser.full_name, phone: editingUser.phone,
              role: editingUser.role, is_active: String(editingUser.is_active),
            }}
          />
        )}
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDeactivate}
        title="Remove Access"
        message={pendingDeactivate ? `Remove ${pendingDeactivate.username}'s access? This can be reversed by an administrator.` : ''}
        confirmLabel="Remove Access"
        onConfirm={confirmDeactivate}
        onCancel={() => setPendingDeactivate(null)}
        loading={deactivating}
      />
    </div>
  );
}

export { LoginPage, ForgotPasswordPage, ResetPasswordPage, UsersPage };
