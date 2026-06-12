import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/pages/StockInventoryPage.css';
import StockTable from '../components/stock/StockTable';
import AddProductModal from '../components/stock/AddProductModal';
import StockFilters from '../components/stock/StockFilters';

function StockInventoryPage({ user }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [filters, setFilters] = useState({ category: '', searchTerm: '' });
  const [selectedProduct, setSelectedProduct] = useState(null);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchProducts();
  }, [filters]);

  const fetchProducts = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const params = new URLSearchParams();
      
      if (filters.category) params.append('category', filters.category);
      if (filters.searchTerm) params.append('search', filters.searchTerm);

      const response = await axios.get(
        `${API_BASE_URL}/api/inventory/products?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setProducts(response.data.products);
    } catch (err) {
      setError('Failed to load products');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddProduct = async (productData) => {
    try {
      const token = localStorage.getItem('authToken');
      await axios.post(
        `${API_BASE_URL}/api/inventory/products`,
        productData,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setShowAddModal(false);
      fetchProducts();
    } catch (err) {
      setError('Failed to add product');
      console.error(err);
    }
  };

  const handleUpdateProduct = async (productId, updatedData) => {
    try {
      const token = localStorage.getItem('authToken');
      await axios.put(
        `${API_BASE_URL}/api/inventory/products/${productId}`,
        updatedData,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchProducts();
      setSelectedProduct(null);
    } catch (err) {
      setError('Failed to update product');
      console.error(err);
    }
  };

  const handleDeleteProduct = async (productId) => {
    if (!window.confirm('Are you sure you want to delete this product?')) return;
    
    try {
      const token = localStorage.getItem('authToken');
      await axios.delete(
        `${API_BASE_URL}/api/inventory/products/${productId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchProducts();
    } catch (err) {
      setError('Failed to delete product');
      console.error(err);
    }
  };

  return (
    <div className="stock-inventory-page">
      <div className="stock-header">
        <div>
          <h1>Stock Inventory</h1>
          <p>Manage your product inventory</p>
        </div>
        {user?.role === 'master' && (
          <button 
            className="btn-primary"
            onClick={() => setShowAddModal(true)}
          >
            Add New Product
          </button>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      <StockFilters filters={filters} setFilters={setFilters} />

      {loading ? (
        <div className="loading">Loading inventory...</div>
      ) : (
        <StockTable 
          products={products}
          user={user}
          onEdit={(product) => setSelectedProduct(product)}
          onDelete={handleDeleteProduct}
        />
      )}

      {showAddModal && (
        <AddProductModal
          onAdd={handleAddProduct}
          onClose={() => setShowAddModal(false)}
        />
      )}
    </div>
  );
}

export default StockInventoryPage;