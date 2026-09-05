import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { productImportAPI } from '../../../utils/api';
import Card from '../../../components/common/Card';
import Alert from '../../../components/common/Alert';

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

export default ProductImportPage;
