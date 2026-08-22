import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { formatCurrency } from '../utils/currency';
import { productsAPI, clientProductRateAPI } from '../utils/api';
import '../styles/components/LineItemEditor.css';

const CATEGORIES = ['Material', 'Labor', 'Furniture', 'Hardware', 'Installation', 'Transportation', 'Design', 'Service', 'Other'];

// Product Master's own category/subcategory vocabulary is more
// granular than this editor's flat cost-classification list (e.g. a
// product might be tagged category="Seating" or subcategory="Living
// Room" rather than the literal string "Furniture") - this maps a
// selected product's actual category/subcategory into the closest
// matching entry here, so picking "Custom Wardrobe" correctly
// pre-fills "Furniture" instead of leaving the field blank for the
// user to set redundantly (the exact behavior the product brief
// calls out: "the system already knows the product belongs to
// Furniture - the user should not then have to select it again").
const FURNITURE_HINT_WORDS = [
  'furniture', 'seating', 'sofa', 'chair', 'table', 'bed', 'wardrobe',
  'storage', 'tv unit', 'cabinet', 'shelf', 'bedroom', 'living room', 'kitchen',
];
function deriveLineItemCategory(product) {
  const haystack = `${product.category || ''} ${product.subcategory || ''}`.toLowerCase();
  if (FURNITURE_HINT_WORDS.some((w) => haystack.includes(w))) return 'Furniture';
  if (haystack.includes('service') || haystack.includes('installation')) return 'Installation';
  if (haystack.includes('hardware')) return 'Hardware';
  if (haystack.includes('cnc') || haystack.includes('laser')) return 'Service';
  return '';
}

// Countable units - a finished piece of furniture (or any other
// discretely-counted item) doesn't come in fractional units. A
// measurable/continuous unit genuinely can. Matched case-insensitively
// against whatever's typed/selected in the Unit field, since it's
// free text (populated from the product's own unit, or typed by hand).
const WHOLE_NUMBER_UNITS = new Set([
  'piece', 'pieces', 'pcs', 'pc', 'set', 'sets', 'pair', 'pairs',
  'nos', 'no', 'box', 'boxes', 'roll', 'rolls', 'bundle', 'bundles',
  'sheet', 'sheets', 'job', 'jobs',
]);
function quantityViolatesWholeUnitRule(quantity, unit) {
  const normalizedUnit = (unit || '').trim().toLowerCase();
  if (!WHOLE_NUMBER_UNITS.has(normalizedUnit)) return false;
  const n = Number(quantity);
  return Number.isFinite(n) && !Number.isInteger(n);
}

const emptyRow = () => ({ description: '', category: '', quantity: '1', unit: '', rate: '0', product_id: '', product_label: '', pricing_rule: '', margin_percent: null });

