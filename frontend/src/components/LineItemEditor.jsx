import React, { useState, useRef, useEffect } from 'react';
import { formatCurrency } from '../utils/currency';
import { productsAPI, clientProductRateAPI } from '../utils/api';
import '../styles/components/LineItemEditor.css';

const CATEGORIES = ['Material', 'Labor', 'Furniture', 'Hardware', 'Installation', 'Transportation', 'Design', 'Service', 'Other'];

const emptyRow = () => ({ description: '', category: '', quantity: '1', unit: '', rate: '0', product_id: '', product_label: '' });

// Product ID + search, shared by every row - Family 102 Product ID
// requirement: the user should never need to remember Product IDs.
function ProductPicker({ row, onPick }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef(null);
  const boxRef = useRef(null);

  useEffect(() => {
    const onClickOutside = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const runSearch = (text) => {
    setQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (text.trim().length < 3) {
      setResults([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await productsAPI.list({ search: text.trim(), is_active: true, limit: 8 });
        setResults(res.data);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
  };

  const pick = (product) => {
    onPick(product);
    setQuery('');
    setResults([]);
    setOpen(false);
  };

  return (
    <div className="product-picker" ref={boxRef}>
      <input
        type="text" placeholder="Product ID" value={row.product_id}
        onChange={(e) => onPick({ id: e.target.value, name: '', __idOnly: true })}
        className={!row.product_id ? 'product-id-missing' : ''}
      />
      {row.product_label && <div className="product-picker-label">{row.product_label}</div>}
      <button type="button" className="btn-link product-picker-toggle" onClick={() => setOpen((v) => !v)}>
        Don&apos;t know Product ID? Search Product
      </button>
      {open && (
        <div className="product-picker-dropdown">
          <input
            type="text" autoFocus placeholder="Search product name or code..."
            value={query} onChange={(e) => runSearch(e.target.value)}
          />
          {loading && <div className="product-picker-hint">Searching...</div>}
          {!loading && query.trim().length >= 3 && results.length === 0 && (
            <div className="product-picker-hint">No matching products.</div>
          )}
          {!loading && query.trim().length > 0 && query.trim().length < 3 && (
            <div className="product-picker-hint">Type at least 3 characters.</div>
          )}
          {results.map((p) => (
            <button type="button" key={p.id} className="product-picker-result" onClick={() => pick(p)}>
              <span className="product-picker-result-id">{p.product_code}</span>
              <span className="product-picker-result-name">{p.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function LineItemEditor({ items, onChange, clientId }) {
  const updateRow = (idx, field, value) => {
    const next = items.map((row, i) => (i === idx ? {
      ...row, [field]: value,
      ...(field === 'rate' ? { pricing_rule: '' } : {}),
    } : row));
    onChange(next);
  };

  const pickProduct = async (idx, product) => {
    if (product.__idOnly) {
      // Manual Product ID entry - Product ID is authoritative, so the
      // label is cleared until it's actually resolved server-side on
      // save; typing an ID here never lets the user also type a
      // conflicting name (Family 102 Product ID consistency rule).
      const next = items.map((row, i) => (i === idx ? { ...row, product_id: product.id, product_label: '', pricing_rule: '' } : row));
      onChange(next);
      return;
    }
    const baseNext = items.map((row, i) => (i === idx ? {
      ...row,
      product_id: product.id,
      product_label: `${product.product_code} · ${product.name}`,
      description: row.description || product.name,
      unit: row.unit || product.unit || '',
      rate: (row.rate === '0' || !row.rate) && product.selling_price != null ? String(product.selling_price) : row.rate,
      pricing_rule: '',
    } : row));
    onChange(baseNext);

    // Live pricing resolution (customer-specific override -> estimate
    // margin -> product margin -> global default) - only meaningful
    // once a client is actually selected, and only ever SUGGESTS a
    // rate into an empty/zero field; it never overwrites a rate the
    // person already typed themselves (that's priority level 1,
    // "explicit line-item override", and it already won just by
    // existing - this call is only for rows that are still at their
    // default '0').
    if (clientId && (baseNext[idx].rate === '0' || !baseNext[idx].rate)) {
      try {
        const res = await clientProductRateAPI.resolve({ product_id: product.id, client_id: Number(clientId) });
        const resolved = items.map((row, i) => (i === idx ? {
          ...row, product_id: product.id, product_label: `${product.product_code} · ${product.name}`,
          description: row.description || product.name, unit: row.unit || product.unit || '',
          rate: String(res.data.selling_rate), pricing_rule: res.data.pricing_rule_applied,
        } : row));
        onChange(resolved);
      } catch {
        // Resolution is a convenience suggestion, not a required step -
        // if it fails (e.g. no cost data yet), the product's own flat
        // selling_price (already applied above) stands as the fallback.
      }
    }
  };

  const addRow = () => onChange([...items, emptyRow()]);
  const removeRow = (idx) => onChange(items.filter((_, i) => i !== idx));
  const moveRow = (idx, direction) => {
    const target = idx + direction;
    if (target < 0 || target >= items.length) return;
    const next = [...items];
    [next[idx], next[target]] = [next[target], next[idx]];
    onChange(next);
  };

  const subtotal = items.reduce((sum, row) => sum + (Number(row.quantity) || 0) * (Number(row.rate) || 0), 0);

  return (
    <div className="line-item-editor">
      <div className="line-item-header-row">
        <span>Product</span><span>Description</span><span>Category</span><span>Qty</span><span>Unit</span><span>Rate</span><span>Amount</span><span />
      </div>
      {items.map((row, idx) => (
        <div className="line-item-row" key={idx}>
          <ProductPicker row={row} onPick={(product) => pickProduct(idx, product)} />
          <input
            type="text" placeholder="e.g. Wardrobe" value={row.description}
            onChange={(e) => updateRow(idx, 'description', e.target.value)}
          />
          <select value={row.category} onChange={(e) => updateRow(idx, 'category', e.target.value)}>
            <option value="">-</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input type="number" min="0.01" step="0.01" value={row.quantity} onChange={(e) => updateRow(idx, 'quantity', e.target.value)} />
          <input type="text" placeholder="Nos/Lot" value={row.unit} onChange={(e) => updateRow(idx, 'unit', e.target.value)} />
          <div>
            <input type="number" min="0" step="0.01" value={row.rate} onChange={(e) => updateRow(idx, 'rate', e.target.value)} />
            {row.pricing_rule && (
              <div className="line-item-pricing-rule">
                {row.pricing_rule === 'CUSTOMER_MARGIN_OVERRIDE' && 'Customer margin'}
                {row.pricing_rule === 'CUSTOMER_PRODUCT_PRICE_OVERRIDE' && 'Customer negotiated price'}
                {row.pricing_rule === 'PRODUCT_MARGIN' && 'Product margin'}
                {row.pricing_rule === 'GLOBAL_DEFAULT_MARGIN' && 'Default margin'}
              </div>
            )}
          </div>
          <span className="line-item-amount">{formatCurrency((Number(row.quantity) || 0) * (Number(row.rate) || 0))}</span>
          <div className="line-item-row-actions">
            <button type="button" onClick={() => moveRow(idx, -1)} disabled={idx === 0} title="Move up">↑</button>
            <button type="button" onClick={() => moveRow(idx, 1)} disabled={idx === items.length - 1} title="Move down">↓</button>
            <button type="button" onClick={() => removeRow(idx)} title="Remove" className="line-item-remove">×</button>
          </div>
        </div>
      ))}
      <button type="button" className="btn-secondary line-item-add" onClick={addRow}>+ Add Item</button>
      {items.length > 0 && (
        <div className="line-item-subtotal">Subtotal: <strong>{formatCurrency(subtotal)}</strong></div>
      )}
    </div>
  );
}

export default LineItemEditor;
export { emptyRow };
