import React from 'react';
import './LowStockAlert.css';

function LowStockAlert({ items }) {
  return (
    <div className="low-stock-alert">
      <div className="alert-header">
        <span className="alert-icon">ALERT</span>
        <span className="alert-title">Low Stock Alert</span>
      </div>
      <div className="alert-items">
        {items.map(item => (
          <div key={item.id} className="alert-item">
            <span className="item-name">{item.name}</span>
            <span className="item-sku">SKU: {item.sku}</span>
            <span className="item-quantity">Stock: {item.quantity} (Min: {item.min_stock})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default LowStockAlert;