import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { estimateImportAPI } from '../../../utils/api';
import Card from '../../../components/common/Card';
import Alert from '../../../components/common/Alert';

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function headerStatus(h) {
  const itemErrors = h.items.some((it) => it.errors.length > 0);
  const hasItems = h.items.length > 0;
  if (h.errors.length > 0 || itemErrors || !hasItems) return { label: 'ERROR', className: 'status-danger' };
  if (!h.is_new_estimate) return { label: 'UPDATE EXISTING', className: 'status-neutral' };
  return { label: 'NEW', className: 'status-gold' };
}

function EstimateImportPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({});
  const [expandedRows, setExpandedRows] = useState({});
  const [stage, setStage] = useState('empty');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [downloadingErrors, setDownloadingErrors] = useState(false);
  const fileInputRef = useRef(null);

  const resetFile = () => {
    setFile(null);
    setPreview(null);
    setExcludedRows({});
    setExpandedRows({});
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
      const res = await estimateImportAPI.preview(file);
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
      const estimatesToCommit = preview.estimates
        .filter((h) => h.errors.length === 0 && h.items.length > 0 && !h.items.some((it) => it.errors.length > 0))
        .map((h) => ({
          matched_estimate_id: h.matched_estimate_id,
          client_id: h.matched_client_id,
          estimate_date: h.estimate_date,
          valid_until: h.valid_until,
          margin_percent: h.margin_percent,
          discount: h.discount || 0,
          tax_percent: h.tax_percent || 18,
          notes: h.notes,
          items: h.items.map((it) => ({
            product_id: it.product_id, description: it.description, category: it.category,
            quantity: it.quantity, unit: it.unit || 'Nos', rate: it.rate,
            discount_percent: it.discount_percent || 0, tax_percent: it.tax_percent,
          })),
          skip: !!excludedRows[h.row_number],
        }));
      const res = await estimateImportAPI.commit(estimatesToCommit);
      setResult(res.data);
      setPreview(null);
      setFile(null);
      setStage(res.data.error_count > 0 ? 'error' : 'success');
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
      const res = await estimateImportAPI.errorReport(file);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Estimate_Import_Errors.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not generate the error report. Please try again.');
    } finally {
      setDownloadingErrors(false);
    }
  };

  const importableCount = preview
    ? preview.estimates.filter((h) => h.errors.length === 0 && h.items.length > 0 && !h.items.some((it) => it.errors.length > 0) && !excludedRows[h.row_number]).length
    : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Import Estimates from Excel</h1>
          <p className="page-summary">
            Download the template (two sheets: Estimate Header and Estimate Items), fill it in, then upload it here for review before anything is saved.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => navigate('/estimates')}>Back to Estimates</button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {(stage === 'success' || stage === 'error') && result && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>{stage === 'error' ? 'Import Partially Complete' : 'Import Complete'}</h3>
            <div className="import-result-grid">
              <div><span className="import-result-number">{result.created_count}</span><span className="import-result-label">Created</span></div>
              <div><span className="import-result-number">{result.updated_count}</span><span className="import-result-label">Updated</span></div>
              <div><span className="import-result-number">{result.skipped_count}</span><span className="import-result-label">Skipped</span></div>
              <div><span className="import-result-number">{result.error_count}</span><span className="import-result-label">Errors</span></div>
            </div>
            {result.results.filter((r) => r.error).map((r, i) => (
              <Alert key={i} type="warning" message={r.error} onClose={() => {}} />
            ))}
            <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
              <button className="btn-primary" onClick={() => navigate('/estimates')}>View Estimates</button>
              <button className="btn-secondary" onClick={resetFile}>Import Another File</button>
            </div>
          </div>
        </Card>
      )}

      {(stage === 'empty' || stage === 'selected' || stage === 'validating') && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={estimateImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
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
              <h3 style={{ marginTop: 0 }}>{preview.total_estimates} estimate{preview.total_estimates !== 1 ? 's' : ''} detected</h3>
              <p>
                {preview.new_estimates} new &middot; {preview.existing_estimates} matching existing estimates &middot;{' '}
                {preview.error_estimates} rejected{preview.error_estimates > 0 ? ' (won\u2019t be imported)' : ''}.
              </p>
              {preview.error_estimates > 0 && (
                <button className="btn-link" onClick={downloadErrorReport} disabled={downloadingErrors}>
                  {downloadingErrors ? 'Preparing report...' : 'Download Error Report'}
                </button>
              )}
              {preview.orphan_item_rows.length > 0 && (
                <Alert type="warning" onClose={() => {}} message={
                  `${preview.orphan_item_rows.length} row(s) on the Estimate Items sheet reference an Estimate Row # that doesn't match any header row and will be ignored.`
                } />
              )}
            </div>
          </Card>

          <table className="data-table">
            <thead>
              <tr>
                <th></th><th></th><th>Client</th><th>Valid Until</th><th>Items</th><th>Total</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.estimates.map((h) => {
                const status = headerStatus(h);
                const canExclude = status.label !== 'ERROR';
                const isExpanded = !!expandedRows[h.row_number];
                return (
                  <React.Fragment key={h.row_number}>
                    <tr style={{ opacity: excludedRows[h.row_number] ? 0.5 : 1 }}>
                      <td>
                        {canExclude && (
                          <input
                            type="checkbox" checked={!excludedRows[h.row_number]}
                            onChange={(e) => setExcludedRows((prev) => ({ ...prev, [h.row_number]: !e.target.checked }))}
                          />
                        )}
                      </td>
                      <td>
                        <button className="btn-link" onClick={() => setExpandedRows((prev) => ({ ...prev, [h.row_number]: !prev[h.row_number] }))}>
                          {isExpanded ? '\u25be' : '\u25b8'} {h.matched_estimate_code || `Row ${h.row_number}`}
                        </button>
                      </td>
                      <td>{h.client_name || '-'}{h.matched_client_id ? '' : ' (not found)'}</td>
                      <td>{h.valid_until ? new Date(h.valid_until).toLocaleDateString() : '-'}</td>
                      <td>{h.items.length}</td>
                      <td>{h.computed_total != null ? `\u20b9${Number(h.computed_total).toLocaleString('en-IN')}` : '-'}</td>
                      <td>
                        <span className={`status-badge ${status.className}`}>{status.label}</span>
                        {h.errors.length > 0 && <div className="import-row-error">{h.errors.join('; ')}</div>}
                      </td>
                    </tr>
                    {isExpanded && h.items.map((it) => (
                      <tr key={`${h.row_number}-${it.row_number}`} className="import-nested-row">
                        <td></td>
                        <td colSpan={2} style={{ paddingLeft: 32 }}>{it.description || '-'} {it.product_code ? `(${it.product_code})` : ''}</td>
                        <td>{it.quantity != null ? `${it.quantity} ${it.unit || ''}` : '-'}</td>
                        <td>{it.rate != null ? `\u20b9${Number(it.rate).toLocaleString('en-IN')}` : '-'}</td>
                        <td>{it.amount != null ? `\u20b9${Number(it.amount).toLocaleString('en-IN')}` : '-'}</td>
                        <td>{it.errors.length > 0 && <div className="import-row-error">{it.errors.join('; ')}</div>}</td>
                      </tr>
                    ))}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>

          <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="btn-primary" onClick={handleImport} disabled={stage === 'importing' || importableCount === 0}>
              {stage === 'importing' ? 'Importing...' : `Confirm Import (${importableCount} estimate${importableCount !== 1 ? 's' : ''})`}
            </button>
            <button className="btn-secondary" onClick={resetFile} disabled={stage === 'importing'}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}

export default EstimateImportPage;
