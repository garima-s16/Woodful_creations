import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { materialsAPI, purchasesAPI, issuesAPI } from '../utils/api';
import { fetchStart, fetchSuccess, fetchFailure, addProduct } from '../redux/slices/inventorySlice';
import ChatWidget from '../components/ChatWidget';
import '../styles/StockInventoryPage.css';

function StockInventoryPage({ user }) {
  const dispatch = useDispatch();
  const { products, loading } = useSelector((state) => state.inventory);
  const [showForm, setShowForm] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [formData, setFormData] = useState({
    name: '',
    category: '',
    quantity: '',
    minQuantity: '',
    price: '',
    unit: 'pieces',
  });

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    dispatch(fetchStart());
    try {
      const response = await materialsAPI.getInventory();
      dispatch(fetchSuccess(response.data));
    } catch (error) {
      dispatch(fetchFailure(error.message));
    }
  };

  const handleAddProduct = async (e) => {
    e.preventDefault();
    try {
      const response = await materialsAPI.addProduct(formData);
      dispatch(addProduct(response.data));
      setFormData({
        name: '',
        category: '',
        quantity: '',
        minQuantity: '',
        price: '',
        unit: 'pieces',
      });
      setShowForm(false);
    } catch (error) {
      console.error('Error adding product:', error);
      alert('Error adding product');
    }
  };

  const isLowStock = (qty, min) => qty <= min;

  const filteredProducts = products.filter((p) => {
    const matchSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchCategory = filterCategory === 'all' || p.category === filterCategory;
    return matchSearch && matchCategory;
  });

  const categories = ['all', ...new Set(products.map((p) => p.category))];
  const canEdit = user?.role === 'master' || user?.role === 'user';

  return (
    <div className="stock-inventory-page">
      <div className="page-header">
        <h1>Stock Inventory</h1>
        {canEdit && (
          <button
            className="add-product-button"
            onClick={() => setShowForm(!showForm)}
          >
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
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label>Category</label>
                <input
                  type="text"
                  value={formData.category}
                  onChange={(e) =>
                    setFormData({ ...formData, category: e.target.value })
                  }
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
                  onChange={(e) =>
                    setFormData({ ...formData, quantity: e.target.value })
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label>Minimum Quantity</label>
                <input
                  type="number"
                  value={formData.minQuantity}
                  onChange={(e) =>
                    setFormData({ ...formData, minQuantity: e.target.value })
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label>Price</label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.price}
                  onChange={(e) =>
                    setFormData({ ...formData, price: e.target.value })
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label>Unit</label>
                <select
                  value={formData.unit}
                  onChange={(e) =>
                    setFormData({ ...formData, unit: e.target.value })
                  }
                >
                  <option>pieces</option>
                  <option>kg</option>
                  <option>liters</option>
                  <option>meters</option>
                </select>
              </div>
            </div>

            <button type="submit" className="submit-button">
              Add Product
            </button>
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
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
          >
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat.charAt(0).toUpperCase() + cat.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading inventory...</div>
      ) : (
        <div className="products-table-container">
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
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map((product) => (
                  <tr
                    key={product.id}
                    className={
                      isLowStock(product.quantity, product.minQuantity)
                        ? 'low-stock'
                        : ''
                    }
                  >
                    <td className="product-name">{product.name}</td>
                    <td>{product.category}</td>
                    <td className="quantity">{product.quantity}</td>
                    <td>{product.minQuantity}</td>
                    <td>Rs {product.price}</td>
                    <td>{product.unit}</td>
                    <td>
                      <span
                        className={`status-badge ${
                          isLowStock(product.quantity, product.minQuantity)
                            ? 'low'
                            : 'ok'
                        }`}
                      >
                        {isLowStock(product.quantity, product.minQuantity)
                          ? 'Low Stock'
                          : 'In Stock'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <ChatWidget />
    </div>
  );
}

export default StockInventoryPage;
