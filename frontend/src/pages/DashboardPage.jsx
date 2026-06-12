import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/pages/DashboardPage.css';
import StockCard from '../components/dashboard/StockCard';
import QuickStats from '../components/dashboard/QuickStats';
import RecentActivity from '../components/dashboard/RecentActivity';

function DashboardPage({ user }) {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.get(`${API_BASE_URL}/api/dashboard`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDashboardData(response.data);
    } catch (err) {
      setError('Failed to load dashboard data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="dashboard-loading">Loading dashboard...</div>;
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <p className="welcome-text">Welcome back, {user?.name || 'User'}</p>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="dashboard-grid">
        <QuickStats data={dashboardData?.stats} />
        <StockCard data={dashboardData?.lowStockItems} />
        <RecentActivity data={dashboardData?.recentActivities} />
      </div>
    </div>
  );
}

export default DashboardPage;