import React, { useState } from 'react';
import '../../styles/components/payments/PaymentForm.css';

function PaymentForm({ onAdd, onClose }) {
  const [formData, setFormData] = useState({
    vendor_name: '',
    invoice_number: '',
    amount: 0,
    payment_date: new Date().toISOString().split('T')[0],
    maturity_date: '',
    payment_mode: 'bank_transfer',
    status: 'pending',
    reference_number: '',
    notes: ''
  });

  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'amount' ? parseFloat(value) || 0 : value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    const newErrors = {};
    if (!formData.vendor_name.trim()) newErrors.vendor_name = 'Vendor name is required';
    if (!formData.invoice_number.trim()) newErrors.invoice_number = 'Invoice number is required';
    if (formData.amount <= 0) newErrors.amount = 'Amount must be greater than 0';
    if (!formData.maturity_date) newErrors.maturity_date = 'Maturity date is required';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onAdd(formData);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add New Payment</h2>
          <button className="close-button" onClick={onClose}>X</button>
        </div>

        <form onSubmit={handleSubmit} className="payment-form">
          <div className="form-row">
            <div className="form-group">
              <label>Vendor/Supplier Name</label>
              <input
                type="text"
                name="vendor_name"
                value={formData.vendor_name}
                onChange={handleChange}
                placeholder="Enter vendor name"
              />
              {errors.vendor_name && <span className="error">{errors.vendor_name}</span>}
            </div>

            <div className="form-group">
              <label>Invoice Number</label>
              <input
                type="text"
                name="invoice_number"
                value={formData.invoice_number}
                onChange={handleChange}
                placeholder="Enter invoice number"
              />
              {errors.invoice_number && <span className="error">{errors.invoice_number}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Amount (Rs)</label>
              <input
                type="number"
                name="amount"
                value={formData.amount}
                onChange={handleChange}
                placeholder="0"
              />
              {errors.amount && <span className="error">{errors.amount}</span>}
            </div>

            <div className="form-group">
              <label>Payment Mode</label>
              <select 
                name="payment_mode"
                value={formData.payment_mode}
                onChange={handleChange}
              >
                <option value="bank_transfer">Bank Transfer</option>
                <option value="cheque">Cheque</option>
                <option value="cash">Cash</option>
                <option value="upi">UPI</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Payment Date</label>
              <input
                type="date"
                name="payment_date"
                value={formData.payment_date}
                onChange={handleChange}
              />
            </div>

            <div className="form-group">
              <label>Maturity Date</label>
              <input
                type="date"
                name="maturity_date"
                value={formData.maturity_date}
                onChange={handleChange}
              />
              {errors.maturity_date && <span className="error">{errors.maturity_date}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Status</label>
              <select 
                name="status"
                value={formData.status}
                onChange={handleChange}
              >
                <option value="pending">Pending</option>
                <option value="completed">Completed</option>
                <option value="overdue">Overdue</option>
              </select>
            </div>

            <div className="form-group">
              <label>Reference Number</label>
              <input
                type="text"
                name="reference_number"
                value={formData.reference_number}
                onChange={handleChange}
                placeholder="Cheque/Transaction number"
              />
            </div>
          </div>

          <div className="form-group">
            <label>Notes</label>
            <textarea
              name="notes"
              value={formData.notes}
              onChange={handleChange}
              placeholder="Add any notes"
              rows="3"
            />
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-submit">Add Payment</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default PaymentForm;