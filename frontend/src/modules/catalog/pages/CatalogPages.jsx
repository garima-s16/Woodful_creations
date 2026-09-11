// Catalog pages: products list/detail/import, rate cards list/import.
// Combines the former ProductsPage.jsx, ProductDetailPage.jsx,
// ProductImportPage.jsx, RateCardsPage.jsx, and RateCardImportPage.jsx.
import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { documentsAPI, productImportAPI, productsAPI, rateImportAPI, ratesAPI, reportsAPI } from '../../../utils/api';
import { Alert, Card, ConfirmDialog, Form, KpiCard, Modal, Table } from '../../../components/common/UI';
import { classifyLoadError, formatCurrency } from '../../../utils/utils';
import { DocumentsPanel } from '../../../components/Assistant';

// --- ProductsPage.jsx ---
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
  const [deleting, setDeleting] = useState(false);
  const [duplicateWarning, setDuplicateWarning] = useState(null); // { matches, pendingFormData }
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
    if (status) params.is_active = status === 'active';
    productsAPI.list(params).then((res) => setProducts(res.data)).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
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
    setDeleting(true);
    try {
      await productsAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'This product cannot be deleted.');
      setPendingDelete(null);
    } finally {
      setDeleting(false);
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
        columns={columns} data={products} loading={pageLoading} error={loadError} onRetry={load}
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
        loading={loading}
      />

      <ConfirmDialog
        isOpen={!!pendingDelete}
        message={pendingDelete ? `Permanently delete ${pendingDelete.product_code} - ${pendingDelete.name}? This cannot be undone.` : ''}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
        loading={deleting}
      />
    </div>
  );
}

