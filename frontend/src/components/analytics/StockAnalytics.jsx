import React from 'react';
import '../../styles/components/analytics/StockAnalytics.css';

function StockAnalytics({ data }) {
  const stockData = data?.stock || {};

  return (
    <div className="stock-analytics">
      <div className="analytics-section">
        <h3>Stock Turnover Rates</h3>
        <div className="chart-container">
          <div className="chart-placeholder">
            Stock turnover visualization chart
          </div>
        </div>
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-label">Average Turnover Rate</div>
            <div className="metric-value">{stockData.avg_turnover || 0}x</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Total Inventory Value</div>
            <div className="metric-value">Rs {stockData.total_value || 0}</div>
          </div>
        </div>
      </div>

      <div className="analytics-section">
        <h3>Fast Moving Items</h3>
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Quantity Sold</th>
              <th>Revenue</th>
              <th>Turnover Rate</th>
            </tr>
          </thead>
          <tbody>
            {stockData.fast_moving && stockData.fast_moving.length > 0 ? (
              stockData.fast_moving.map((item, idx) => (
                <tr key={idx}>
                  <td>{item.name}</td>
                  <td>{item.quantity}</td>
                  <td>Rs {item.revenue}</td>
                  <td>{item.turnover}x</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4" className="no-data">No data available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="analytics-section">
        <h3>Slow Moving Items</h3>
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Stock Quantity</th>
              <th>Days in Stock</th>
              <th>Recommendation</th>
            </tr>
          </thead>
          <tbody>
            {stockData.slow_moving && stockData.slow_moving.length > 0 ? (
              stockData.slow_moving.map((item, idx) => (
                <tr key={idx}>
                  <td>{item.name}</td>
                  <td>{item.quantity}</td>
                  <td>{item.days}</td>
                  <td>{item.recommendation}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4" className="no-data">No slow moving items</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="analytics-section">
        <h3>Revenue by Category</h3>
        <div className="chart-container">
          <div className="chart-placeholder">
            Category revenue distribution chart
          </div>
        </div>
      </div>
    </div>
  );
}

export default StockAnalytics;