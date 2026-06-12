import React from 'react';
import '../../styles/components/estimates/EstimatePreview.css';

function EstimatePreview({ estimate, onSendEmail, onGeneratePDF }) {
  const [showEmailForm, setShowEmailForm] = React.useState(false);
  const [recipientEmail, setRecipientEmail] = React.useState('');

  const handleSendEmail = () => {
    if (recipientEmail.trim()) {
      onSendEmail(estimate.id, recipientEmail);
      setRecipientEmail('');
      setShowEmailForm(false);
    }
  };

  return (
    <div className="estimate-preview">
      <div className="preview-header">
        <h2>Estimate #{estimate.id}</h2>
        <span className={`status-badge ${estimate.status}`}>
          {estimate.status.toUpperCase()}
        </span>
      </div>

      <div className="preview-actions">
        <button 
          className="btn-action"
          onClick={() => onGeneratePDF(estimate.id)}
        >
          Download PDF
        </button>
        <button 
          className="btn-action"
          onClick={() => setShowEmailForm(!showEmailForm)}
        >
          Send Email
        </button>
      </div>

      {showEmailForm && (
        <div className="email-form">
          <input
            type="email"
            value={recipientEmail}
            onChange={(e) => setRecipientEmail(e.target.value)}
            placeholder="Recipient email"
          />
          <button onClick={handleSendEmail}>Send</button>
          <button onClick={() => setShowEmailForm(false)}>Cancel</button>
        </div>
      )}

      <div className="preview-content">
        <div className="preview-section">
          <h3>Client Information</h3>
          <p><strong>Name:</strong> {estimate.client_name}</p>
          <p><strong>Email:</strong> {estimate.client_email}</p>
          <p><strong>Phone:</strong> {estimate.client_phone}</p>
        </div>

        <div className="preview-section">
          <h3>Estimate Details</h3>
          <p><strong>Date:</strong> {estimate.created_date}</p>
          <p><strong>Valid Until:</strong> {estimate.valid_until}</p>
        </div>

        <div className="preview-section">
          <h3>Items</h3>
          <table className="items-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Quantity</th>
                <th>Unit Price</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {estimate.items && estimate.items.map((item, idx) => (
                <tr key={idx}>
                  <td>{item.product_name}</td>
                  <td>{item.quantity}</td>
                  <td>Rs {item.unit_price}</td>
                  <td>Rs {item.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="preview-section">
          <h3>Cost Summary</h3>
          <div className="summary-line">
            <span>Subtotal:</span>
            <span>Rs {estimate.subtotal}</span>
          </div>
          <div className="summary-line">
            <span>Discount:</span>
            <span>Rs {estimate.discount}</span>
          </div>
          <div className="summary-line">
            <span>Tax (18%):</span>
            <span>Rs {estimate.tax}</span>
          </div>
          <div className="summary-line total">
            <span>Total Amount:</span>
            <span>Rs {estimate.total_amount}</span>
          </div>
        </div>

        {estimate.notes && (
          <div className="preview-section">
            <h3>Notes</h3>
            <p>{estimate.notes}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default EstimatePreview;