// --- ProductDetailPage.jsx ---
function ProductDetailPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isMaster = user?.role === 'master';

  const [product, setProduct] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState(null);

  const load = () => {
    setLoadError(null);
    productsAPI.get(productId).then((res) => setProduct(res.data)).catch((err) => setLoadError(classifyLoadError(err, 'product')));
  };
  useEffect(() => { load(); }, [productId]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleActive = async () => {
    await productsAPI.update(product.id, { is_active: !product.is_active });
    load();
  };

  const confirmDelete = async () => {
    setError('');
    setDeleting(true);
    try {
      await productsAPI.remove(product.id);
      navigate('/products');
    } catch (err) {
      setError(err.response?.data?.detail || 'This product cannot be deleted - it has historical references. Deactivate it instead.');
      setPendingDelete(false);
    } finally {
      setDeleting(false);
    }
  };

  if (loadError) return (
    <div className="page">
      <Alert type="error" message={loadError.message} />
      {!loadError.isNotFound && (
        <button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button>
      )}
    </div>
  );
  if (!product) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/products" className="btn-link">&larr; Back to Products</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{product.name}</h1>
          <div className="detail-subtitle">
            {product.category || 'Uncategorized'}
            {product.business_id && <span className="business-id-badge">{product.business_id}</span>}
            <span className={`status-badge ${product.is_active ? 'status-ok' : 'status-muted'}`} style={{ marginLeft: 8 }}>
              {product.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
        </div>
        {isMaster && (
          <div className="page-actions">
            <button className="btn-secondary" onClick={toggleActive}>
              {product.is_active ? 'Deactivate' : 'Activate'}
            </button>
            <a className="btn-secondary" href={reportsAPI.downloadUrl(`products/${product.id}/product.pdf`)} target="_blank" rel="noreferrer">
              Export PDF
            </a>
            <a className="btn-secondary" href={reportsAPI.downloadUrl(`products.xlsx?search=${encodeURIComponent(product.product_code)}`)} target="_blank" rel="noreferrer">
              Export Excel
            </a>
            <button className="btn-link" onClick={() => setPendingDelete(true)}>Delete</button>
          </div>
        )}
      </div>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      <Card title="Product Information">
        <div className="detail-meta">
          <div className="detail-meta-item"><span className="detail-meta-label">Product ID</span><span className="detail-meta-value">{product.business_id || '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Product Code</span><span className="detail-meta-value">{product.product_code}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Type</span><span className="detail-meta-value">{product.product_type}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Category</span><span className="detail-meta-value">{product.category || '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Subcategory</span><span className="detail-meta-value">{product.subcategory || '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Unit</span><span className="detail-meta-value">{product.unit}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Default Rate</span><span className="detail-meta-value">{product.selling_price != null ? formatCurrency(product.selling_price) : '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">GST %</span><span className="detail-meta-value">{product.gst_percent != null ? `${product.gst_percent}%` : '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Primary Material</span><span className="detail-meta-value">{product.primary_material || '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Finish</span><span className="detail-meta-value">{product.finish || '-'}</span></div>
        </div>
        {product.specifications && (
          <div style={{ marginTop: 16 }}>
            <div className="detail-meta-label">Description / Specifications</div>
            <p>{product.specifications}</p>
          </div>
        )}
      </Card>

      {isMaster && (product.cost_price != null || product.margin != null) && (
        <Card title="Costing">
          <div className="detail-meta">
            <div className="detail-meta-item"><span className="detail-meta-label">Cost Price</span><span className="detail-meta-value">{product.cost_price != null ? formatCurrency(product.cost_price) : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Margin</span><span className="detail-meta-value">{product.margin != null ? formatCurrency(product.margin) : '-'}</span></div>
          </div>
        </Card>
      )}

      <Card title="System Information">
        <div className="detail-meta">
          <div className="detail-meta-item"><span className="detail-meta-label">Created</span><span className="detail-meta-value">{product.created_at ? new Date(product.created_at).toLocaleString() : '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Last Updated</span><span className="detail-meta-value">{product.updated_at ? new Date(product.updated_at).toLocaleString() : '-'}</span></div>
        </div>
      </Card>

      <DocumentsPanel title="Documents" api={{
        list: () => documentsAPI.list('product', productId),
        upload: (file, description) => documentsAPI.upload('product', productId, file, description),
        downloadUrl: (documentId) => documentsAPI.downloadUrl('product', productId, documentId),
        remove: (documentId) => documentsAPI.remove('product', productId, documentId),
      }} canUpload={isMaster} />

      <ConfirmDialog
        isOpen={pendingDelete}
        message={`Are you sure you want to permanently delete ${product.product_code} - ${product.name}? This cannot be undone.`}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(false)}
        loading={deleting}
      />
    </div>
  );
}

// --- ProductImportPage.jsx ---
function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function rowStatus(row, resolution) {
  if (row.errors.length > 0) return { label: 'ERROR', className: 'status-danger' };
  if (row.is_duplicate) return { label: 'EXISTING', className: 'status-neutral' };
  if (row.possible_match_product_id) {
    if (resolution === 'use_existing') return { label: 'USING EXISTING', className: 'status-neutral' };
    if (resolution === 'create_new') return { label: 'NEW (CONFIRMED)', className: 'status-gold' };
    return { label: 'POSSIBLE MATCH', className: 'status-warning' };
  }
  return { label: 'NEW', className: 'status-gold' };
}

function ProductImportPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({});
  // row_number -> 'use_existing' | 'create_new', only meaningful for
  // rows with a possible_match_product_id (a fuzzy/uncertain match,
  // unlike is_duplicate which the backend already treats as certain).
  // Commit must not silently guess either way - see handleImport.
  const [resolutions, setResolutions] = useState({});
  const [stage, setStage] = useState('empty'); // empty | selected | validating | preview | importing | success | error
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [downloadingErrors, setDownloadingErrors] = useState(false);
  const fileInputRef = useRef(null);

  const resetFile = () => {
    setFile(null);
    setPreview(null);
    setExcludedRows({});
    setResolutions({});
    setStage('empty');
    setError('');
  };

  const handleFileSelected = (selected) => {
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith('.xlsx')) {
      setError('Please choose a .xlsx file - other formats are not supported.');
      return;
    }
    setFile(selected);
    setPreview(null);
    setResult(null);
    setError('');
    setStage('selected');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFileSelected(e.dataTransfer.files?.[0]);
  };

  const handleValidate = async () => {
    if (!file) return;
    setStage('validating');
    setError('');
    try {
      const res = await productImportAPI.preview(file);
      setPreview(res.data);
      setExcludedRows({});
      setResolutions({});
      setStage('preview');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not read this file. Make sure you used the downloaded template.');
      setStage('selected');
    }
  };

  const handleImport = async () => {
    if (!preview) return;
    setStage('importing');
    setError('');
    try {
      const rowsToCommit = preview.rows
        .filter((r) => r.errors.length === 0)
        .map((r) => ({
          name: r.name, product_type: r.product_type || 'standard', category: r.category,
          subcategory: r.subcategory, unit: r.unit || 'Nos', length: r.length, width: r.width, height: r.height,
          dimension_unit: r.dimension_unit, primary_material: r.primary_material, finish: r.finish,
          material_cost: r.material_cost, hardware_cost: r.hardware_cost, labour_cost: r.labour_cost,
          machine_cost: r.machine_cost, finish_cost: r.finish_cost, packing_cost: r.packing_cost,
          transport_cost: r.transport_cost, other_cost: r.other_cost, overhead_percent: r.overhead_percent,
          margin_percent: r.margin_percent, cost_price: r.cost_price, selling_price: r.selling_price,
          notes: r.notes, skip: !!excludedRows[r.row_number],
          // Certain exact match: send it as-is. Possible/uncertain match:
          // only send it if the user explicitly chose "Use Existing" -
          // never guess, and "Create New" must send null so the backend
          // creates a fresh product rather than silently reusing the
          // suggested match.
          matched_product_id: r.is_duplicate
            ? r.matched_product_id
            : (r.possible_match_product_id && resolutions[r.row_number] === 'use_existing'
                ? r.possible_match_product_id : null),
        }));
      const res = await productImportAPI.commit(rowsToCommit);
      setResult(res.data);
      setPreview(null);
      setFile(null);
      setStage(res.data.error ? 'error' : 'success');
    } catch (err) {
      setError(err.response?.data?.detail || 'Import failed. Please try again.');
      setStage('preview');
    }
  };

  const downloadErrorReport = async () => {
    if (!file) return;
    setDownloadingErrors(true);
    setError('');
    try {
      const res = await productImportAPI.errorReport(file);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Product_Import_Errors.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not generate the error report. Please try again.');
    } finally {
      setDownloadingErrors(false);
    }
  };

  const errorCount = preview ? preview.rows.filter((r) => r.errors.length > 0).length : 0;
  const unresolvedCount = preview
    ? preview.rows.filter((r) => r.errors.length === 0 && !excludedRows[r.row_number]
        && r.possible_match_product_id && !resolutions[r.row_number]).length
    : 0;
  const importableCount = preview ? preview.rows.filter((r) => r.errors.length === 0 && !excludedRows[r.row_number]).length : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Import Products from Excel</h1>
          <p className="page-summary">
            Download the template, fill in one row per product, then upload it here for review before anything is saved.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => navigate('/products')}>Back to Products</button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {(stage === 'success' || stage === 'error') && result && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>{stage === 'error' ? 'Import Partially Complete' : 'Import Complete'}</h3>
            <div className="import-result-grid">
              <div><span className="import-result-number">{result.created_products}</span><span className="import-result-label">New Products</span></div>
              <div><span className="import-result-number">{result.skipped}</span><span className="import-result-label">Skipped</span></div>
            </div>
            {result.error && <Alert type="warning" message={result.error} />}
            <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
              <button className="btn-primary" onClick={() => navigate('/products')}>View Imported Products</button>
              <button className="btn-secondary" onClick={resetFile}>Import Another File</button>
            </div>
          </div>
        </Card>
      )}

      {(stage === 'empty' || stage === 'selected' || stage === 'validating') && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={productImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
                Download Template
              </a>
            </p>

            {!file && (
              <div
                className={`import-dropzone ${dragOver ? 'drag-over' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
              >
                <p className="import-dropzone-title">Drag and drop your Excel file here</p>
                <p className="import-dropzone-hint">or click to choose a file &middot; accepts .xlsx only</p>
                <input
                  ref={fileInputRef} type="file" accept=".xlsx" style={{ display: 'none' }}
                  onChange={(e) => handleFileSelected(e.target.files?.[0])}
                />
              </div>
            )}

            {file && (
              <div className="import-file-selected">
                <div>
                  <span className="import-file-name">{file.name}</span>
                  <span className="import-file-size">{formatFileSize(file.size)}</span>
                </div>
                <button className="btn-link" onClick={resetFile} disabled={stage === 'validating'}>Remove</button>
              </div>
            )}

            <button
              className="btn-primary" style={{ marginTop: 16 }}
              onClick={handleValidate} disabled={!file || stage === 'validating'}
            >
              {stage === 'validating' ? 'Validating...' : 'Validate & Preview'}
            </button>
          </div>
        </Card>
      )}

      {(stage === 'preview' || stage === 'importing') && preview && (
        <>
          <Card>
            <div className="card-body">
              <h3 style={{ marginTop: 0 }}>{preview.total_rows} row{preview.total_rows !== 1 ? 's' : ''} detected</h3>
              <p>
                {preview.new_rows} new product{preview.new_rows !== 1 ? 's' : ''} &middot;{' '}
                {preview.error_rows} row{preview.error_rows !== 1 ? 's' : ''} rejected
                {preview.error_rows > 0 ? ' (won\u2019t be imported)' : ''}.
              </p>
              {preview.error_rows > 0 && (
                <button className="btn-link" onClick={downloadErrorReport} disabled={downloadingErrors}>
                  {downloadingErrors ? 'Preparing report...' : 'Download Error Report'}
                </button>
              )}
            </div>
          </Card>

          <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th></th><th>Product Name</th><th>Category</th><th>Unit</th><th>Default Rate</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r) => {
                const resolution = resolutions[r.row_number];
                const status = rowStatus(r, resolution);
                const canExclude = r.errors.length === 0;
                return (
                  <tr key={r.row_number} style={{ opacity: excludedRows[r.row_number] ? 0.5 : 1 }}>
                    <td>
                      {canExclude && (
                        <input
                          type="checkbox" checked={!excludedRows[r.row_number]}
                          onChange={(e) => setExcludedRows((prev) => ({ ...prev, [r.row_number]: !e.target.checked }))}
                        />
                      )}
                    </td>
                    <td>{r.name || '-'}</td>
                    <td>{r.category || '-'}</td>
                    <td>{r.unit || '-'}</td>
                    <td>{r.selling_price != null ? r.selling_price : '-'}</td>
                    <td>
                      <span className={`status-badge ${status.className}`}>{status.label}</span>
                      {r.errors.length > 0 && (
                        <div className="import-row-error">{r.errors.join('; ')}</div>
                      )}
                      {r.possible_match_product_id && !excludedRows[r.row_number] && (
                        <div className="import-row-possible-match">
                          <span>Possibly the same as "{r.possible_match_name}"?</span>{' '}
                          <button
                            type="button" className="btn-link"
                            onClick={() => setResolutions((prev) => ({ ...prev, [r.row_number]: 'use_existing' }))}
                          >Use Existing</button>{' '}
                          <button
                            type="button" className="btn-link"
                            onClick={() => setResolutions((prev) => ({ ...prev, [r.row_number]: 'create_new' }))}
                          >Create New</button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
            <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="btn-primary" onClick={handleImport} disabled={stage === 'importing' || importableCount === 0 || unresolvedCount > 0}>
              {stage === 'importing' ? 'Importing...' : `Confirm Import (${importableCount} row${importableCount !== 1 ? 's' : ''})`}
            </button>
            <button className="btn-secondary" onClick={resetFile} disabled={stage === 'importing'}>Cancel</button>
            {unresolvedCount > 0 && (
              <span className="import-row-error">
                {unresolvedCount} row{unresolvedCount !== 1 ? 's need' : ' needs'} a possible-match decision before importing.
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// --- RateCardsPage.jsx ---
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
          <div className="table-container">
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
          </div>
        )}
      </Modal>
    </div>
  );
}

// --- RateCardImportPage.jsx ---
function formatFileSizeRC(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function rowStatusRC(row) {
  if (row.errors.length > 0) return { label: 'ERROR', className: 'status-danger' };
  if (row.is_update) return { label: 'UPDATE (new version)', className: 'status-info' };
  return { label: 'NEW', className: 'status-gold' };
}

function RateCardImportPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({});
  const [stage, setStage] = useState('empty'); // empty | selected | validating | preview | importing | success | error
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [downloadingErrors, setDownloadingErrors] = useState(false);
  const fileInputRef = useRef(null);

  const resetFile = () => {
    setFile(null);
    setPreview(null);
    setExcludedRows({});
    setStage('empty');
    setError('');
  };

  const handleFileSelected = (selected) => {
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith('.xlsx')) {
      setError('Please choose a .xlsx file - other formats are not supported.');
      return;
    }
    setFile(selected);
    setPreview(null);
    setResult(null);
    setError('');
    setStage('selected');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFileSelected(e.dataTransfer.files?.[0]);
  };

  const handleValidate = async () => {
    if (!file) return;
    setStage('validating');
    setError('');
    try {
      const res = await rateImportAPI.preview(file);
      setPreview(res.data);
      setExcludedRows({});
      setStage('preview');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not read this file. Make sure you used the downloaded template.');
      setStage('selected');
    }
  };

  const handleImport = async () => {
    if (!preview) return;
    setStage('importing');
    setError('');
    try {
      const rowsToCommit = preview.rows
        .filter((r) => r.errors.length === 0)
        .map((r) => ({
          matched_rate_id: r.matched_rate_id,
          category: r.category, subcategory: r.subcategory, item_name: r.item_name,
          specification: r.specification, location: r.location || 'Indore, Madhya Pradesh', uom: r.uom,
          market_reference_rate: r.market_reference_rate, woodful_cost_rate: r.woodful_cost_rate,
          woodful_selling_rate: r.woodful_selling_rate, overhead_percent: r.overhead_percent,
          target_margin_percent: r.target_margin_percent, wastage_percent: r.wastage_percent,
          tax_percent: r.tax_percent, source_type: r.source_type, source_reference: r.source_reference,
          confidence: r.confidence || 'NOT_VERIFIED', notes: r.notes,
          skip: !!excludedRows[r.row_number],
        }));
      const res = await rateImportAPI.commit(rowsToCommit);
      setResult(res.data);
      setPreview(null);
      setFile(null);
      setStage(res.data.error ? 'error' : 'success');
    } catch (err) {
      setError(err.response?.data?.detail || 'Import failed. Please try again.');
      setStage('preview');
    }
  };

  const downloadErrorReport = async () => {
    if (!file) return;
    setDownloadingErrors(true);
    setError('');
    try {
      const res = await rateImportAPI.errorReport(file);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Rate_Master_Import_Errors.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not generate the error report. Please try again.');
    } finally {
      setDownloadingErrors(false);
    }
  };

  const errorCount = preview ? preview.rows.filter((r) => r.errors.length > 0).length : 0;
  const importableCount = preview ? preview.rows.filter((r) => r.errors.length === 0 && !excludedRows[r.row_number]).length : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Import Rate Master from Excel</h1>
          <p className="page-summary">
            Download the template, fill in one row per rate, then upload it here for review before anything is saved. Leave Rate ID blank for a new rate, or use an existing Rate ID to create a new version of it.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => navigate('/rate-master')}>Back to Rate Master</button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {(stage === 'success' || stage === 'error') && result && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>{stage === 'error' ? 'Import Partially Complete' : 'Import Complete'}</h3>
            <div className="import-result-grid">
              <div><span className="import-result-number">{result.created}</span><span className="import-result-label">New Rates</span></div>
              <div><span className="import-result-number">{result.updated}</span><span className="import-result-label">Updated (new version)</span></div>
              <div><span className="import-result-number">{result.skipped}</span><span className="import-result-label">Skipped</span></div>
            </div>
            {result.error && <Alert type="warning" message={result.error} />}
            <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
              <button className="btn-primary" onClick={() => navigate('/rate-master')}>View Rate Master</button>
              <button className="btn-secondary" onClick={resetFile}>Import Another File</button>
            </div>
          </div>
        </Card>
      )}

      {(stage === 'empty' || stage === 'selected' || stage === 'validating') && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={rateImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
                Download Template
              </a>
            </p>

            {!file && (
              <div
                className={`import-dropzone ${dragOver ? 'drag-over' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
              >
                <p className="import-dropzone-title">Drag and drop your Excel file here</p>
                <p className="import-dropzone-hint">or click to choose a file &middot; accepts .xlsx only</p>
                <input
                  ref={fileInputRef} type="file" accept=".xlsx" style={{ display: 'none' }}
                  onChange={(e) => handleFileSelected(e.target.files?.[0])}
                />
              </div>
            )}

            {file && (
              <div className="import-file-selected">
                <div>
                  <span className="import-file-name">{file.name}</span>
                  <span className="import-file-size">{formatFileSizeRC(file.size)}</span>
                </div>
                <button className="btn-link" onClick={resetFile} disabled={stage === 'validating'}>Remove</button>
              </div>
            )}

            <button
              className="btn-primary" style={{ marginTop: 16 }}
              onClick={handleValidate} disabled={!file || stage === 'validating'}
            >
              {stage === 'validating' ? 'Validating...' : 'Validate & Preview'}
            </button>
          </div>
        </Card>
      )}

      {(stage === 'preview' || stage === 'importing') && preview && (
        <>
          <Card>
            <div className="card-body">
              <h3 style={{ marginTop: 0 }}>{preview.total_rows} row{preview.total_rows !== 1 ? 's' : ''} detected</h3>
              <p>
                {preview.new_rows} new rate{preview.new_rows !== 1 ? 's' : ''} &middot;{' '}
                {preview.update_rows} update{preview.update_rows !== 1 ? 's' : ''} (new version) &middot;{' '}
                {preview.error_rows} row{preview.error_rows !== 1 ? 's' : ''} rejected
                {preview.error_rows > 0 ? ' (won\u2019t be imported)' : ''}.
              </p>
              {preview.error_rows > 0 && (
                <button className="btn-link" onClick={downloadErrorReport} disabled={downloadingErrors}>
                  {downloadingErrors ? 'Preparing report...' : 'Download Error Report'}
                </button>
              )}
            </div>
          </Card>

          <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th></th><th>Category</th><th>Item / Service</th><th>UOM</th><th>Market Ref.</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r) => {
                const status = rowStatusRC(r);
                const canExclude = r.errors.length === 0;
                return (
                  <tr key={r.row_number} style={{ opacity: excludedRows[r.row_number] ? 0.5 : 1 }}>
                    <td>
                      {canExclude && (
                        <input
                          type="checkbox" checked={!excludedRows[r.row_number]}
                          onChange={(e) => setExcludedRows((prev) => ({ ...prev, [r.row_number]: !e.target.checked }))}
                        />
                      )}
                    </td>
                    <td>{r.category || '-'}{r.subcategory ? ` / ${r.subcategory}` : ''}</td>
                    <td>{r.item_name || '-'}</td>
                    <td>{r.uom || '-'}</td>
                    <td>{r.market_reference_rate != null ? r.market_reference_rate : '-'}</td>
                    <td>
                      <span className={`status-badge ${status.className}`}>{status.label}</span>
                      {r.errors.length > 0 && (
                        <div className="import-row-error">{r.errors.join('; ')}</div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>

          <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="btn-primary" onClick={handleImport} disabled={stage === 'importing' || importableCount === 0}>
              {stage === 'importing' ? 'Importing...' : `Confirm Import (${importableCount} row${importableCount !== 1 ? 's' : ''})`}
            </button>
            <button className="btn-secondary" onClick={resetFile} disabled={stage === 'importing'}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}

export { ProductsPage, ProductDetailPage, ProductImportPage, RateCardsPage, RateCardImportPage };
