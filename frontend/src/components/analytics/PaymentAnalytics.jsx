import React from 'react';
import '../../styles/components/analytics/PaymentAnalytics.css';

function PaymentAnalytics({ data }) {
  const paymentData = data?.payment || {};

  return (
    <div className="payment-analytics">
      <div className="analytics-section">
        <h3>Revenue Trends</h3>
        <div className="chart-container">
          <div className="chart-placeholder">
            Revenue trends visualization
          </div>
        </div>
      </div>

      <div className="analytics-section">
        <h3>Payment Summary</h3>
        <div className="summary-grid">
          <div className="summary-card total">
            <div className="summary-label">Total Revenue</div>
            <div className="summary-value">Rs {paymentData.total_revenue || 0}</div>
          </div>
          <div className="summary-card received">
            <div className="summary-label">Payments Received</div>
            <div className="summary-value">Rs {paymentData.received || 0}</div>
          </div>
          <div className="summary-card pending">
            <div className="summary-label">Outstanding Receivables</div>
            <div className="summary-value">Rs {paymentData.outstanding || 0}</div>
          </div>
          <div className="summary-card delayed">
            <div className="summary-label">Delayed Payments</div>
            <div className="summary-value">Rs {paymentData.delayed || 0}</div>
          </div>
        </div>
      </div>

      <div className="analytics-section">
        <h3>Payment Delays and Client Reliability</h3>
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Client Name</th>
              <th>Total Due</th>
              <th>Overdue Amount</th>
              <th>Days Overdue</th>
              <th>Reliability Score</th>
            </tr>
          </thead>
          <tbody>
            {paymentData.client_payment_status && paymentData.client_payment_status.length > 0 ? (
              paymentData.client_payment_status.map((client, idx) => (
                <tr key={idx}>
                  <td>{client.name}</td>
                  <td>Rs {client.total_due}</td>
                  <td>Rs {client.overdue}</td>
                  <td>{client.days_overdue}</td>
                  <td>
                    <span className={`reliability-badge ${client.score >= 80 ? 'high' : client.score >= 50 ? 'medium' : 'low'}`}>
                      {client.score}%
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5" className="no-data">No payment data available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="analytics-section">
        <h3>Cash Flow Projections</h3>
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Period</th>
              <th>Projected Inflow</th>
              <th>Projected Outflow</th>
              <th>Net Cash Flow</th>
            </tr>
          </thead>
          <tbody>
            {paymentData.cash_flow && paymentData.cash_flow.length > 0 ? (
              paymentData.cash_flow.map((period, idx) => (
                <tr key={idx}>
                  <td>{period.month}</td>
                  <td>Rs {period.inflow}</td>
                  <td>Rs {period.outflow}</td>
                  <td className={period.net >= 0 ? 'positive' : 'negative'}>
                    Rs {period.net}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4" className="no-data">No cash flow data available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default PaymentAnalytics;