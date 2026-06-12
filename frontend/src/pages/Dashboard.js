import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Dashboard.css';

function Dashboard({ userRole }) {
  const [stats, setStats] = useState({
    totalProducts: 0,
    lowStockItems: 0,
    pendingEstimates: 0,
    activeClients: 0,
    pendingPayments: 0
  });
  const [recentActivity, setRecentActivity] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/dashboard', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      setStats(response.data.stats);
      setRecentActivity(response.data.recentActivity);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      // Use mock data for demo
      setStats({
        totalProducts: 24,
        lowStockItems: 3,
        pendingEstimates: 5,
        activeClients: 8,
        pendingPayments: 12000
      });
      setRecentActivity([
        { id: 1, type: 'inventory', message: 'Walnut wood stock updated', timestamp: new Date() },
        { id: 2, type: 'estimate', message: 'Estimate #001 created for client', timestamp: new Date() },
        { id: 3, type: 'client', message: 'New client added', timestamp: new Date() }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return <div className="dashboard"><div className="loading">Loading...</div></div>;
  }

  return (
    <div className="dashboard">
      <h1>Dashboard</h1>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon inventory">I</div>
          <div className="stat-info">
            <h3>Total Products</h3>
            <p className="stat-value">{stats.totalProducts}</p>
          </div>
        </div>

        <div className="stat-card warning">
          <div className="stat-icon warning">W</div>
          <div className="stat-info">
            <h3>Low Stock Items</h3>
            <p className="stat-value">{stats.lowStockItems}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon estimate">E</div>
          <div className="stat-info">
            <h3>Pending Estimates</h3>
            <p className="stat-value">{stats.pendingEstimates}</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon client">C</div>
          <div className="stat-info">
            <h3>Active Clients</h3>
            <p className="stat-value">{stats.activeClients}</p>
          </div>
        </div>

        {userRole === 'master' && (
          <div className="stat-card payment">
            <div className="stat-icon payment">P</div>
            <div className="stat-info">
              <h3>Pending Payments</h3>
              <p className="stat-value">Rs {stats.pendingPayments}</p>
            </div>
          </div>
        )}
      </div>

      <div className="dashboard-sections">
        <div className="section recent-activity">
          <h2>Recent Activity</h2>
          <div className="activity-list">
            {recentActivity.map(activity => (
              <div key={activity.id} className="activity-item">
                <span className="activity-type">{activity.type}</span>
                <span className="activity-message">{activity.message}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="section quick-actions">
          <h2>Quick Actions</h2>
          <div className="actions-grid">
            <button className="action-btn inventory-btn">Add Product</button>
            <button className="action-btn estimate-btn">Create Estimate</button>
            <button className="action-btn client-btn">Add Client</button>
            <button className="action-btn report-btn">Generate Report</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;