// Product ID + search, shared by every row - Family 102 Product ID
// requirement: the user should never need to remember Product IDs.
//
// The results dropdown is rendered through a portal into document.body
// instead of as a normal absolutely-positioned child here. This editor
// lives inside Modal's .modal-body, which scrolls (see Modal.css) - a
// row near the bottom of a long item list would have its dropdown
// clipped by that scroll container's overflow, or by the modal's own
// overflow:hidden card edge, no matter how high its z-index was set.
// Portaling it to <body> and positioning it in viewport coordinates
// (tracked on open/scroll/resize below) escapes both.
function ProductPicker({ row, onPick }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dropdownRect, setDropdownRect] = useState(null);
  const debounceRef = useRef(null);
  const boxRef = useRef(null);
  const dropdownRef = useRef(null);

  const updatePosition = useCallback(() => {
    if (!boxRef.current) return;
    const rect = boxRef.current.getBoundingClientRect();
    const width = Math.max(rect.width, 260);
    // Flip above the field instead of below if there isn't enough room
    // beneath it in the viewport - otherwise a row near the bottom of
    // the modal would still have its dropdown run off the bottom of
    // the screen even after escaping the modal's own clipping.
    const estimatedHeight = Math.min(320, 60 + results.length * 44);
    const spaceBelow = window.innerHeight - rect.bottom;
    const openUpward = spaceBelow < estimatedHeight && rect.top > estimatedHeight;
    setDropdownRect({
      top: openUpward ? undefined : rect.bottom + 4,
      bottom: openUpward ? window.innerHeight - rect.top + 4 : undefined,
      left: rect.left,
      width,
    });
  }, [results.length]);

  useEffect(() => {
    if (!open) return undefined;
    updatePosition();
    // Capture phase, not bubble - a scroll event on the modal's own
    // scrolling body (or any other scrollable ancestor) does not bubble
    // up to window, so only the capture phase sees it.
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);
    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [open, updatePosition]);

  // Re-run the up/down flip decision once results actually load in -
  // updatePosition's own estimatedHeight depends on results.length, but
  // a debounced search resolving after the dropdown is already open
  // wouldn't otherwise trigger a reposition on its own.
  useEffect(() => {
    if (open) updatePosition();
  }, [results, open, updatePosition]);

  useEffect(() => {
    const onClickOutside = (e) => {
      const insideField = boxRef.current && boxRef.current.contains(e.target);
      const insideDropdown = dropdownRef.current && dropdownRef.current.contains(e.target);
      if (!insideField && !insideDropdown) setOpen(false);
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
      {open && dropdownRect && createPortal(
        <div
          className="product-picker-dropdown product-picker-dropdown--portal"
          ref={dropdownRef}
          style={{ top: dropdownRect.top, bottom: dropdownRect.bottom, left: dropdownRect.left, width: dropdownRect.width }}
        >
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
        </div>,
        document.body
      )}
    </div>
  );
}

function LineItemEditor({ items, onChange, clientId }) {
  const updateRow = (idx, field, value) => {
    const next = items.map((row, i) => (i === idx ? {
      ...row, [field]: value,
      ...(field === 'rate' ? { pricing_rule: '', margin_percent: null } : {}),
    } : row));
    onChange(next);
  };

  const pickProduct = async (idx, product) => {
    if (product.__idOnly) {
      // Manual Product ID entry - Product ID is authoritative, so the
      // label is cleared until it's actually resolved server-side on
      // save; typing an ID here never lets the user also type a
      // conflicting name (Family 102 Product ID consistency rule).
      const next = items.map((row, i) => (i === idx ? { ...row, product_id: product.id, product_label: '', pricing_rule: '', margin_percent: null } : row));
      onChange(next);
      return;
    }
    const baseNext = items.map((row, i) => (i === idx ? {
      ...row,
      product_id: product.id,
      product_label: `${product.product_code} · ${product.name}`,
      description: row.description || product.name,
      category: row.category || deriveLineItemCategory(product),
      unit: row.unit || product.unit || '',
      rate: (row.rate === '0' || !row.rate) && product.selling_price != null ? String(product.selling_price) : row.rate,
      pricing_rule: '',
      margin_percent: null,
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
          margin_percent: res.data.margin_percent_used,
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
      {items.map((row, idx) => (
        <div className="line-item-card" key={idx}>
          <div className="line-item-primary-row">
            <div className="line-item-field line-item-field--product" data-label="Product">
              <ProductPicker row={row} onPick={(product) => pickProduct(idx, product)} />
            </div>
            <div className="line-item-field line-item-field--description" data-label="Description">
              <input
                type="text" placeholder="e.g. Wardrobe" value={row.description}
                onChange={(e) => updateRow(idx, 'description', e.target.value)}
              />
            </div>
          </div>
          <div className="line-item-secondary-row">
            <div className="line-item-field line-item-field--category" data-label="Category">
              <select value={row.category} onChange={(e) => updateRow(idx, 'category', e.target.value)}>
                <option value="">-</option>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="line-item-field line-item-field--qty" data-label="Qty">
              <input
                type="number" min="0.01" step="0.01" value={row.quantity}
                onChange={(e) => updateRow(idx, 'quantity', e.target.value)}
                className={quantityViolatesWholeUnitRule(row.quantity, row.unit) ? 'line-item-input-error' : ''}
              />
              {quantityViolatesWholeUnitRule(row.quantity, row.unit) && (
                <div className="line-item-field-error">{row.unit} must be a whole number</div>
              )}
            </div>
            <div className="line-item-field line-item-field--unit" data-label="Unit">
              <input type="text" placeholder="Nos/Lot" value={row.unit} onChange={(e) => updateRow(idx, 'unit', e.target.value)} />
            </div>
            <div className="line-item-field line-item-field--rate" data-label="Rate">
              <input type="number" min="0" step="0.01" value={row.rate} onChange={(e) => updateRow(idx, 'rate', e.target.value)} />
              {row.pricing_rule && (
                <div className="line-item-pricing-rule">
                  {row.pricing_rule === 'CUSTOMER_MARGIN_OVERRIDE' && 'Customer margin'}
                  {row.pricing_rule === 'CUSTOMER_PRODUCT_PRICE_OVERRIDE' && 'Customer negotiated price'}
                  {row.pricing_rule === 'PRODUCT_MARGIN' && 'Product margin'}
                  {row.pricing_rule === 'GLOBAL_DEFAULT_MARGIN' && 'Default margin'}
                  {row.margin_percent != null && ` (${row.margin_percent}%)`}
                </div>
              )}
            </div>
            <div className="line-item-field line-item-field--amount" data-label="Amount">
              <span className="line-item-amount">{formatCurrency((Number(row.quantity) || 0) * (Number(row.rate) || 0))}</span>
            </div>
            <div className="line-item-row-actions">
              <button type="button" onClick={() => moveRow(idx, -1)} disabled={idx === 0} title="Move up" aria-label="Move item up">↑</button>
              <button type="button" onClick={() => moveRow(idx, 1)} disabled={idx === items.length - 1} title="Move down" aria-label="Move item down">↓</button>
              <button type="button" onClick={() => removeRow(idx)} title="Remove" aria-label="Remove item" className="line-item-remove">×</button>
            </div>
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
export { emptyRow, quantityViolatesWholeUnitRule };
