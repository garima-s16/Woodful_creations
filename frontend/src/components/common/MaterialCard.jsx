import React, { useState } from 'react';
import { statusClass } from '../../utils/statusColors';
import { formatCurrency } from '../../utils/currency';
import { CartIcon, PlusIcon } from '../icons';
import './MaterialCard.css';

/**
 * Amazon-style product card for the Material Catalog grid.
 * `view` is 'grid' (default) or 'list' - list renders a slimmer,
 * single-row layout for scanning many materials at once.
 */
function MaterialCard({ material, onOpen, onAddToCart, view = 'grid' }) {
  const [qty, setQty] = useState(1);

  const specLine = [material.thickness_size, material.brand_grade].filter(Boolean).join(' \u2022 ');
  const inStock = material.stock_status !== 'OUT OF STOCK';

  const handleAdd = (e) => {
    e.stopPropagation();
    onAddToCart(material, qty);
    setQty(1);
  };

  const stepQty = (e, delta) => {
    e.stopPropagation();
    setQty((q) => Math.max(1, q + delta));
  };

  if (view === 'list') {
    return (
      <div className="material-row-card" onClick={() => onOpen(material)}>
        <div className="material-row-swatch" aria-hidden="true">{(material.category || material.name || '?')[0]}</div>
        <div className="material-row-main">
          <div className="material-row-name">{material.name}</div>
          <div className="material-row-spec">{material.category || 'Uncategorized'}{specLine ? ` \u2022 ${specLine}` : ''}</div>
        </div>
        <div className="material-row-price">{formatCurrency(material.average_rate)}<span>/ {material.unit}</span></div>
        <div className="material-row-stock">
          <span className={`status-badge ${statusClass(material.stock_status)}`}>{material.stock_status}</span>
          <span className="material-row-stock-count">{material.current_stock} {material.unit}</span>
        </div>
        <div className="material-row-location">{material.location || '\u2014'}</div>
        <button className="btn-secondary material-row-cart-btn" disabled={!inStock} onClick={handleAdd}>
          <CartIcon width={14} height={14} /> Add
        </button>
      </div>
    );
  }

  return (
    <div className="material-card" onClick={() => onOpen(material)}>
      <div className="material-card-media" aria-hidden="true">
        <span className="material-card-initial">{(material.category || material.name || '?')[0]}</span>
        <span className={`status-badge material-card-status ${statusClass(material.stock_status)}`}>{material.stock_status}</span>
      </div>
      <div className="material-card-body">
        <div className="material-card-category">{material.category || 'Uncategorized'}</div>
        <div className="material-card-name">{material.name}</div>
        {specLine && <div className="material-card-spec">{specLine}</div>}
        <div className="material-card-price-row">
          <span className="material-card-price">{formatCurrency(material.average_rate)}</span>
          <span className="material-card-unit">/ {material.unit}</span>
        </div>
        <div className="material-card-meta">
          <span>Stock: <strong>{material.current_stock} {material.unit}</strong></span>
          {material.location && <span className="material-card-location">{material.location}</span>}
        </div>
      </div>
      <div className="material-card-footer">
        <div className="material-card-qty" onClick={(e) => e.stopPropagation()}>
          <button type="button" onClick={(e) => stepQty(e, -1)} aria-label="Decrease quantity">{'\u2212'}</button>
          <span>{qty}</span>
          <button type="button" onClick={(e) => stepQty(e, 1)} aria-label="Increase quantity">
            <PlusIcon width={12} height={12} />
          </button>
        </div>
        <button className="btn-primary material-card-add-btn" disabled={!inStock} onClick={handleAdd}>
          <CartIcon width={14} height={14} /> {inStock ? 'Add to Cart' : 'Out of Stock'}
        </button>
      </div>
    </div>
  );
}

export default MaterialCard;
