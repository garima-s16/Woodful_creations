import React from 'react';
import '../styles/pages/PaymentsPage.css';

function PaymentsPage() {
  return (
    <div className="page-container">
      <h1>Payment Management</h1>
      <div className="coming-soon-section">
        <p>Master view of all payments to be made</p>
        <p>Access restricted to Master Administrators</p>
      </div>
    </div>
  );
}

export default PaymentsPage;