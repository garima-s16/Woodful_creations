import React, { useEffect, useState } from 'react';
import '../styles/Dashboard.css';

function DashboardPage({ user }) {
  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <h1>Welcome, {user?.full_name}</h1>
        <p>Woodful Creations Business Management System</p>
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-card">
          <div className="card-header">
            <h3>Quick Stats</h3>
          </div>
          <div className="card-body">
            <div className="stat-item">
              <span className="stat-label">Total Products</span>
              <span className="stat-value">-</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Low Stock Items</span>
              <span className="stat-value">-</span>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <div className="card-header">
            <h3>System Status</h3>
          </div>
          <div className="card-body">
            <p className="status-message">All systems operational</p>
            <p className="status-time">Last updated: {new Date().toLocaleString()}</p>
          </div>
        </div>

        {user?.is_master && (
          <div className="dashboard-card">
            <div className="card-header">
              <h3>Master Access</h3>
            </div>
            <div className="card-body">
              <p>Full system access enabled</p>
              <p>View all data and manage settings</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default DashboardPage;