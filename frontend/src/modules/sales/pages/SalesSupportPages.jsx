// Sales support pages: payments, estimate/order Excel import, and
// the line-item editor. Combines the former PaymentsPage.jsx,
// EstimateImportPage.jsx, OrderImportPage.jsx, and
// components/LineItemEditor.jsx.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { clientProductRateAPI, estimateImportAPI, orderImportAPI, ordersAPI, paymentDocumentsAPI, paymentsAPI, productsAPI, reportsAPI } from '../../../utils/api';
import { Alert, Card, Form, Modal, SendEmailModal, Table } from '../../../components/common/UI';
import { DocumentsPanel } from '../../../components/Assistant';
import { formatCurrency, today } from '../../../utils/utils';
import { createPortal } from 'react-dom';
import '../../../styles/modules.css';

// --- PaymentsPage.jsx ---
function PaymentsPage() {
  const { user } = useSelector((state) => state.auth);
  const isTrueMaster = user?.role === 'master';
  const isPrivileged = user?.role === 'master';
  const [payments, setPayments] = useState([]);
  const [orders, setOrders] = useState([]);
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingPayment, setEditingPayment] = useState(null);
  const [sendReceiptFor, setSendReceiptFor] = useState(null);
  const [documentsFor, setDocumentsFor] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    paymentsAPI.list().then((res) => setPayments(res.data)).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view payments.' : 'Unable to load payments. Please try again.');
    }).finally(() => setPageLoading(false));
    ordersAPI.list().then((res) => setOrders(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await paymentsAPI.create({
        ...formData,
        order_id: Number(formData.order_id),
        date: new Date(formData.date).toISOString(),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record payment');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await paymentsAPI.update(editingPayment.id, {
        payment_type: formData.payment_type, payment_mode: formData.payment_mode,
        amount: formData.amount, reference_number: formData.reference_number,
        received_by: formData.received_by, remarks: formData.remarks,
      });
      setEditingPayment(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update payment');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'business_id', label: 'Receipt ID', render: (v) => v || '-' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'order_id', label: 'Order', render: (v) => orders.find((o) => o.id === v)?.order_code || v },
    { key: 'payment_type', label: 'Payment Type' }, { key: 'payment_mode', label: 'Payment Mode' },
    { key: 'amount', label: 'Amount', render: (v) => formatCurrency(v) },
    { key: 'reference_number', label: 'Reference No.' }, { key: 'received_by', label: 'Received By' },
    {
      key: 'invoice_action', label: '', render: (v, row) => (
        <a href={reportsAPI.downloadUrl(`orders/${row.order_id}/invoice.pdf`)} target="_blank" rel="noreferrer">Invoice</a>
      ),
    },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isTrueMaster && <button className="btn-link" onClick={() => setEditingPayment(row)}>Edit</button>
      ),
    },
    {
      key: 'send_receipt_action', label: '', render: (v, row) => (
        isTrueMaster && <button className="btn-link" onClick={() => setSendReceiptFor(row)}>Send Receipt</button>
      ),
    },
    {
      key: 'documents_action', label: '', render: (v, row) => (
        isTrueMaster && <button className="btn-link" onClick={() => setDocumentsFor(row)}>Documents</button>
      ),
    },
  ];

  // Reference-number field is context-aware per payment mode: Cash is
  // system-generated (never user-typed, see backend OrderService), while
  // other modes ask for whatever real-world reference identifies that
  // transaction - the label changes so the user isn't guessing what to enter.
  const referenceFieldFor = (mode) => {
    switch (mode) {
      case 'UPI': return { label: 'UPI Transaction ID', placeholder: 'e.g. 402812345678' };
      case 'Bank Transfer': return { label: 'Bank Reference / UTR Number', placeholder: 'e.g. UTR1234567890' };
      case 'Cheque': return { label: 'Cheque Number', placeholder: 'e.g. 000123' };
      case 'Card': return { label: 'Transaction ID', placeholder: 'e.g. auth code / last 4 digits' };
      default: return { label: 'Reference Number', placeholder: '' };
    }
  };

  const createFields = [
    { name: 'order_id', label: 'Order', type: 'select', required: true, section: 'Client & Order', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'date', label: 'Date', type: 'date', required: true, section: 'Client & Order' },
    { name: 'payment_type', label: 'Payment Type', type: 'select', required: true, section: 'Payment Details', options: [
      { value: 'Advance', label: 'Advance' }, { value: 'Progress Payment', label: 'Progress Payment' }, { value: 'Internal', label: 'Internal' },
    ] },
    { name: 'payment_mode', label: 'Payment Mode', type: 'select', required: true, section: 'Payment Details', options: [
      { value: 'Cash', label: 'Cash' }, { value: 'UPI', label: 'UPI' }, { value: 'Bank Transfer', label: 'Bank Transfer' },
      { value: 'Cheque', label: 'Cheque' }, { value: 'Card', label: 'Card' }, { value: 'Other', label: 'Other' },
    ] },
    { name: 'amount', label: 'Amount', type: 'number', required: true, section: 'Payment Details' },
    {
      // Cash: hidden entirely - the backend generates CASH-YYYYMMDD-001
      // automatically, so there's nothing for the user to type.
      name: 'cash_note', type: 'computed', section: 'Reference',
      label: 'Reference Number',
      hint: 'Generated automatically for cash payments (e.g. CASH-20260812-001) - you do not need to enter one.',
      compute: () => 'Auto-generated on save',
      visibleIf: (fd) => fd.payment_mode === 'Cash',
    },
    {
      name: 'reference_number', section: 'Reference',
      getLabel: (fd) => referenceFieldFor(fd.payment_mode).label,
      visibleIf: (fd) => fd.payment_mode && fd.payment_mode !== 'Cash',
    },
    { name: 'received_by', label: 'Received By', section: 'Reference' },
  ];

  const editFields = createFields
    .filter((f) => !['receipt_code', 'date', 'order_id'].includes(f.name))
    .map(({ section, ...f }) => f);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Payments</h1>
          <p className="page-summary">Record and review payments received against orders.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('payments.xlsx')} target="_blank" rel="noreferrer">Export</a>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Record Payment</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={payments} loading={pageLoading} error={loadError} onRetry={load} emptyMessage="No payments recorded yet." />
      <Modal isOpen={showAdd} title="Record Payment" onClose={() => setShowAdd(false)}>
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Record Payment"
          initialValues={{ date: today(), received_by: user?.full_name || user?.username || '' }} />
      </Modal>
      <Modal isOpen={!!editingPayment} title={`Edit ${editingPayment?.receipt_code || ''}`} onClose={() => setEditingPayment(null)}>
        {editingPayment && (
          <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingPayment} />
        )}
      </Modal>
      <SendEmailModal
        isOpen={!!sendReceiptFor}
        title={`Send Receipt - ${sendReceiptFor?.business_id || ''}`}
        previewFn={() => paymentsAPI.emailPreview(sendReceiptFor.id)}
        sendFn={(data) => paymentsAPI.sendEmail(sendReceiptFor.id, data)}
        onClose={() => setSendReceiptFor(null)}
      />
      <Modal isOpen={!!documentsFor} title={`Documents - ${documentsFor?.business_id || ''}`} onClose={() => setDocumentsFor(null)}>
        {documentsFor && (
          <DocumentsPanel title="" api={{
            list: () => paymentDocumentsAPI.list(documentsFor.id),
            upload: (file, description) => paymentDocumentsAPI.upload(documentsFor.id, file, description),
            downloadUrl: (documentId) => paymentDocumentsAPI.downloadUrl(documentsFor.id, documentId),
            remove: (documentId) => paymentDocumentsAPI.remove(documentsFor.id, documentId),
          }} canUpload={isTrueMaster} />
        )}
      </Modal>
    </div>
  );
}

