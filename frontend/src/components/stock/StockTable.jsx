import React from 'react';
import '../../styles/components/stock/StockTable.css';

function StockTable({ products, user, onEdit, onDelete }) {
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
            <th>Supplier</th>
            <th>Status</th>
            {user?.role === 'master' && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {products.length > 0 ? (
            products.map(product => (
              <tr key={product.id} className={product.quantity <= product.min_stock ? 'low-stock' : ''}>
                <td>{product.name}</td>
                <td>{product.sku}</td>
                <td>{product.category}</td>
                <td className={product.quantity <= product.min_stock ? 'warning' : ''}>
                  {product.quantity}
                </td>
                <td>{product.min_stock}</td>
                <td>Rs {product.unit_cost}</td>
                <td>Rs {product.selling_price}</td>
                <td>{product.supplier}</td>
                <td>
                  <span className={`status-badge ${product.quantity > product.min_stock ? 'in-stock' : 'low-stock'}`}>
                    {product.quantity > product.min_stock ? 'In Stock' : 'Low Stock'}
                  </span>
                </td>
                {user?.role === 'master' && (
                  <td className="actions">
                    <button className="btn-edit" onClick={() => onEdit(product)}>Edit</button>
                    <button className="btn-delete" onClick={() => onDelete(product.id)}>Delete</button>
                  </td>
                )}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={user?.role === 'master' ? 10 : 9} className="no-data">
                No products found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default StockTable;