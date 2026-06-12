import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../utils/api';
import '../styles/LoginPage.css';

function LoginPage({ onLogin }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await authAPI.login(email, password);
      const { token, user } = response.data;

      onLogin(user, token);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.message || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setLoading(true);
    try {
      const response = await authAPI.login('nikhil@woodful.com', 'nikhil123');
      const { token, user } = response.data;

      onLogin(user, token);
      navigate('/dashboard');
    } catch (err) {
      setError('Demo login failed. Please try with email/password.');
    } finally {
      setLoading(false);
    }
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

          <div className="demo-section">
            <p>Try Demo Account</p>
            <button
              type="button"
              className="demo-button"
              onClick={handleDemoLogin}
              disabled={loading}
            >
              Demo Login
            </button>
          </div>

          <div className="test-credentials">
            <h4>Test Credentials</h4>
            <p>Master: nikhil@woodful.com / nikhil123</p>
            <p>Master: garima@woodful.com / garima123</p>
            <p>User: user@woodful.com / user123</p>
          </div>
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