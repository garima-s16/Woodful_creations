// Material pages: detail, Excel import, locations, and the material
// attributes editor. Combines the former MaterialDetailPage.jsx,
// MaterialImportPage.jsx, LocationsPage.jsx, and
// components/MaterialAttributesEditor.jsx.
import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { issuesAPI, locationsAPI, materialCategoriesAPI, materialImportAPI, materialsAPI, purchasesAPI, stockAPI, supplierMaterialsAPI } from '../../../utils/api';
import { addToCart } from '../../../redux/slices';
import { Alert, Card, Form, Modal, Table } from '../../../components/common/UI';
import { formatCurrency, statusClass } from '../../../utils/utils';
import '../../../styles/modules.css';

// --- MaterialDetailPage.jsx ---
const TABS = ['Overview', 'Suppliers', 'Purchases', 'Issues'];

function MaterialDetailPage() {
  const { materialId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [material, setMaterial] = useState(null);
  const [purchases, setPurchases] = useState([]);
  const [issues, setIssues] = useState([]);
  const [supplierLinks, setSupplierLinks] = useState([]);
  const VALID_TABS = ['Overview', 'Suppliers', 'Purchases', 'Issues'];
  const requestedTab = searchParams.get('tab');
  const [tab, setTab] = useState(VALID_TABS.includes(requestedTab) ? requestedTab : 'Overview');
  const [addedToCart, setAddedToCart] = useState(false);
  const [allLocations, setAllLocations] = useState([]);
  const [locationStock, setLocationStock] = useState(null);
  const [showTransfer, setShowTransfer] = useState(false);
  const [showAdjust, setShowAdjust] = useState(false);
  const [stockLoading, setStockLoading] = useState(false);
  const [stockError, setStockError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [purchasesError, setPurchasesError] = useState(false);
  const [issuesError, setIssuesError] = useState(false);
  const [supplierLinksError, setSupplierLinksError] = useState(false);

  const load = useCallback(() => {
    setLoadError('');
    setPurchasesError(false);
    setIssuesError(false);
    setSupplierLinksError(false);
    materialsAPI.get(materialId).then((res) => setMaterial(res.data)).catch(() => setLoadError('Unable to load this material.'));
    purchasesAPI.list({ material_id: materialId }).then((res) => setPurchases(res.data)).catch(() => { setPurchases([]); setPurchasesError(true); });
    issuesAPI.list({ material_id: materialId }).then((res) => setIssues(res.data)).catch(() => { setIssues([]); setIssuesError(true); });
    supplierMaterialsAPI.byMaterial(materialId).then((res) => setSupplierLinks(res.data)).catch(() => { setSupplierLinks([]); setSupplierLinksError(true); });
    stockAPI.locationStock(materialId).then((res) => setLocationStock(res.data)).catch(() => setLocationStock(null));
  }, [materialId]);

  useEffect(load, [load]);

  // Locations is reference data for the transfer-to-location form,
  // not specific to this material - fetched once per page visit
  // rather than on every load() call.
  useEffect(() => {
    locationsAPI.list().then((res) => setAllLocations(res.data)).catch(() => setAllLocations([]));
  }, []);

  const handleTransfer = async (formData) => {
    setStockLoading(true);
    setStockError('');
    try {
      await stockAPI.transfer({
        material_id: Number(materialId), quantity: Number(formData.quantity),
        to_location_id: Number(formData.to_location_id),
        from_location_id: formData.from_location_id ? Number(formData.from_location_id) : undefined,
        remarks: formData.remarks,
      });
      setShowTransfer(false);
      load();
    } catch (err) {
      setStockError(err.response?.data?.detail || 'Transfer failed');
    } finally {
      setStockLoading(false);
    }
  };

  const handleAdjust = async (formData) => {
    setStockLoading(true);
    setStockError('');
    try {
      const isReturn = formData.adjustment_type === 'Return from Issue';
      const delta = isReturn
        ? Math.abs(Number(formData.quantity))
        : (formData.direction === 'decrease' ? -Math.abs(Number(formData.quantity)) : Math.abs(Number(formData.quantity)));
      await stockAPI.adjust({
        material_id: Number(materialId), adjustment_type: formData.adjustment_type,
        quantity_delta: delta, reason: formData.reason,
        related_issue_id: isReturn ? Number(formData.related_issue_id) : undefined,
        location_id: formData.location_id ? Number(formData.location_id) : undefined,
      });
      setShowAdjust(false);
      load();
    } catch (err) {
      setStockError(err.response?.data?.detail || 'Adjustment failed');
    } finally {
      setStockLoading(false);
    }
  };

  const handleAddToCart = () => {
    const preferred = supplierLinks.find((s) => s.is_preferred) || supplierLinks[0];
    dispatch(addToCart({
      materialId: material.id, name: material.name, unit: material.unit,
      rate: preferred?.supplier_price || material.average_rate,
      supplierId: preferred?.supplier_id, supplierName: preferred?.supplier_name,
      quantity: 1, currentStock: material.current_stock,
    }));
    setAddedToCart(true);
    setTimeout(() => setAddedToCart(false), 1500);
  };

  if (loadError) return <div className="page"><Alert type="error" message={loadError} /><button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button></div>;
  if (!material) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/materials" className="btn-link">&larr; Back to Materials</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{material.name}</h1>
          <div className="detail-subtitle">
            {material.material_code} &middot; {material.category || 'Uncategorized'}
            {' '}<span className={`status-badge ${statusClass(material.stock_status)}`}>{material.stock_status}</span>
            {material.business_id && <span className="business-id-badge">{material.business_id}</span>}
          </div>
        </div>
        <div className="detail-header-actions">
          {isPrivileged && <button className="btn-secondary" onClick={() => setShowTransfer(true)}>Transfer</button>}
          {isPrivileged && <button className="btn-secondary" onClick={() => setShowAdjust(true)}>Adjust Stock</button>}
          <button className="btn-primary" onClick={handleAddToCart}>
            {addedToCart ? 'Added!' : 'Add to Purchase Cart'}
          </button>
        </div>
      </div>

      {stockError && <Alert type="error" message={stockError} onClose={() => setStockError('')} />}

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Available Stock</div><h3>{material.current_stock} {material.unit}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Reorder Level</div><h3>{material.minimum_stock} {material.unit}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Average Rate</div><h3>{material.average_rate != null ? formatCurrency(material.average_rate) : 'Restricted'}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Stock Value</div><h3>{material.stock_value != null ? formatCurrency(material.stock_value) : 'Restricted'}</h3></div></Card>
      </div>

      <div className="tab-bar">
        {(isPrivileged ? TABS : TABS.filter((t) => t !== 'Purchases')).map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && (
        <Card title="Material Details">
          <div className="card-body">
            <div className="detail-meta">
              <div className="detail-meta-item"><span className="detail-meta-label">Brand/Grade</span><span className="detail-meta-value">{material.brand_grade || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Thickness/Size</span><span className="detail-meta-value">{material.thickness_size || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Opening Stock</span><span className="detail-meta-value">{material.opening_stock} {material.unit}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Total Purchased</span><span className="detail-meta-value">{material.total_purchased} {material.unit}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Total Issued</span><span className="detail-meta-value">{material.total_issued} {material.unit}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Location</span><span className="detail-meta-value">{material.location || '-'}</span></div>
            </div>
          </div>
        </Card>
      )}

      {tab === 'Overview' && locationStock?.locations?.length > 0 && (
        <Card title="Stock by Location">
          <div className="card-body">
            <Table
              columns={[
                { key: 'location_name', label: 'Location' },
                { key: 'quantity', label: 'Quantity', render: (v) => `${v} ${material.unit}` },
              ]}
              data={[...locationStock.locations, { location_id: 'total', location_name: 'Total', quantity: locationStock.total }]}
            />
          </div>
        </Card>
      )}

      {tab === 'Overview' && material.attribute_values?.length > 0 && (
        <Card title="Specifications">
          <div className="card-body">
            <div className="detail-meta">
              {material.attribute_values.map((attr) => (
                <div className="detail-meta-item" key={attr.id}>
                  <span className="detail-meta-label">{attr.attribute_name}</span>
                  <span className="detail-meta-value">{attr.display_value}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      {tab === 'Suppliers' && (
        supplierLinks.length === 0 ? (
          <Card><div className="card-body" style={{ color: 'var(--text-secondary)' }}>
            No suppliers linked to this material yet.
          </div></Card>
        ) : (
          <Table
            columns={[
              { key: 'supplier_name', label: 'Supplier' },
              { key: 'supplier_price', label: 'Price', render: (v) => v ? formatCurrency(v) : (isPrivileged ? '-' : 'Restricted') },
              { key: 'last_purchase_price', label: 'Last Purchase Price', render: (v) => v ? formatCurrency(v) : (isPrivileged ? '-' : 'Restricted') },
              { key: 'moq', label: 'MOQ', render: (v) => v || '-' },
              { key: 'lead_time_days', label: 'Lead Time', render: (v) => v ? `${v} days` : '-' },
              { key: 'is_preferred', label: 'Preferred', render: (v) => v ? <span className="status-badge status-ok">Preferred</span> : '' },
            ]}
            data={supplierLinks}
            error={supplierLinksError}
            onRetry={load}
            emptyMessage="No suppliers linked to this material yet."
          />
        )
      )}

      {tab === 'Purchases' && isPrivileged && (
        <Table
          columns={[
            { key: 'purchase_code', label: 'Purchase' },
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'quantity', label: 'Quantity', align: 'right' }, { key: 'rate', label: 'Rate', render: formatCurrency, align: 'right' },
            { key: 'invoice_total', label: 'Invoice Total', render: formatCurrency, align: 'right' },
            { key: 'payment_status', label: 'Payment Status' },
          ]}
          data={purchases}
          error={purchasesError}
          onRetry={load}
          emptyMessage="No purchase history for this material yet."
        />
      )}
      {tab === 'Purchases' && !isPrivileged && (
        <p className="page-summary">Purchase history is restricted to master accounts.</p>
      )}

      {tab === 'Issues' && (
        <Table
          columns={[
            { key: 'issue_code', label: 'Issue' },
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'quantity_issued', label: 'Quantity' }, { key: 'issued_to', label: 'Issued To' },
            { key: 'department', label: 'Department' },
          ]}
          data={issues}
          error={issuesError}
          onRetry={load}
          emptyMessage="No issue history for this material yet."
        />
      )}

      <Modal isOpen={showTransfer} title={`Transfer ${material.name}`} onClose={() => setShowTransfer(false)}>
        <p style={{ marginTop: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          Current stock: {material.current_stock} {material.unit} at {material.location || 'no location set'}.
        </p>
        <Form
          fields={[
            { name: 'to_location_id', label: 'Transfer To', type: 'select', required: true, options: allLocations.map((l) => ({ value: l.id, label: l.full_path })) },
            { name: 'from_location_id', label: 'Transfer From', type: 'select',
              options: allLocations.map((l) => ({ value: l.id, label: l.full_path })),
              placeholder: material.location || 'Primary location' },
            { name: 'quantity', label: `Quantity (${material.unit})`, type: 'number', required: true },
            { name: 'remarks', label: 'Remarks', type: 'textarea' },
          ]}
          onSubmit={handleTransfer} loading={stockLoading} submitText="Confirm Transfer"
        />
      </Modal>

      <Modal isOpen={showAdjust} title={`Adjust Stock - ${material.name}`} onClose={() => setShowAdjust(false)}>
        <p style={{ marginTop: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          Current stock: {material.current_stock} {material.unit}. Every adjustment is recorded with a reason.
        </p>
        <Form
          fields={[
            { name: 'adjustment_type', label: 'Type', type: 'select', required: true, options: [
              { value: 'Physical Count Increase', label: 'Physical Count Increase' },
              { value: 'Physical Count Decrease', label: 'Physical Count Decrease' },
              { value: 'Damage', label: 'Damage' },
              { value: 'Wastage', label: 'Wastage' },
              { value: 'Theft/Loss', label: 'Theft/Loss' },
              { value: 'Correction', label: 'Correction' },
              { value: 'Return from Issue', label: 'Return from Issue' },
            ] },
            { name: 'related_issue_id', label: 'Issue Being Returned Against', type: 'select',
              visibleIf: (fd) => fd.adjustment_type === 'Return from Issue',
              required: true,
              options: issues.map((i) => ({
                value: i.id, label: `${i.issue_code} - ${i.quantity_issued} ${material.unit} (${new Date(i.date).toLocaleDateString()})`,
              })) },
            { name: 'direction', label: 'Direction', type: 'select', required: true,
              visibleIf: (fd) => fd.adjustment_type !== 'Return from Issue',
              options: [
                { value: 'increase', label: 'Increase stock' }, { value: 'decrease', label: 'Decrease stock' },
              ] },
            { name: 'quantity', label: `Quantity (${material.unit})`, type: 'number', required: true },
            { name: 'location_id', label: 'Location', type: 'select',
              options: allLocations.map((l) => ({ value: l.id, label: l.full_path })),
              placeholder: material.location || 'Primary location' },
            { name: 'reason', label: 'Reason', type: 'textarea', required: true },
          ]}
          onSubmit={handleAdjust} loading={stockLoading} submitText="Confirm Adjustment"
        />
      </Modal>
    </div>
  );
}

// --- MaterialImportPage.jsx ---
function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function rowStatus(row, resolution) {
  if (row.errors.length > 0) return { label: 'ERROR', className: 'status-danger' };
  if (row.is_duplicate) return { label: 'EXISTING', className: 'status-neutral' };
  if (row.possible_match_material_id) {
    if (resolution === 'use_existing') return { label: 'USING EXISTING', className: 'status-neutral' };
    if (resolution === 'create_new') return { label: 'NEW (CONFIRMED)', className: 'status-gold' };
    return { label: 'POSSIBLE MATCH', className: 'status-warning' };
  }
  return { label: 'NEW', className: 'status-gold' };
}

function MaterialImportPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({});
  // row_number -> 'use_existing' | 'create_new', only meaningful for
  // rows with a possible_match_material_id (a fuzzy/uncertain match,
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
      const res = await materialImportAPI.preview(file);
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
          name: r.name, category: r.category, subcategory_id: r.subcategory_id,
          brand_grade: r.brand_grade, thickness_size: r.thickness_size, unit: r.unit || 'Nos',
          supplier_id: r.supplier_id, opening_stock: r.opening_stock || 0, minimum_stock: r.minimum_stock || 0,
          location_id: r.location_id, is_active: r.is_active,
          matched_material_id: r.is_duplicate
            ? r.matched_material_id
            : (r.possible_match_material_id && resolutions[r.row_number] === 'use_existing'
                ? r.possible_match_material_id : null),
          skip: !!excludedRows[r.row_number],
        }));
      const res = await materialImportAPI.commit(rowsToCommit);
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
      const res = await materialImportAPI.errorReport(file);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Material_Import_Errors.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not generate the error report. Please try again.');
    } finally {
      setDownloadingErrors(false);
    }
  };

  const importableCount = preview ? preview.rows.filter((r) => r.errors.length === 0 && !excludedRows[r.row_number]).length : 0;
  const unresolvedCount = preview
    ? preview.rows.filter((r) => r.errors.length === 0 && !excludedRows[r.row_number]
        && r.possible_match_material_id && !resolutions[r.row_number]).length
    : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Import Materials from Excel</h1>
          <p className="page-summary">
            Download the template, fill in one row per material, then upload it here for review before anything is saved.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => navigate('/materials')}>Back to Materials</button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {(stage === 'success' || stage === 'error') && result && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>{stage === 'error' ? 'Import Partially Complete' : 'Import Complete'}</h3>
            <div className="import-result-grid">
              <div><span className="import-result-number">{result.created_materials}</span><span className="import-result-label">New Materials</span></div>
              <div><span className="import-result-number">{result.matched_existing}</span><span className="import-result-label">Matched Existing</span></div>
              <div><span className="import-result-number">{result.skipped}</span><span className="import-result-label">Skipped</span></div>
            </div>
            {result.error && <Alert type="warning" message={result.error} />}
            <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
              <button className="btn-primary" onClick={() => navigate('/materials')}>View Imported Materials</button>
              <button className="btn-secondary" onClick={resetFile}>Import Another File</button>
            </div>
          </div>
        </Card>
      )}

      {(stage === 'empty' || stage === 'selected' || stage === 'validating') && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={materialImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
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
                {preview.new_rows} new material{preview.new_rows !== 1 ? 's' : ''} &middot;{' '}
                {preview.duplicate_rows} matching existing material{preview.duplicate_rows !== 1 ? 's' : ''} &middot;{' '}
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
                <th></th><th>Material Name</th><th>Category</th><th>Unit</th><th>Opening Stock</th><th>Status</th>
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
                    <td>{r.opening_stock != null ? r.opening_stock : '-'}</td>
                    <td>
                      <span className={`status-badge ${status.className}`}>{status.label}</span>
                      {r.errors.length > 0 && (
                        <div className="import-row-error">{r.errors.join('; ')}</div>
                      )}
                      {r.possible_match_material_id && !excludedRows[r.row_number] && (
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

// --- LocationsPage.jsx ---
function LocationNode({ node, onAddChild, isPrivileged }) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <li className="location-node">
      <div className="location-node-row">
        {hasChildren ? (
          <button className="location-node-toggle" onClick={() => setExpanded((e) => !e)} aria-label={expanded ? 'Collapse' : 'Expand'}>
            {expanded ? '\u2212' : '+'}
          </button>
        ) : <span className="location-node-toggle-spacer" />}
        <span className="location-node-name">{node.name}</span>
        {node.location_type && <span className="location-node-type">{node.location_type}</span>}
        {node.business_id && <span className="business-id-badge">{node.business_id}</span>}
        {isPrivileged && <button className="btn-link" onClick={() => onAddChild(node)}>+ Add here</button>}
      </div>
      {hasChildren && expanded && (
        <ul className="location-node-children">
          {node.children.map((child) => (
            <LocationNode key={child.id} node={child} onAddChild={onAddChild} isPrivileged={isPrivileged} />
          ))}
        </ul>
      )}
    </li>
  );
}

function LocationsPage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [tree, setTree] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [parentForNew, setParentForNew] = useState(null); // null = top-level (new Warehouse)
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    locationsAPI.tree().then((res) => setTree(res.data)).catch(() => setError('Unable to load locations.'));
  }, []);

  useEffect(load, [load]);

  const handleAddChild = (node) => {
    setParentForNew(node);
    setShowAdd(true);
  };

  const handleAddTopLevel = () => {
    setParentForNew(null);
    setShowAdd(true);
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await locationsAPI.create({
        name: formData.name, location_type: formData.location_type || null,
        parent_id: parentForNew ? parentForNew.id : null,
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create location');
    } finally {
      setLoading(false);
    }
  };

  const fields = [
    { name: 'name', label: 'Name', required: true, placeholder: parentForNew ? 'e.g. Rack A2' : 'e.g. Main Warehouse' },
    { name: 'location_type', label: 'Type (optional)', placeholder: 'Warehouse / Area / Rack / Bin' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Locations</h1>
          <p className="page-summary">
            Where materials are actually stored - a flexible tree (Warehouse &rarr; Area &rarr; Rack &rarr; Bin,
            or as many/few levels as your business needs). Create your own structure; nothing here is fixed.
          </p>
        </div>
        {isPrivileged && <button className="btn-primary" onClick={handleAddTopLevel}>+ New Top-Level Location</button>}
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <Card>
        {tree.length === 0 ? (
          <div className="card-body" style={{ color: 'var(--text-secondary)' }}>
            No locations yet. Create your first top-level location (e.g. a warehouse) to get started.
          </div>
        ) : (
          <ul className="location-tree-root">
            {tree.map((node) => (
              <LocationNode key={node.id} node={node} onAddChild={handleAddChild} isPrivileged={isPrivileged} />
            ))}
          </ul>
        )}
      </Card>

      <Modal
        isOpen={showAdd}
        title={parentForNew ? `New location under "${parentForNew.name}"` : 'New Top-Level Location'}
        onClose={() => { setShowAdd(false); setParentForNew(null); }}
      >
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Create Location" />
      </Modal>
    </div>
  );
}

// --- ../components/MaterialAttributesEditor.jsx ---
/* Category -> Subcategory -> dynamic attribute fields. Form.js can't
 * render fields that change based on another field's value within the
 * same form, so this is a dedicated component (same reason
 * LineItemEditor exists) - rendered alongside the static Form fields
 * (name, unit, stock settings), not replacing them. Reports
 * {subcategoryId, attributeValues} up to the parent on every change.
 *
 * initialSubcategoryId/initialAttributeValues let the same component
 * serve both create (blank) and edit (pre-populated with the
 * material's current specs) - passing neither behaves exactly as
 * before. initialAttributeValues is the material's real
 * attribute_values response shape (attribute_definition_id +
 * value_text/value_number), not a separately-invented input format. */
const MaterialAttributesEditor = forwardRef(function MaterialAttributesEditor(
  { onChange, initialSubcategoryId, initialAttributeValues }, ref
) {
  const [categories, setCategories] = useState([]);
  const [categoryId, setCategoryId] = useState('');
  const [subcategories, setSubcategories] = useState([]);
  const [subcategoryId, setSubcategoryId] = useState('');
  const [attributeDefs, setAttributeDefs] = useState([]);
  const [values, setValues] = useState({}); // attribute_definition_id -> raw string input

  // Selects a subcategory (and pre-fills its attribute values) given the
  // already-fetched category list. Shared by the initial-mount pre-fill
  // (editing an existing material) and applySuggestedSubcategory below
  // ("intelligent defaults", accepted by explicit user action)
  // so the two never drift into two different implementations of the
  // same lookup.
  const selectSubcategory = (targetSubcategoryId, categoriesList, prefillAttributeValues) => {
    for (const category of categoriesList) {
      const match = (category.subcategories || []).find((s) => s.id === targetSubcategoryId);
      if (match) {
        setCategoryId(String(category.id));
        setSubcategories(category.subcategories);
        setSubcategoryId(String(match.id));
        setAttributeDefs(match.attribute_definitions || []);
        const prefilled = {};
        const attributeValues = [];
        (prefillAttributeValues || []).forEach((v) => {
          const raw = v.value_number ?? v.value_text ?? '';
          prefilled[v.attribute_definition_id] = raw;
          attributeValues.push({
            attribute_definition_id: v.attribute_definition_id,
            value_number: v.value_number != null ? raw : undefined,
            value_text: v.value_number == null ? raw : undefined,
          });
        });
        setValues(prefilled);
        onChange({ subcategoryId: match.id, attributeValues });
        return true;
      }
    }
    return false;
  };

  useEffect(() => {
    materialCategoriesAPI.list().then((res) => {
      setCategories(res.data);
      if (!initialSubcategoryId) return;
      // Find which category owns this subcategory, so both selects and
      // the attribute fields can be pre-populated in one pass. The
      // parent's state must reflect these pre-populated values
      // immediately - otherwise saving the form without touching the
      // hierarchy fields would submit subcategoryId: null and silently
      // wipe the material's existing category/specs.
      selectSubcategory(initialSubcategoryId, res.data, initialAttributeValues);
    }).catch(() => setCategories([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useImperativeHandle(ref, () => ({
    // Applies a suggested subcategory (material-name
    // interpretation, e.g. typing "HDHMR 6mm"). Only ever called from an
    // explicit "Apply suggestion" click - never automatically - so it
    // can't fight a category/subcategory the user already chose
    // themselves. Selecting a subcategory clears attribute values the
    // same way the manual dropdown does (a different subcategory means
    // different attribute definitions), so there's nothing stale left
    // behind from a prior selection. Returns false if the suggested
    // subcategory can no longer be found (e.g. deleted meanwhile).
    applySuggestedSubcategory(targetSubcategoryId) {
      if (!targetSubcategoryId) return false;
      return selectSubcategory(targetSubcategoryId, categories, null);
    },
  }), [categories]);

  const handleCategoryChange = (e) => {
    const id = e.target.value;
    setCategoryId(id);
    setSubcategoryId('');
    setAttributeDefs([]);
    setValues({});
    const category = categories.find((c) => String(c.id) === id);
    setSubcategories(category?.subcategories || []);
    onChange({ subcategoryId: null, attributeValues: [] });
  };

  const handleSubcategoryChange = (e) => {
    const id = e.target.value;
    setSubcategoryId(id);
    setValues({});
    const subcategory = subcategories.find((s) => String(s.id) === id);
    const defs = subcategory?.attribute_definitions || [];
    setAttributeDefs(defs);
    onChange({ subcategoryId: id ? Number(id) : null, attributeValues: [] });
  };

  const handleValueChange = (attrId, rawValue, dataType) => {
    const nextValues = { ...values, [attrId]: rawValue };
    setValues(nextValues);
    const attributeValues = attributeDefs
      .filter((def) => nextValues[def.id])
      .map((def) => ({
        attribute_definition_id: def.id,
        value_number: def.data_type === 'number' ? nextValues[def.id] : undefined,
        value_text: def.data_type !== 'number' ? nextValues[def.id] : undefined,
      }));
    onChange({ subcategoryId: subcategoryId ? Number(subcategoryId) : null, attributeValues });
  };

  return (
    <div className="material-attributes-editor">
      <div className="material-attributes-row">
        <div className="form-group">
          <label>Category</label>
          <select className="form-input" value={categoryId} onChange={handleCategoryChange}>
            <option value="">Select category (optional)</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        {categoryId && (
          <div className="form-group">
            <label>Subcategory</label>
            <select className="form-input" value={subcategoryId} onChange={handleSubcategoryChange}>
              <option value="">Select subcategory</option>
              {subcategories.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        )}
      </div>

      {attributeDefs.length > 0 && (
        <div className="material-attributes-fields">
          <div className="material-attributes-label">Specifications</div>
          {attributeDefs.map((def) => (
            <div className="form-group" key={def.id}>
              <label>{def.name}{def.is_required && ' *'}{def.unit_label && ` (${def.unit_label})`}</label>
              {def.data_type === 'select' ? (
                <select className="form-input" value={values[def.id] || ''} onChange={(e) => handleValueChange(def.id, e.target.value, def.data_type)}>
                  <option value="">Select {def.name}</option>
                  {(def.select_options || '').split(',').map((opt) => opt.trim()).filter(Boolean).map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : (
                <input
                  type={def.data_type === 'number' ? 'number' : 'text'}
                  className="form-input"
                  value={values[def.id] || ''}
                  onChange={(e) => handleValueChange(def.id, e.target.value, def.data_type)}
                  placeholder={def.name}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

export { MaterialDetailPage, MaterialImportPage, LocationsPage, MaterialAttributesEditor };
