import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './StockInventory.css';

function StockInventory({ userRole }) {
  const [products, setProducts] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [formData, setFormData] = useState({
    name: '',
    category: '',
    quantity: '',
    minQuantity: '',
    price: '',
    unit: 'pieces'
  });

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/inventory', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      setProducts(response.data);
    } catch (error) {
      console.error('Error fetching products:', error);
      // Mock data for demo
      setProducts([
        { id: 1, name: 'Walnut Wood', category: 'Wood', quantity: 150, minQuantity: 50, price: 500, unit: 'pieces', lastUpdated: new Date() },
        { id: 2, name: 'Oak Wood', category: 'Wood', quantity: 20, minQuantity: 50, price: 450, unit: 'pieces', lastUpdated: new Date() },
        { id: 3, name: 'Hardware Set', category: 'Hardware', quantity: 200, minQuantity: 100, price: 150, unit: 'sets', lastUpdated: new Date() },
        { id: 4, name: 'Wood Stain', category: 'Finishing', quantity: 80, minQuantity: 30, price: 250, unit: 'liters', lastUpdated: new Date() },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddProduct = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post('http://localhost:8000/api/inventory', formData, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      setProducts([...products, response.data]);
      setFormData({ name: '', category: '', quantity: '', minQuantity: '', price: '', unit: 'pieces' });
      setShowForm(false);
    } catch (error) {
      console.error('Error adding product:', error);
      alert('Error adding product. Please try again.');
    }
  };

  const handleUpdateQuantity = async (productId, newQuantity) => {
    try {
      await axios.patch(`http://localhost:8000/api/inventory/${productId}`, 
        { quantity: newQuantity },
        { headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` } }
      );
      fetchProducts();
    } catch (error) {
      console.error('Error updating product:', error);
    }
  };

  const filteredProducts = products.filter(product => {
    const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = filterCategory === 'all' || product.category === filterCategory;
    return matchesSearch && matchesCategory;
  });

  const categories = ['all', ...new Set(products.map(p => p.category))];

  const isLowStock = (quantity, minQuantity) => quantity <= minQuantity;

  if (isLoading) {
    return <div className="stock-inventory"><div className="loading">Loading inventory...</div></div>;
  }

  return (
    <div className="stock-inventory">
      <div className="inventory-header">
        <h1>Stock Inventory</h1>
        {(userRole === 'master' || userRole === 'user') && (
          <button className="add-product-btn" onClick={() => setShowForm(!showForm)}>
            {showForm ? 'Cancel' : 'Add Product'}
          </button>
        )}
      </div>

      {showForm && (
        <div className="add-product-form">
          <h2>Add New Product</h2>
          <form onSubmit={handleAddProduct}>
            <div className="form-row">
              <div className="form-group">
                <label>Product Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  required
                />
              </div>
              <div className="form-group">
                <label>Category</label>
                <input
                  type="text"
                  value={formData.category}
                  onChange={(e) => setFormData({...formData, category: e.target.value})}
                  required
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Quantity</label>
                <input
                  type="number"
                  value={formData.quantity}
                  onChange={(e) => setFormData({...formData, quantity: e.target.value})}
                  required
                />
              </div>
              <div className="form-group">
                <label>Minimum Quantity</label>
                <input
                  type="number"
                  value={formData.minQuantity}
                  onChange={(e) => setFormData({...formData, minQuantity: e.target.value})}
                  required
                />
              </div>
              <div className="form-group">
                <label>Price</label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.price}
                  onChange={(e) => setFormData({...formData, price: e.target.value})}
                  required
                />
              </div>
              <div className="form-group">
                <label>Unit</label>
                <select
                  value={formData.unit}
                  onChange={(e) => setFormData({...formData, unit: e.target.value})}
                >
                  <option value="pieces">Pieces</option>
                  <option value="kg">Kg</option>
                  <option value="liters">Liters</option>
                  <option value="meters">Meters</option>
                </select>
              </div>
            </div>

            <button type="submit" className="submit-btn">Add Product</button>
          </form>
        </div>
      )}

      <div className="inventory-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search products..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="filter-box">
          <label>Category:</label>
          <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
            {categories.map(cat => (
              <option key={cat} value={cat}>
                {cat.charAt(0).toUpperCase() + cat.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="products-container">
        {filteredProducts.length === 0 ? (
          <div className="no-products">No products found</div>
        ) : (
          <table className="products-table">
            <thead>
              <tr>
                <th>Product Name</th>
                <th>Category</th>
                <th>Quantity</th>
                <th>Min Qty</th>
                <th>Price</th>
                <th>Unit</th>
                <th>Status</th>
                {(userRole === 'master' || userRole === 'user') && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {filteredProducts.map(product => (
                <tr key={product.id} className={isLowStock(product.quantity, product.minQuantity) ? 'low-stock' : ''}>
                  <td className="product-name">{product.name}</td>
                  <td>{product.category}</td>
                  <td className="quantity">{product.quantity}</td>
                  <td>{product.minQuantity}</td>
                  <td>Rs {product.price}</td>
                  <td>{product.unit}</td>
                  <td>
                    <span className={`status-badge ${isLowStock(product.quantity, product.minQuantity) ? 'low' : 'ok'}`}>
                      {isLowStock(product.quantity, product.minQuantity) ? 'Low Stock' : 'In Stock'}
                    </span>
                  </td>
                  {(userRole === 'master' || userRole === 'user') && (
                    <td className="actions">
                      <button 
                        className="edit-btn"
                        onClick={() => handleUpdateQuantity(product.id, product.quantity + 1)}
                        title="Increase quantity"
                      >
                        +
                      </button>
                      <button 
                        className="delete-btn"
                        onClick={() => handleUpdateQuantity(product.id, Math.max(0, product.quantity - 1))}
                        title="Decrease quantity"
                      >
                        -
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="inventory-stats">
        <div className="stat">
          <span>Total Products:</span>
          <strong>{products.length}</strong>
        </div>
        <div className="stat">
          <span>Low Stock Items:</span>
          <strong className="warning">{products.filter(p => isLowStock(p.quantity, p.minQuantity)).length}</strong>
        </div>
        <div className="stat">
          <span>Total Value:</span>
          <strong>Rs {products.reduce((sum, p) => sum + (p.price * p.quantity), 0).toLocaleString()}</strong>
        </div>
      </div>
    </div>
  );
}

export default StockInventory;