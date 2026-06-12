import React, { useState } from 'react';
import './StockTable.css';

function StockTable({ products, isMasterUser, onUpdateStock, onDeleteProduct }) {
  const [editingId, setEditingId] = useState(null);
  const [editQuantity, setEditQuantity] = useState('');

  const handleEditClick = (product) => {
    setEditingId(product.id);
    setEditQuantity(product.quantity);
  };

  const handleSaveClick = async (productId) => {
    if (editQuantity !== '') {
      await onUpdateStock(productId, parseInt(editQuantity));
      setEditingId(null);
      setEditQuantity('');
    }
  };

  const getStockStatus = (quantity, minStock) => {
    if (quantity <= 0) return 'out-of-stock';
    if (quantity <= minStock) return 'low-stock';
    return 'in-stock';
  };

  const getStatusBadge = (status) => {
    const statusMap = {
      'in-stock': { label: 'In Stock', class: 'badge-success' },
      'low-stock': { label: 'Low Stock', class: 'badge-warning' },
      'out-of-stock': { label: 'Out of Stock', class: 'badge-error' },
    };
    const statusInfo = statusMap[status] || statusMap['in-stock'];
    return <span className={`badge ${statusInfo.class}`}>{statusInfo.label}</span>;
  };

  return (
    <div className="stock-table-container">
      <table className="stock-table">
        <thead>
          <tr>
            <th>Product Name</th>
            <th>SKU</th>
            <th>Category</th>
            <th>Quantity</th>
            <th>Min Stock</th>
            <th>Unit Cost</th>
            <th>Selling Price</th>
            <th>Status</th>
            {isMasterUser && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {products.length === 0 ? (
            <tr>
              <td colSpan={isMasterUser ? 9 : 8} className="text-center text-muted">
                No products found
              </td>
            </tr>
          ) : (
            products.map(product => {
              const status = getStockStatus(product.quantity, product.min_stock);
              return (
                <tr key={product.id} className={`status-${status}`}>
                  <td className="product-name">{product.name}</td>
                  <td className="sku">{product.sku}</td>
                  <td>{product.category}</td>
                  <td>
                    {editingId === product.id ? (
                      <input
                        type="number"
                        value={editQuantity}
                        onChange={(e) => setEditQuantity(e.target.value)}
                        className="quantity-input"
                        min="0"
                      />
                    ) : (
                      <span className="quantity-value">{product.quantity}</span>
                    )}
                  </td>
                  <td>{product.min_stock}</td>
                  <td>₹{product.unit_cost.toFixed(2)}</td>
                  <td>₹{product.selling_price.toFixed(2)}</td>
                  <td>{getStatusBadge(status)}</td>
                  {isMasterUser && (
                    <td className="actions">
                      {editingId === product.id ? (
                        <>
                          <button
                            className="btn-save"
                            onClick={() => handleSaveClick(product.id)}
                          >
                            Save
                          </button>
                          <button
                            className="btn-cancel"
                            onClick={() => setEditingId(null)}
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            className="btn-edit"
                            onClick={() => handleEditClick(product)}
                          >
                            Edit
                          </button>
                          <button
                            className="btn-delete"
                            onClick={() => onDeleteProduct(product.id)}
                          >
                            Delete
                          </button>
                        </>
                      )}
                    </td>
                  )}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

export default StockTable;