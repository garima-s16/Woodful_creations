import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { authAPI } from '../utils/api';
import { loginStart, loginSuccess, loginFailure } from '../redux/slices/authSlice';
import '../styles/LoginPage.css';

function LoginPage() {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const performLogin = async (loginEmail, loginPassword) => {
    setError('');
    setLoading(true);
    dispatch(loginStart());

    try {
      const response = await authAPI.login(loginEmail, loginPassword);
      // The auth token itself lives in an HttpOnly cookie the browser now
      // holds automatically - we never touch it here or store it ourselves.
      dispatch(loginSuccess(response.data));
      navigate('/', { replace: true });
    } catch (err) {
      const message = err.response?.data?.detail || 'Login failed. Please try again.';
      setError(message);
      dispatch(loginFailure(message));
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (e) => {
    e.preventDefault();
    performLogin(email, password);
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-box">
          <div className="login-header">
            <div className="logo-circle">W</div>
            <h1>Woodful Creations</h1>
            <p>Business Management System</p>
          </div>

          <form onSubmit={handleLogin} className="login-form">
            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                required
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                disabled={loading}
              />
            </div>

            {error && <div className="error-message">{error}</div>}

            <button type="submit" className="login-button" disabled={loading}>
              {loading ? 'Logging in...' : 'Login'}
            </button>
          </form>
        </div>

        <div className="login-illustration">
          <div className="illustration-content">
            <h2>Welcome to Woodful</h2>
            <p>Comprehensive business management system for woodcraft and furniture design</p>
            <ul className="features-list">
              <li>Stock Inventory Management</li>
              <li>Cost Estimation</li>
              <li>Client Management</li>
              <li>Employee Attendance</li>
              <li>AI Assistant Chat</li>
              <li>Advanced Analytics</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
