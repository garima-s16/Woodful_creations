import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { ratesAPI, rateImportAPI } from '../../../utils/api';
import Table from '../../../components/common/Table';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import { formatCurrency } from '../../../utils/format';

const SOURCE_TYPES = [
  'INDORE_SUPPLIER', 'INDORE_SERVICE_PROVIDER', 'INDORE_MARKET_LISTING',
  'NATIONAL_MARKET_BENCHMARK', 'WOODFUL_HISTORICAL', 'WOODFUL_INTERNAL', 'MANUAL_VERIFIED',
];
const CONFIDENCE_LEVELS = ['HIGH', 'MEDIUM', 'LOW', 'NOT_VERIFIED'];
const STANDARD_UOMS = [
  'Piece', 'Set', 'Pair', 'Sq Ft', 'Running Ft', 'Meter', 'Sq Meter', 'Kg', 'Gram',
  'Litre', 'Millilitre', 'Sheet', 'Box', 'Pack', 'Roll', 'Bundle', 'Cu Ft',
  'Minute', 'Hour', 'Day', 'Job', 'Hole',
];

function confidenceBadgeClass(c) {
  if (c === 'HIGH') return 'status-ok';
  if (c === 'MEDIUM') return 'status-warning';
  return 'status-muted';
}

function RateCardsPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isMaster = user?.role === 'master';

  const [rates, setRates] = useState([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [editingRate, setEditingRate] = useState(null);
  const [historyFor, setHistoryFor] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    const params = {};
    if (search.trim()) params.search = search.trim();
    if (category) params.category = category;
    params.is_active = showInactive ? undefined : true;
    ratesAPI.list(params).then((res) => setRates(res.data)).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
  };

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, category, showInactive]);

  const submitCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await ratesAPI.create(formData);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add rate');
    } finally {
      setLoading(false);
    }
  };

  const submitRevise = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await ratesAPI.revise(editingRate.id, formData);
      setEditingRate(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to revise rate');
    } finally {
      setLoading(false);
    }
  };

  const deactivate = async (rate) => {
    setError('');
    try {
      await ratesAPI.deactivate(rate.id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to deactivate rate');
    }
  };

  const viewHistory = async (rate) => {
    setHistoryFor(rate);
    try {
      const res = await ratesAPI.history(rate.id);
      setHistory(res.data);
    } catch {
      setHistory([]);
    }
  };

  const columns = [
    { key: 'rate_code', label: 'Rate ID', render: (v, row) => <span className="business-id-badge">{row.business_id || v}</span> },
    { key: 'category', label: 'Category' },
    { key: 'subcategory', label: 'Subcategory' },
    { key: 'item_name', label: 'Item / Service' },
    { key: 'specification', label: 'Spec' },
    { key: 'uom', label: 'UOM' },
    { key: 'market_reference_rate', label: 'Market Ref.', render: (v) => v != null ? formatCurrency(v) : '\u2014' },
    { key: 'woodful_cost_rate', label: 'Woodful Cost', render: (v) => v != null ? formatCurrency(v) : '\u2014' },
    {
      key: 'effective_selling_rate', label: 'Selling Rate',
      render: (v, row) => (
        <span>
          {v != null ? formatCurrency(v) : '\u2014'}
          {row.override_price != null && <span className="status-badge status-warning" style={{ marginLeft: 6 }}>Overridden</span>}
        </span>
      ),
    },
    { key: 'confidence', label: 'Confidence', render: (v) => <span className={`status-badge ${confidenceBadgeClass(v)}`}>{v}</span> },
    { key: 'is_active', label: 'Status', render: (v) => <span className={`status-badge ${v ? 'status-ok' : 'status-muted'}`}>{v ? 'Active' : 'Inactive'}</span> },
    {
      key: 'actions', label: '', render: (v, row) => (
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-link" onClick={(e) => { e.stopPropagation(); viewHistory(row); }}>History</button>
          {isMaster && row.is_active && (
            <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingRate(row); }}>Revise</button>
          )}
          {isMaster && row.is_active && (
            <button className="btn-link" onClick={(e) => { e.stopPropagation(); deactivate(row); }}>Deactivate</button>
          )}
        </div>
      ),
    },
  ];

  const fields = [
    { name: 'category', label: 'Category', required: true, placeholder: 'e.g. Material, Furniture, CNC Services' },
    { name: 'subcategory', label: 'Subcategory', placeholder: 'e.g. Plywood, Tables' },
    { name: 'item_name', label: 'Item / Service Name', required: true },
    { name: 'specification', label: 'Specification', placeholder: 'e.g. 18mm BWP, Standard' },
    { name: 'uom', label: 'UOM', type: 'select', required: true, options: STANDARD_UOMS.map((u) => ({ value: u, label: u })) },
    { name: 'woodful_selling_rate', label: 'Woodful Selling Rate', type: 'number' },
    { name: 'location', label: 'Location', placeholder: 'Indore, Madhya Pradesh', advanced: true },
    { name: 'market_reference_rate', label: 'Market Reference Rate (Indore)', type: 'number', advanced: true },
    { name: 'woodful_cost_rate', label: 'Woodful Internal Cost', type: 'number', advanced: true },
    { name: 'overhead_percent', label: 'Overhead %', type: 'number', advanced: true },
    { name: 'target_margin_percent', label: 'Target Margin %', type: 'number', advanced: true },
    { name: 'wastage_percent', label: 'Wastage %', type: 'number', advanced: true },
    { name: 'tax_percent', label: 'Tax %', type: 'number', advanced: true },
    { name: 'source_type', label: 'Source Type', type: 'select', required: true, advanced: true,
      options: SOURCE_TYPES.map((s) => ({ value: s, label: s.replace(/_/g, ' ') })) },
    { name: 'confidence', label: 'Confidence', type: 'select', advanced: true,
      options: CONFIDENCE_LEVELS.map((c) => ({ value: c, label: c.replace('_', ' ') })) },
    { name: 'source_reference', label: 'Source Reference', type: 'textarea', advanced: true },
    { name: 'notes', label: 'Notes', type: 'textarea', advanced: true },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Rate Master</h1>
          <p className="page-summary">
            Three separate pricing layers: Indore Market Reference, Woodful Internal Cost, and Woodful Selling Rate.
            Never overwritten - every change creates a new version.
          </p>
        </div>
        <div className="page-actions">
          {isMaster && <button className="btn-primary" onClick={() => setShowAdd(true)}>+ Add Rate</button>}
          {isMaster && <a className="btn-secondary" href={rateImportAPI.templateUrl}>Download Template</a>}
          {isMaster && <button className="btn-secondary" onClick={() => navigate('/rate-master/import')}>Import Excel</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <form className="page-search" onSubmit={(e) => e.preventDefault()}>
        <input
          type="text" className="form-input" placeholder="Search item, spec, or Rate ID..."
          value={search} onChange={(e) => setSearch(e.target.value)}
        />
        <input
          type="text" className="form-input" placeholder="Filter by category..."
          value={category} onChange={(e) => setCategory(e.target.value)}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}>
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Include inactive
        </label>
      </form>

      <Table
        columns={columns} data={rates} loading={pageLoading} error={loadError} onRetry={load}
        emptyMessage="No rates yet. Add rates individually or import the Rate Master template."
        emptyAction={isMaster ? { label: 'Add Rate', onClick: () => setShowAdd(true) } : undefined}
      />

      <Modal isOpen={showAdd} title="Add Rate" onClose={() => setShowAdd(false)}>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 0 }}>
          Market Reference is what the market charges. Woodful Cost is what it actually costs Woodful.
          Woodful Selling Rate is what Woodful charges - these are never the same number automatically.
        </p>
        <Form fields={fields} onSubmit={submitCreate} loading={loading} submitText="Add Rate" />
      </Modal>

      <Modal isOpen={!!editingRate} title={`Revise ${editingRate?.item_name || ''}`} onClose={() => setEditingRate(null)}>
        {editingRate && (
          <>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 0 }}>
              This creates a new version effective today. The current rate is deactivated but preserved -
              any Estimate/Order that already used it keeps its original number.
            </p>
            <Form
              fields={fields.filter((f) => !['category', 'subcategory', 'item_name', 'specification', 'uom', 'location'].includes(f.name))}
              onSubmit={submitRevise} loading={loading} submitText="Save New Version" initialValues={editingRate}
            />
          </>
        )}
      </Modal>

      <Modal isOpen={!!historyFor} title={`Rate History - ${historyFor?.item_name || ''}`} onClose={() => setHistoryFor(null)}>
        {history.length === 0 && <p>No version history.</p>}
        {history.length > 0 && (
          <table className="data-table">
            <thead>
              <tr><th>Rate ID</th><th>Selling Rate</th><th>Effective From</th><th>Effective To</th><th>Status</th></tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id}>
                  <td>{h.rate_code}</td>
                  <td>{h.effective_selling_rate != null ? formatCurrency(h.effective_selling_rate) : '\u2014'}</td>
                  <td>{h.effective_from ? new Date(h.effective_from).toLocaleDateString() : '-'}</td>
                  <td>{h.effective_to ? new Date(h.effective_to).toLocaleDateString() : 'Current'}</td>
                  <td><span className={`status-badge ${h.is_active ? 'status-ok' : 'status-muted'}`}>{h.is_active ? 'Active' : 'Superseded'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Modal>
    </div>
  );
}

export default RateCardsPage;
