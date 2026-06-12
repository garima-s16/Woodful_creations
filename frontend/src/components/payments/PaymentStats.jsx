import React from 'react';
import '../../styles/components/payments/PaymentStats.css';

function PaymentStats({ stats }) {
  return (
    <div className="payment-stats">
      <div className="stat-card total">
        <div className="stat-label">Total Payments</div>
        <div className="stat-value">Rs {stats.total_amount || 0}</div>
      </div>

      <div className="stat-card pending">
        <div className="stat-label">Pending</div>
        <div className="stat-value">Rs {stats.pending_amount || 0}</div>
      </div>

      <div className="stat-card completed">
        <div className="stat-label">Completed</div>
        <div className="stat-value">Rs {stats.completed_amount || 0}</div>
      </div>

      <div className="stat-card overdue">
        <div className="stat-label">Overdue</div>
        <div className="stat-value">Rs {stats.overdue_amount || 0}</div>
      </div>
    </div>
  );
}

export default PaymentStats;