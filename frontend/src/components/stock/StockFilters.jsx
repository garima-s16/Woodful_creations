import React from 'react';
import '../../styles/components/stock/StockFilters.css';

function StockFilters({ filters, setFilters }) {
  const categories = [
    'All Categories',
    'Wood',
    'Furniture',
    'Accessories',
    'Custom Items'
  ];

  return (
    <div className="stock-filters">
      <div className="filter-group">
        <input
          type="text"
          placeholder="Search products..."
          value={filters.searchTerm}
          onChange={(e) => setFilters({ ...filters, searchTerm: e.target.value })}
          className="filter-input"
        />
      </div>

      <div className="filter-group">
        <select
          value={filters.category}
          onChange={(e) => setFilters({ ...filters, category: e.target.value })}
          className="filter-select"
        >
          {categories.map(cat => (
            <option key={cat} value={cat === 'All Categories' ? '' : cat}>
              {cat}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export default StockFilters;