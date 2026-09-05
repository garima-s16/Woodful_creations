import React, { useState } from 'react';
import { purchaseImportAPI } from '../../../utils/api';
import Card from '../../../components/common/Card';
import Alert from '../../../components/common/Alert';
import { formatCurrency } from '../../../utils/format';

function PurchaseImportPage() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({}); // row_number -> true if user opted out
  const [createDecisions, setCreateDecisions] = useState({}); // row_number -> bool, for new-material rows
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [downloadingErrors, setDownloadingErrors] = useState(false);

  const handleFileChange = (e) => {
    setFile(e.target.files[0] || null);
    setPreview(null);
    setResult(null);
    setError('');
  };

  const handlePreview = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    try {
      const res = await purchaseImportAPI.preview(file);
      setPreview(res.data);
      // Default: include every error-free row; default new materials to "create"
      const decisions = {};
      res.data.rows.forEach((r) => { if (r.is_new_material) decisions[r.row_number] = true; });
      setCreateDecisions(decisions);
      setExcludedRows({});
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not read this file. Make sure you used the downloaded template.');
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!preview) return;
    setLoading(true);
    setError('');
    try {
      const rowsToCommit = preview.rows
        .filter((r) => r.errors.length === 0 && !excludedRows[r.row_number])
        .map((r) => ({
          material_name: r.material_name, specification: r.specification,
          matched_material_id: r.matched_material_id, matched_supplier_id: r.matched_supplier_id,
          quantity: r.quantity, unit: r.unit, rate: r.rate, gst_percent: r.gst_percent || '0',
          invoice_date: r.invoice_date, remarks: r.remarks,
          create_new_material: r.is_new_material ? !!createDecisions[r.row_number] : false,
        }))
        .filter((r) => r.matched_material_id || r.create_new_material);

      const res = await purchaseImportAPI.commit(rowsToCommit);
      setResult(res.data);
      setPreview(null);
      setFile(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  const downloadErrorReport = async () => {
    if (!file) return;
    setDownloadingErrors(true);
    setError('');
    try {
      const res = await purchaseImportAPI.errorReport(file);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Purchase_Import_Errors.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not generate the error report. Please try again.');
    } finally {
      setDownloadingErrors(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Import Purchases from Excel</h1>
          <p className="page-summary">
            Download the template, fill in one row per material purchased, then upload it here for review
            before anything is saved.
          </p>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {result && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>Import Complete</h3>
            <p>
              {result.created_purchases} purchase{result.created_purchases !== 1 ? 's' : ''} created
              {result.created_materials > 0 && `, ${result.created_materials} new material${result.created_materials !== 1 ? 's' : ''} added`}.
            </p>
            {result.error && <Alert type="warning" message={result.error} />}
          </div>
        </Card>
      )}

      {!preview && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={purchaseImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
                Download Template
              </a>
            </p>
            <div style={{ marginTop: 16 }}>
              <input type="file" accept=".xlsx" onChange={handleFileChange} />
            </div>
            <button className="btn-primary" style={{ marginTop: 16 }} onClick={handlePreview} disabled={!file || loading}>
              {loading ? 'Reading file...' : 'Preview Import'}
            </button>
          </div>
        </Card>
      )}

      {preview && (
        <>
          <Card>
            <div className="card-body">
              <h3 style={{ marginTop: 0 }}>{preview.total_rows} rows detected</h3>
              <p>
                {preview.matched_rows} matched existing material &middot; {preview.new_material_rows} new material{preview.new_material_rows !== 1 ? 's' : ''} detected &middot;{' '}
                {preview.error_rows} row{preview.error_rows !== 1 ? 's' : ''} with errors
                {preview.error_rows > 0 ? ' (won\'t be imported)' : ''}.
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
                <th></th><th>Material</th><th>Qty</th><th>Unit</th><th>Supplier</th>
                <th>Rate</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r) => (
                <tr key={r.row_number} style={{ opacity: excludedRows[r.row_number] ? 0.5 : 1 }}>
                  <td>
                    {r.errors.length === 0 && (
                      <input
                        type="checkbox" checked={!excludedRows[r.row_number]}
                        onChange={(e) => setExcludedRows((prev) => ({ ...prev, [r.row_number]: !e.target.checked }))}
                      />
                    )}
                  </td>
                  <td>{r.material_name}</td>
                  <td>{r.quantity != null ? Number(r.quantity) : '-'}</td>
                  <td>{r.unit}</td>
                  <td>{r.supplier_name}</td>
                  <td>{r.rate != null ? formatCurrency(r.rate) : '-'}</td>
                  <td>
                    {r.errors.length > 0 ? (
                      <span className="status-badge status-danger">{r.errors.join('; ')}</span>
                    ) : r.is_new_material ? (
                      <label style={{ fontSize: '0.8rem' }}>
                        <input
                          type="checkbox" checked={!!createDecisions[r.row_number]}
                          onChange={(e) => setCreateDecisions((prev) => ({ ...prev, [r.row_number]: e.target.checked }))}
                        />{' '}
                        New - Create Material
                      </label>
                    ) : (
                      <span className="status-badge status-ok">Matched</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
            <button className="btn-primary" onClick={handleCommit} disabled={loading}>
              {loading ? 'Importing...' : 'Confirm Import'}
            </button>
            <button className="btn-secondary" onClick={() => { setPreview(null); setFile(null); }}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}

export default PurchaseImportPage;
