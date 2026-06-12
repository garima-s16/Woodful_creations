import React from 'react';
import '../../styles/components/analytics/ClientAnalytics.css';

function ClientAnalytics({ data }) {
  const clientData = data?.client || {};

  return (
    <div className="client-analytics">
      <div className="analytics-section">
        <h3>Revenue by Client</h3>
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Client Name</th>
              <th>Total Orders</th>
              <th>Total Revenue</th>
              <th>Average Order Value</th>
              <th>Classification</th>
            </tr>
          </thead>
          <tbody>
            {clientData.by_revenue && clientData.by_revenue.length > 0 ? (
              clientData.by_revenue.map((client, idx) => (
                <tr key={idx}>
                  <td>{client.name}</td>
                  <td>{client.orders}</td>
                  <td>Rs {client.revenue}</td>
                  <td>Rs {client.avg_value}</td>
                  <td>
                    <span className={`badge ${client.classification}`}>
                      {client.classification}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5" className="no-data">No client data available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="analytics-section">
        <h3>Top Clients</h3>
        <div className="metrics-grid">
          {clientData.top_clients && clientData.top_clients.length > 0 ? (
            clientData.top_clients.map((client, idx) => (
              <div key={idx} className="client-card">
                <div className="client-rank">#{idx + 1}</div>
                <div className="client-name">{client.name}</div>
                <div className="client-revenue">Rs {client.revenue}</div>
              </div>
            ))
          ) : (
            <div className="no-data">No top clients data</div>
          )}
        </div>
      </div>

      <div className="analytics-section">
        <h3>Client Acquisition and Retention</h3>
        <div className="metrics-row">
          <div className="metric-card">
            <div className="metric-label">New Clients This Period</div>
            <div className="metric-value">{clientData.new_clients || 0}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Repeat Order Rate</div>
            <div className="metric-value">{clientData.repeat_rate || 0}%</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Client Retention Rate</div>
            <div className="metric-value">{clientData.retention_rate || 0}%</div>
          </div>
        </div>
      </div>

      <div className="analytics-section">
        <h3>Client Satisfaction Metrics</h3>
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Client Name</th>
              <th>Satisfaction Score</th>
              <th>Repeat Orders</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {clientData.satisfaction && clientData.satisfaction.length > 0 ? (
              clientData.satisfaction.map((client, idx) => (
                <tr key={idx}>
                  <td>{client.name}</td>
                  <td>
                    <div className="score-bar">
                      <div 
                        className="score-fill"
                        style={{width: `${client.score}%`}}
                      ></div>
                    </div>
                    {client.score}%
                  </td>
                  <td>{client.repeat_orders}</td>
                  <td>
                    <span className={`status-badge ${client.status}`}>
                      {client.status}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4" className="no-data">No satisfaction data available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ClientAnalytics;