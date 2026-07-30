import React, { useState, useEffect } from 'react';
import { dashboardAPI } from '../utils/api';
import ChatWidget from '../components/ChatWidget';
import '../styles/pages/DashboardPage.css';

function DashboardPage({ user }) {
  const [stats, setStats] = useState(null);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const response = await dashboardAPI.getDashboard();
      setStats(response.data.stats);
      setActivity(response.data.recentActivity);
    } catch (error) {
      console.error('Error fetching dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="dashboard-loading">Loading dashboard...</div>;
  }

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <h1>Dashboard</h1>
        <p className="welcome-text">Welcome back, {user?.name}</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">I</div>
          <div className="stat-content">
            <h3>Total Products</h3>
            <p className="stat-value">{stats?.totalProducts || 0}</p>
          </div>
        </div>

        <div className="stat-card warning">
          <div className="stat-icon">W</div>
          <div className="stat-content">
            <h3>Low Stock Items</h3>
            <p className="stat-value">{stats?.lowStockItems || 0}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">E</div>
          <div className="stat-content">
            <h3>Pending Estimates</h3>
            <p className="stat-value">{stats?.pendingEstimates || 0}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">C</div>
          <div className="stat-content">
            <h3>Active Clients</h3>
            <p className="stat-value">{stats?.activeClients || 0}</p>
          </div>
        </div>

        {user?.role === 'master' && (
          <div className="stat-card success">
            <div className="stat-icon">P</div>
            <div className="stat-content">
              <h3>Pending Payments</h3>
              <p className="stat-value">Rs {stats?.pendingPayments || 0}</p>
            </div>
          </div>
        )}
      </div>

      <div className="dashboard-sections">
        <div className="section">
          <h2>Recent Activity</h2>
          <div className="activity-list">
            {activity.map((item) => (
              <div key={item.id} className="activity-item">
                <span className="activity-type">{item.type}</span>
                <span className="activity-text">{item.message}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="section">
          <h2>Quick Actions</h2>
          <div className="actions-grid">
            <button className="action-button">Add Product</button>
            <button className="action-button">Create Estimate</button>
            <button className="action-button">Add Client</button>
            <button className="action-button">View Reports</button>
          </div>
        </div>
      </div>

      <ChatWidget />
    </div>
  );
}

export default DashboardPage;