// --- EstimateImportPage.jsx ---
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

          <div className="table-container">
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
          </div>

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

// --- OrderImportPage.jsx ---
function formatFileSizeOrder(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function headerStatusOrder(h) {
  const itemErrors = h.items.some((it) => it.errors.length > 0);
  const hasItems = h.items.length > 0 || h.matched_estimate_id;
  if (h.errors.length > 0 || itemErrors || !hasItems) return { label: 'ERROR', className: 'status-danger' };
  if (!h.is_new_order) return { label: 'UPDATE EXISTING', className: 'status-neutral' };
  return { label: 'NEW', className: 'status-gold' };
}

function OrderImportPage() {
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
      const res = await orderImportAPI.preview(file);
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
      const ordersToCommit = preview.orders
        .filter((h) => h.errors.length === 0 && (h.items.length > 0 || h.matched_estimate_id) && !h.items.some((it) => it.errors.length > 0))
        .map((h) => ({
          matched_order_id: h.matched_order_id,
          client_id: h.matched_client_id,
          from_estimate_id: h.matched_estimate_id || null,
          order_date: h.order_date,
          delivery_date: h.delivery_date,
          discount: h.discount || 0,
          tax_percent: h.tax_percent || 18,
          notes: h.notes,
          items: h.matched_estimate_id ? [] : h.items.map((it) => ({
            product_id: it.product_id, description: it.description, category: it.category,
            quantity: it.quantity, unit: it.unit || 'Nos', rate: it.rate,
            discount_percent: it.discount_percent || 0, tax_percent: it.tax_percent,
          })),
          skip: !!excludedRows[h.row_number],
        }));
      const res = await orderImportAPI.commit(ordersToCommit);
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
      const res = await orderImportAPI.errorReport(file);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Order_Import_Errors.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not generate the error report. Please try again.');
    } finally {
      setDownloadingErrors(false);
    }
  };

  const importableCount = preview
    ? preview.orders.filter((h) => h.errors.length === 0 && (h.items.length > 0 || h.matched_estimate_id) && !h.items.some((it) => it.errors.length > 0) && !excludedRows[h.row_number]).length
    : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Import Orders from Excel</h1>
          <p className="page-summary">
            Download the template (two sheets: Order Header and Order Items), fill it in, then upload it here for review before anything is saved.
            An order can either carry its own line items, or reference an existing Estimate to convert directly.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => navigate('/orders')}>Back to Orders</button>
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
              <button className="btn-primary" onClick={() => navigate('/orders')}>View Orders</button>
              <button className="btn-secondary" onClick={resetFile}>Import Another File</button>
            </div>
          </div>
        </Card>
      )}

      {(stage === 'empty' || stage === 'selected' || stage === 'validating') && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={orderImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
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
                  <span className="import-file-size">{formatFileSizeOrder(file.size)}</span>
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
              <h3 style={{ marginTop: 0 }}>{preview.total_orders} order{preview.total_orders !== 1 ? 's' : ''} detected</h3>
              <p>
                {preview.new_orders} new &middot; {preview.existing_orders} matching existing orders &middot;{' '}
                {preview.error_orders} rejected{preview.error_orders > 0 ? ' (won\u2019t be imported)' : ''}.
              </p>
              {preview.error_orders > 0 && (
                <button className="btn-link" onClick={downloadErrorReport} disabled={downloadingErrors}>
                  {downloadingErrors ? 'Preparing report...' : 'Download Error Report'}
                </button>
              )}
              {preview.orphan_item_rows.length > 0 && (
                <Alert type="warning" onClose={() => {}} message={
                  `${preview.orphan_item_rows.length} row(s) on the Order Items sheet reference an Order Row # that doesn't match any header row and will be ignored.`
                } />
              )}
            </div>
          </Card>

          <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th></th><th></th><th>Client</th><th>Source Estimate</th><th>Items</th><th>Total</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.orders.map((h) => {
                const status = headerStatusOrder(h);
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
                          {isExpanded ? '\u25be' : '\u25b8'} {h.matched_order_code || `Row ${h.row_number}`}
                        </button>
                      </td>
                      <td>{h.client_name || '-'}{h.matched_client_id ? '' : ' (not found)'}</td>
                      <td>{h.matched_estimate_code || (h.raw_estimate_id ? `${h.raw_estimate_id} (not found)` : '-')}</td>
                      <td>{h.matched_estimate_id ? 'from Estimate' : h.items.length}</td>
                      <td>{h.computed_total != null ? `\u20b9${Number(h.computed_total).toLocaleString('en-IN')}` : '-'}</td>
                      <td>
                        <span className={`status-badge ${status.className}`}>{status.label}</span>
                        {h.errors.length > 0 && <div className="import-row-error">{h.errors.join('; ')}</div>}
                      </td>
                    </tr>
                    {isExpanded && !h.matched_estimate_id && h.items.map((it) => (
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
          </div>

          <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="btn-primary" onClick={handleImport} disabled={stage === 'importing' || importableCount === 0}>
              {stage === 'importing' ? 'Importing...' : `Confirm Import (${importableCount} order${importableCount !== 1 ? 's' : ''})`}
            </button>
            <button className="btn-secondary" onClick={resetFile} disabled={stage === 'importing'}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}

// --- ../components/LineItemEditor.jsx ---
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

// Product ID + search, shared by every row -
// the user should never need to remember Product IDs.
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
      // conflicting name (Product ID/name consistency rule).
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


export { emptyRow, quantityViolatesWholeUnitRule };

export { PaymentsPage, EstimateImportPage, OrderImportPage, LineItemEditor };
