import React from 'react';
import './StockFilters.css';

function StockFilters({ searchTerm, setSearchTerm, categoryFilter, setCategoryFilter }) {
  const categories = [
    'all',
    'Furniture',
    'Decorative Items',
    'Custom Orders',
    'Materials',
    'Hardware',
    'Finishes',
  ];

  return (
    <div className="stock-filters">
      <div className="search-box">
        <input
          type="text"
          placeholder="Search by product name or SKU..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </div>

      <div className="category-filter">
        <label>Category:</label>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="category-select"
        >
          {categories.map(cat => (
            <option key={cat} value={cat}>
              {cat === 'all' ? 'All Categories' : cat}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export default StockFilters;