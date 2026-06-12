import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/pages/AnalyticsPage.css';
import StockAnalytics from '../components/analytics/StockAnalytics';
import ClientAnalytics from '../components/analytics/ClientAnalytics';
import PaymentAnalytics from '../components/analytics/PaymentAnalytics';
import EmployeeAnalytics from '../components/analytics/EmployeeAnalytics';

function AnalyticsPage({ user }) {
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedTab, setSelectedTab] = useState('stock');
  const [dateRange, setDateRange] = useState('month');

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchAnalytics();
  }, [dateRange, selectedTab]);

  const fetchAnalytics = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.get(
        `${API_BASE_URL}/api/analytics?tab=${selectedTab}&range=${dateRange}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setAnalyticsData(response.data);
    } catch (err) {
      setError('Failed to load analytics data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleExportReport = async (format) => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.get(
        `${API_BASE_URL}/api/analytics/export?tab=${selectedTab}&format=${format}&range=${dateRange}`,
        { 
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob'
        }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      const extension = format === 'pdf' ? 'pdf' : format === 'excel' ? 'xlsx' : 'docx';
      link.setAttribute('download', `analytics-${selectedTab}-${dateRange}.${extension}`);
      document.body.appendChild(link);
      link.click();
      link.parentChild.removeChild(link);
    } catch (err) {
      setError('Failed to export report');
      console.error(err);
    }
  };

  return (
    <div className="analytics-page">
      <div className="analytics-header">
        <div>
          <h1>Advanced Analytics</h1>
          <p>Business insights and data-driven reports</p>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="analytics-controls">
        <div className="date-range-selector">
          <label>Date Range:</label>
          <select 
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="date-select"
          >
            <option value="week">This Week</option>
            <option value="month">This Month</option>
            <option value="quarter">This Quarter</option>
            <option value="year">This Year</option>
          </select>
        </div>

        <div className="export-buttons">
          <button 
            className="btn-export"
            onClick={() => handleExportReport('excel')}
          >
            Export to Excel
          </button>
          <button 
            className="btn-export"
            onClick={() => handleExportReport('pdf')}
          >
            Export to PDF
          </button>
          <button 
            className="btn-export"
            onClick={() => handleExportReport('word')}
          >
            Export to Word
          </button>
        </div>
      </div>

      <div className="analytics-tabs">
        <button 
          className={`tab-button ${selectedTab === 'stock' ? 'active' : ''}`}
          onClick={() => setSelectedTab('stock')}
        >
          Stock Analytics
        </button>
        <button 
          className={`tab-button ${selectedTab === 'client' ? 'active' : ''}`}
          onClick={() => setSelectedTab('client')}
        >
          Client Analytics
        </button>
        <button 
          className={`tab-button ${selectedTab === 'payment' ? 'active' : ''}`}
          onClick={() => setSelectedTab('payment')}
        >
          Payment Analytics
        </button>
        {user?.role === 'master' && (
          <button 
            className={`tab-button ${selectedTab === 'employee' ? 'active' : ''}`}
            onClick={() => setSelectedTab('employee')}
          >
            Employee Analytics
          </button>
        )}
      </div>

      {loading ? (
        <div className="loading">Loading analytics...</div>
      ) : analyticsData ? (
        <div className="analytics-content">
          {selectedTab === 'stock' && <StockAnalytics data={analyticsData} />}
          {selectedTab === 'client' && <ClientAnalytics data={analyticsData} />}
          {selectedTab === 'payment' && <PaymentAnalytics data={analyticsData} />}
          {selectedTab === 'employee' && <EmployeeAnalytics data={analyticsData} />}
        </div>
      ) : null}
    </div>
  );
}

export default AnalyticsPage;