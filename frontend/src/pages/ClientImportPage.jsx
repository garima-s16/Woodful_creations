import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientImportAPI } from '../utils/api';
import Card from '../components/common/Card';
import Alert from '../components/common/Alert';

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function rowStatus(row) {
  if (row.errors.length > 0) return { label: 'ERROR', className: 'status-danger' };
  if (row.is_duplicate) return { label: 'EXISTING CLIENT', className: 'status-info' };
  return { label: 'NEW', className: 'status-gold' };
}

function ClientImportPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [lastUploadedFile, setLastUploadedFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({}); // row_number -> true if user opted out
  const [stage, setStage] = useState('empty'); // empty | selected | validating | preview | importing | success | error
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  const resetFile = () => {
    setFile(null);
    setPreview(null);
    setExcludedRows({});
    setLastUploadedFile(null);
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
      const res = await clientImportAPI.preview(file);
      setPreview(res.data);
      setLastUploadedFile(file);
      // Every error-free, non-matched row is included by default;
      // existing-client matches are always reused (never excludable -
      // excluding one would just mean "don't reuse it", but there's no
      // create-a-duplicate-anyway option per the Client Recognition rule)
      // and error rows can never be included until fixed and re-uploaded.
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
          name: r.name, contact_person: r.contact_person, phone: r.phone,
          alternate_phone: r.alternate_phone, email: r.email, address: r.address,
          site_address: r.site_address, city: r.city, gstin: r.gstin,
          lead_source: r.lead_source, remarks: r.remarks,
          matched_client_id: r.matched_client_id,
          skip: !!excludedRows[r.row_number],
        }));
      const res = await clientImportAPI.commit(rowsToCommit);
      setResult(res.data);
      setPreview(null);
      setFile(null);
      setStage(res.data.error ? 'error' : 'success');
    } catch (err) {
      setError(err.response?.data?.detail || 'Import failed. Please try again.');
      setStage('preview');
    }
  };

  const [downloadingErrors, setDownloadingErrors] = useState(false);
  const downloadErrorReport = async () => {
    if (!lastUploadedFile) return;
    setDownloadingErrors(true);
    setError('');
    try {
      const res = await clientImportAPI.errorReport(lastUploadedFile);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Client_Import_Errors.xlsx';
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
          <h1>Import Clients from Excel</h1>
          <p className="page-summary">
            Download the template, fill in one row per client, then upload it here for review before anything is saved.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => navigate('/clients')}>Back to Clients</button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {(stage === 'success' || stage === 'error') && result && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>{stage === 'error' ? 'Import Partially Complete' : 'Import Complete'}</h3>
            <div className="import-result-grid">
              <div><span className="import-result-number">{result.created_clients}</span><span className="import-result-label">New Clients</span></div>
              <div><span className="import-result-number">{result.matched_existing}</span><span className="import-result-label">Existing Clients Matched</span></div>
              <div><span className="import-result-number">{result.skipped}</span><span className="import-result-label">Skipped</span></div>
            </div>
            {result.error && <Alert type="warning" message={result.error} />}
            <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
              <button className="btn-primary" onClick={() => navigate('/clients')}>View Imported Clients</button>
              <button className="btn-secondary" onClick={resetFile}>Import Another File</button>
            </div>
          </div>
        </Card>
      )}

      {(stage === 'empty' || stage === 'selected' || stage === 'validating') && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={clientImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
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
                {preview.new_rows} new client{preview.new_rows !== 1 ? 's' : ''} &middot;{' '}
                {preview.duplicate_rows} existing client{preview.duplicate_rows !== 1 ? 's' : ''} matched &middot;{' '}
                {preview.error_rows} row{preview.error_rows !== 1 ? 's' : ''} rejected
                {preview.error_rows > 0 ? ' (won\u2019t be imported)' : ''}.
              </p>
              {errorCount > 0 && (
                <button className="btn-link" onClick={downloadErrorReport} disabled={downloadingErrors}>
                  {downloadingErrors ? 'Preparing report...' : 'Download Error Report'}
                </button>
              )}
            </div>
          </Card>

          <table className="data-table">
            <thead>
              <tr>
                <th></th><th>Client Name</th><th>Phone</th><th>Email</th><th>City</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r) => {
                const status = rowStatus(r);
                const canExclude = r.errors.length === 0 && !r.is_duplicate;
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
                    <td>{r.phone || '-'}</td>
                    <td>{r.email || '-'}</td>
                    <td>{r.city || '-'}</td>
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

export default ClientImportPage;
