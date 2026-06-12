import React, { useState } from 'react';
import './Pages.css';

function Estimates() {
  const [estimates, setEstimates] = useState([
    { id: 1, clientName: 'Client A', amount: 50000, status: 'pending', createdDate: new Date() },
    { id: 2, clientName: 'Client B', amount: 75000, status: 'approved', createdDate: new Date() },
  ]);

  return (
    <div className="page-container">
      <h1>Cost Estimates</h1>
      <div className="coming-soon">
        <p>Create and manage cost estimates for clients</p>
        <p>Features: PDF generation, product images, cost breakdown, client details</p>
      </div>
    </div>
  );
}

export default Estimates;