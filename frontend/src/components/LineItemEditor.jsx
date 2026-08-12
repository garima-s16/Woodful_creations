import React from 'react';
import { formatCurrency } from '../utils/currency';
import '../styles/components/LineItemEditor.css';

const CATEGORIES = ['Material', 'Labor', 'Furniture', 'Hardware', 'Installation', 'Transportation', 'Design', 'Service', 'Other'];

const emptyRow = () => ({ description: '', category: '', quantity: '1', unit: '', rate: '0' });

function LineItemEditor({ items, onChange }) {
  const updateRow = (idx, field, value) => {
    const next = items.map((row, i) => (i === idx ? { ...row, [field]: value } : row));
    onChange(next);
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
        <span>Description</span><span>Category</span><span>Qty</span><span>Unit</span><span>Rate</span><span>Amount</span><span />
      </div>
      {items.map((row, idx) => (
        <div className="line-item-row" key={idx}>
          <input
            type="text" placeholder="e.g. Wardrobe" value={row.description}
            onChange={(e) => updateRow(idx, 'description', e.target.value)}
          />
          <select value={row.category} onChange={(e) => updateRow(idx, 'category', e.target.value)}>
            <option value="">-</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input type="number" min="0" step="0.01" value={row.quantity} onChange={(e) => updateRow(idx, 'quantity', e.target.value)} />
          <input type="text" placeholder="Nos/Lot" value={row.unit} onChange={(e) => updateRow(idx, 'unit', e.target.value)} />
          <input type="number" min="0" step="0.01" value={row.rate} onChange={(e) => updateRow(idx, 'rate', e.target.value)} />
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
