import React, { useEffect, useState } from 'react';
import './App.css';
import axios from 'axios';

function App() {
  const [apiStatus, setApiStatus] = useState('checking');
  const [appInfo, setAppInfo] = useState(null);

  useEffect(() => {
    checkBackendConnection();
  }, []);

  const checkBackendConnection = async () => {
    try {
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/health`, {
        timeout: 5000
      });
      setApiStatus('connected');
      setAppInfo(response.data);
    } catch (error) {
      console.error('Backend connection error:', error);
      setApiStatus('disconnected');
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Woodful Creations</h1>
        <p>AI-Powered Management System</p>
        <div className="status-container">
          <div className={`status-badge ${apiStatus}`}>
            API Status: {apiStatus.toUpperCase()}
          </div>
        </div>
        {appInfo && (
          <div className="app-info">
            <p>Service: {appInfo.service}</p>
          </div>
        )}
        {apiStatus === 'disconnected' && (
          <div className="error-message">
            Unable to connect to backend. Please ensure the backend server is running on {process.env.REACT_APP_API_URL}
          </div>
        )}
      </header>
      <main className="App-main">
        <section className="feature-section">
          <h2>Welcome to Woodful Creations</h2>
          <p>Your comprehensive AI-powered business management system</p>
          <div className="features-grid">
            <div className="feature-card">
              <h3>Stock Inventory</h3>
              <p>Manage inventory with AI-powered alerts</p>
            </div>
            <div className="feature-card">
              <h3>Cost Estimates</h3>
              <p>Generate beautiful PDF estimates</p>
            </div>
            <div className="feature-card">
              <h3>Client Management</h3>
              <p>Track clients and their projects</p>
            </div>
            <div className="feature-card">
              <h3>Employee Management</h3>
              <p>Attendance and salary management</p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;