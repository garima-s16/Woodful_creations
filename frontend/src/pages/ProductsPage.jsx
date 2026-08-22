import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { productsAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import KpiCard from '../components/common/KpiCard';
import { formatCurrency } from '../utils/currency';

const CATEGORY_OPTIONS = ['Seating', 'Tables', 'Storage', 'Bedroom', 'Kitchen', 'Decor', 'Services', 'Other'];
const UNIT_OPTIONS = ['Nos', 'Set', 'Sq Ft', 'Running Ft', 'Kg', 'Lot', 'Visit'];

function ProductsPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isMaster = user?.role === 'master';

  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [status, setStatus] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [duplicateWarning, setDuplicateWarning] = useState(null); // { matches, pendingFormData }
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = () => {
    setPageLoading(true);
    const params = {};
    if (search.trim()) params.search = search.trim();
    if (category) params.category = category;
    if (status) params.is_active = status === 'active';
    productsAPI.list(params).then((res) => setProducts(res.data)).finally(() => setPageLoading(false));
  };

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, category, status]);

  const submitCreate = async (formData, confirmDuplicate = false) => {
    setLoading(true);
    setError('');
    try {
      await productsAPI.create(formData, confirmDuplicate);
      setShowAdd(false);
      setDuplicateWarning(null);
      load();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409 && detail?.matches) {
        setDuplicateWarning({ matches: detail.matches, pendingFormData: formData });
      } else {
        setError(typeof detail === 'string' ? detail : 'Failed to add product');
      }
    } finally {
      setLoading(false);
    }
  };

  const confirmCreateDespiteDuplicate = () => {
    if (duplicateWarning?.pendingFormData) submitCreate(duplicateWarning.pendingFormData, true);
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await productsAPI.update(editingProduct.id, formData);
      setEditingProduct(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update product');
    } finally {
      setLoading(false);
    }
  };

  const toggleActive = async (product) => {
    setError('');
    try {
      await productsAPI.update(product.id, { is_active: !product.is_active });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update product status');
    }
  };

  const confirmDelete = async () => {
    setError('');
    try {
      await productsAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'This product cannot be deleted.');
      setPendingDelete(null);
    }
  };

  const columns = [
    { key: 'business_id', label: 'Product ID', render: (v, row) => <span className="business-id-badge">{v || row.product_code}</span> },
    { key: 'name', label: 'Product Name' },
    { key: 'category', label: 'Category' },
    { key: 'unit', label: 'Unit' },
    { key: 'selling_price', label: 'Default Rate', render: (v) => v != null ? formatCurrency(v) : '\u2014' },
    { key: 'gst_percent', label: 'GST', render: (v) => v != null ? `${v}%` : '\u2014' },
    { key: 'is_active', label: 'Status', render: (v) => <span className={`status-badge ${v ? 'status-ok' : 'status-muted'}`}>{v ? 'Active' : 'Inactive'}</span> },
    {
      key: 'toggle_action', label: '', render: (v, row) => (
        isMaster ? (
          <button className="btn-link" onClick={(e) => { e.stopPropagation(); toggleActive(row); }}>
            {row.is_active ? 'Deactivate' : 'Activate'}
          </button>
        ) : null
      ),
    },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isMaster ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingProduct(row); }}>Edit</button> : null
      ),
    },
    {
      key: 'delete_action', label: '', render: (v, row) => (
        isMaster ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setPendingDelete(row); }}>Delete</button> : null
      ),
    },
  ];

  const fields = [
    { name: 'name', label: 'Product Name', required: true },
    { name: 'product_type', label: 'Type', type: 'select', options: [
      { value: 'standard', label: 'Standard (catalog)' }, { value: 'custom', label: 'Custom (one-off)' },
    ] },
    { name: 'category', label: 'Category', type: 'select', options: CATEGORY_OPTIONS.map((c) => ({ value: c, label: c })) },
    { name: 'subcategory', label: 'Subcategory', advanced: true },
    { name: 'unit', label: 'Unit', type: 'select', options: UNIT_OPTIONS.map((u) => ({ value: u, label: u })) },
    { name: 'selling_price', label: 'Default Rate', type: 'number' },
    { name: 'gst_percent', label: 'GST %', type: 'number' },
    { name: 'primary_material', label: 'Primary Material', advanced: true },
    { name: 'finish', label: 'Finish', advanced: true },
    { name: 'specifications', label: 'Description / Specifications', type: 'textarea', advanced: true },
    { name: 'notes', label: 'Notes', type: 'textarea', advanced: true },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Products</h1>
          <p className="page-summary">The catalog every Estimate and Order line item references.</p>
        </div>
        <div className="page-actions">
          {isMaster && <button className="btn-primary" onClick={() => setShowAdd(true)}>+ Add Product</button>}
          {isMaster && <button className="btn-secondary" onClick={() => navigate('/products/import')}>Import Excel</button>}
          <a className="btn-secondary" href={reportsAPI.downloadUrl('products.xlsx')} target="_blank" rel="noreferrer">Export Excel</a>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <div className="kpi-row">
        <KpiCard label="Total Products" value={products.length} />
        <KpiCard label="Active" value={products.filter((p) => p.is_active).length} />
      </div>

      <form className="page-search" onSubmit={(e) => e.preventDefault()}>
        <input
          type="text" className="form-input" placeholder="Search by name, code, or Product ID..."
          value={search} onChange={(e) => setSearch(e.target.value)}
        />
        <select className="form-input" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All Categories</option>
          {CATEGORY_OPTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="form-input" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </form>

      <Table
        columns={columns} data={products} loading={pageLoading}
        onRowClick={(row) => navigate(`/products/${row.id}`)}
        emptyMessage="No products yet. Add your first product to start using it in Estimates and Orders."
        emptyAction={isMaster ? { label: 'Add Product', onClick: () => setShowAdd(true) } : undefined}
      />

      <Modal isOpen={showAdd} title="Add Product" onClose={() => { setShowAdd(false); setDuplicateWarning(null); }}>
        <Form fields={fields} onSubmit={(data) => submitCreate(data, false)} loading={loading} submitText="Add Product" />
      </Modal>

      <Modal isOpen={!!editingProduct} title={`Edit ${editingProduct?.name || ''}`} onClose={() => setEditingProduct(null)}>
        {editingProduct && (
          <Form fields={fields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingProduct} />
        )}
      </Modal>

      <ConfirmDialog
        isOpen={!!duplicateWarning}
        title="Possible existing product found"
        message={duplicateWarning ? (
          `A product with a very similar name already exists:\n` +
          duplicateWarning.matches.map((m) => `${m.product_code} - ${m.name}`).join('\n') +
          `\n\nCreate this as a new, separate product anyway?`
        ) : ''}
        onConfirm={confirmCreateDespiteDuplicate}
        onCancel={() => setDuplicateWarning(null)}
      />

      <ConfirmDialog
        isOpen={!!pendingDelete}
        message={pendingDelete ? `Permanently delete ${pendingDelete.product_code} - ${pendingDelete.name}? This cannot be undone.` : ''}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

export default ProductsPage;
