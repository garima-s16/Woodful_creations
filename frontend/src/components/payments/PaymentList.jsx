import React from 'react';
import '../../styles/components/payments/PaymentList.css';

function PaymentList({ payments, onDelete }) {
  return (
    <div className="payment-list">
      {payments.length > 0 ? (
        <div className="payments-table-container">
          <table className="payments-table">
            <thead>
              <tr>
                <th>Payment ID</th>
                <th>Vendor/Supplier</th>
                <th>Amount</th>
                <th>Payment Date</th>
                <th>Maturity Date</th>
                <th>Status</th>
                <th>Mode</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {payments.map(payment => (
                <tr key={payment.id}>
                  <td>{payment.id}</td>
                  <td>{payment.vendor_name}</td>
                  <td>Rs {payment.amount}</td>
                  <td>{payment.payment_date}</td>
                  <td>{payment.maturity_date}</td>
                  <td>
                    <span className={`status-badge ${payment.status}`}>
                      {payment.status.toUpperCase()}
                    </span>
                  </td>
                  <td>{payment.mode}</td>
                  <td>
                    <button 
                      className="btn-delete"
                      onClick={() => onDelete(payment.id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="no-payments">No payments found</div>
      )}
    </div>
  );
}

export default PaymentList;