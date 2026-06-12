import React, { useState } from 'react';
import '../../styles/components/estimates/EstimateForm.css';

function EstimateForm({ onAdd, onClose }) {
  const [formData, setFormData] = useState({
    client_id: '',
    estimate_date: new Date().toISOString().split('T')[0],
    products: [{ product_id: '', quantity: 1, unit_price: 0 }],
    discount: 0,
    tax_rate: 18,
    notes: ''
  });

  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name.includes('rate') || name.includes('discount') 
        ? parseFloat(value) || 0 
        : value
    }));
  };

  const handleProductChange = (index, field, value) => {
    const updatedProducts = [...formData.products];
    updatedProducts[index] = {
      ...updatedProducts[index],
      [field]: field === 'quantity' || field === 'unit_price' ? parseFloat(value) || 0 : value
    };
    setFormData(prev => ({
      ...prev,
      products: updatedProducts
    }));
  };

  const addProduct = () => {
    setFormData(prev => ({
      ...prev,
      products: [...prev.products, { product_id: '', quantity: 1, unit_price: 0 }]
    }));
  };

  const removeProduct = (index) => {
    setFormData(prev => ({
      ...prev,
      products: prev.products.filter((_, i) => i !== index)
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    const newErrors = {};
    if (!formData.client_id) newErrors.client_id = 'Client is required';
    if (formData.products.length === 0) newErrors.products = 'At least one product is required';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onAdd(formData);
  };

  const subtotal = formData.products.reduce((sum, p) => sum + (p.quantity * p.unit_price), 0);
  const tax = (subtotal - formData.discount) * (formData.tax_rate / 100);
  const total = subtotal - formData.discount + tax;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Create New Estimate</h2>
          <button className="close-button" onClick={onClose}>X</button>
        </div>

        <form onSubmit={handleSubmit} className="estimate-form">
          <div className="form-row">
            <div className="form-group">
              <label>Client</label>
              <select 
                name="client_id"
                value={formData.client_id}
                onChange={handleChange}
              >
                <option value="">Select Client</option>
                <option value="1">Client 1</option>
                <option value="2">Client 2</option>
              </select>
              {errors.client_id && <span className="error">{errors.client_id}</span>}
            </div>

            <div className="form-group">
              <label>Estimate Date</label>
              <input
                type="date"
                name="estimate_date"
                value={formData.estimate_date}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="products-section">
            <h3>Products</h3>
            <div className="products-table">
              <div className="products-header">
                <div className="col-product">Product</div>
                <div className="col-quantity">Quantity</div>
                <div className="col-price">Unit Price</div>
                <div className="col-total">Total</div>
                <div className="col-action">Action</div>
              </div>

              {formData.products.map((product, index) => (
                <div key={index} className="product-row">
                  <div className="col-product">
                    <input 
                      type="text"
                      value={product.product_id}
                      onChange={(e) => handleProductChange(index, 'product_id', e.target.value)}
                      placeholder="Product name"
                    />
                  </div>
                  <div className="col-quantity">
                    <input 
                      type="number"
                      value={product.quantity}
                      onChange={(e) => handleProductChange(index, 'quantity', e.target.value)}
                      min="1"
                    />
                  </div>
                  <div className="col-price">
                    <input 
                      type="number"
                      value={product.unit_price}
                      onChange={(e) => handleProductChange(index, 'unit_price', e.target.value)}
                      placeholder="0"
                    />
                  </div>
                  <div className="col-total">
                    Rs {(product.quantity * product.unit_price).toFixed(2)}
                  </div>
                  <div className="col-action">
                    <button 
                      type="button"
                      className="btn-remove"
                      onClick={() => removeProduct(index)}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <button 
              type="button"
              className="btn-add-product"
              onClick={addProduct}
            >
              Add Product
            </button>
            {errors.products && <span className="error">{errors.products}</span>}
          </div>

          <div className="cost-summary">
            <div className="summary-row">
              <span>Subtotal:</span>
              <span>Rs {subtotal.toFixed(2)}</span>
            </div>
            <div className="summary-row">
              <span>Discount:</span>
              <input 
                type="number"
                name="discount"
                value={formData.discount}
                onChange={handleChange}
                className="discount-input"
              />
            </div>
            <div className="summary-row">
              <span>Tax ({formData.tax_rate}%):</span>
              <span>Rs {tax.toFixed(2)}</span>
            </div>
            <div className="summary-row total">
              <span>Total:</span>
              <span>Rs {total.toFixed(2)}</span>
            </div>
          </div>

          <div className="form-group">
            <label>Notes</label>
            <textarea
              name="notes"
              value={formData.notes}
              onChange={handleChange}
              placeholder="Add any notes or terms"
              rows="3"
            />
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-submit">Create Estimate</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default EstimateForm;