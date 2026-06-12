import React from 'react';
import '../../styles/components/dashboard/StockCard.css';

function StockCard({ data }) {
  const lowStockItems = data || [];

  return (
    <div className="stock-card">
      <h2>Low Stock Items</h2>
      {lowStockItems.length > 0 ? (
        <div className="stock-list">
          {lowStockItems.map((item, index) => (
            <div key={index} className="stock-item">
              <div className="item-name">{item.name}</div>
              <div className="item-info">
                <span className="item-quantity">Qty: {item.quantity}</span>
                <span className="item-min">Min: {item.min_stock}</span>
              </div>
              <div className="item-status">Stock below minimum</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="no-items">All items are well stocked</div>
      )}
    </div>
  );
}

export default StockCard;