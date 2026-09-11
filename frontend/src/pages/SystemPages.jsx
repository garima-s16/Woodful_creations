// System pages: audit logs, mobile-app install prompt, 404, and
// settings/lookups. Combines the former AuditLogsPage.jsx,
// MobileAppPage.jsx, NotFoundPage.jsx, and SettingsPage.jsx.
import React, { useEffect, useState } from 'react';
import { auditLogsAPI, communicationAPI, settingsAPI } from '../utils/api';
import { Alert, Card, ConfirmDialog, Form, Modal, Table } from '../components/common/UI';
import { useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { classifyLoadError } from '../utils/utils';
import '../styles/modules.css';

// --- AuditLogsPage.jsx ---
function AuditLogsPage() {
  const [logs, setLogs] = useState([]);
  const [moduleFilter, setModuleFilter] = useState('');
  const [error, setError] = useState('');
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = (params) => {
    setPageLoading(true);
    setLoadError(false);
    auditLogsAPI.list(params).then((res) => setLogs(res.data)).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view audit logs.' : 'Unable to load audit logs. Please try again.');
    }).finally(() => setPageLoading(false));
  };
  useEffect(() => load(), []);

  const handleFilter = (e) => {
    e.preventDefault();
    load(moduleFilter ? { module_name: moduleFilter } : undefined);
  };

  const columns = [
    { key: 'created_at', label: 'Time', render: (v) => new Date(v).toLocaleString() },
    { key: 'action', label: 'Action' }, { key: 'module_name', label: 'Module' },
    { key: 'record_id', label: 'Record ID' }, { key: 'user_id', label: 'User ID' },
    { key: 'ip_address', label: 'IP Address' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Audit Logs</h1>
          <p className="page-summary">A record of who changed what, and when, across the system.</p>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <form className="page-search" onSubmit={handleFilter}>
        <input
          type="text" placeholder="Filter by module (e.g. payments, users)..." value={moduleFilter}
          onChange={(e) => setModuleFilter(e.target.value)} className="form-input"
        />
        <button type="submit" className="btn-secondary">Filter</button>
      </form>
      <Table columns={columns} data={logs} loading={pageLoading} error={loadError} onRetry={() => load(moduleFilter ? { module_name: moduleFilter } : undefined)} emptyMessage="No audit log entries found." />
    </div>
  );
}

// --- MobileAppPage.jsx ---
function MobileAppPage() {
  const { user } = useSelector((state) => state.auth);
  const [copied, setCopied] = useState(false);
  const [qrFailed, setQrFailed] = useState(false);

  // This page has no backend call of its own to enforce access through
  // (unlike most pages, which rely on the API's own RBAC check) - the
  // sidebar already hides this link from non-masters, but since there's
  // no server-side request here to also gate it, the check is made
  // directly rather than silently showing it to anyone who navigates
  // to the URL by hand.
  if (user?.role !== 'master') {
    return (
      <div className="page">
        <Alert type="error" message="This section is only available to master accounts." />
      </div>
    );
  }

  const appUrl = window.location.origin;
  const qrImageUrl = `https://api.qrserver.com/v1/create-qr-code/?size=280x280&margin=10&data=${encodeURIComponent(appUrl)}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(appUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API can fail (permissions, non-secure context) - the
      // URL is already shown as selectable text below regardless.
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Get the Mobile App</h1>
          <p className="page-summary">
            Woodful Creations works as an installable app on both iPhone and Android, directly from
            the browser - no App Store or Play Store download required.
          </p>
        </div>
      </div>

      <div className="mobile-app-grid">
        <Card>
          <div className="card-body mobile-app-qr-card">
            <h3 style={{ marginTop: 0 }}>Scan to Open</h3>
            {!qrFailed ? (
              <img
                src={qrImageUrl} alt={`QR code linking to ${appUrl}`}
                className="mobile-app-qr-image" onError={() => setQrFailed(true)}
              />
            ) : (
              <div className="mobile-app-qr-fallback">
                Couldn't load the QR image. Use the link below instead.
              </div>
            )}
            <div className="mobile-app-url-row">
              <input type="text" readOnly value={appUrl} onFocus={(e) => e.target.select()} />
              <button className="btn-secondary" onClick={handleCopy}>{copied ? 'Copied!' : 'Copy Link'}</button>
            </div>
            <p className="mobile-app-qr-note">
              QR image generated via a public QR service (api.qrserver.com) from this page's own URL -
              nothing sensitive is encoded in it.
            </p>
          </div>
        </Card>

        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>On iPhone (Safari)</h3>
            <ol className="mobile-app-steps">
              <li>Scan the code with the iPhone Camera app, or open the link above in Safari.</li>
              <li>Tap the Share button (the square with an arrow pointing up).</li>
              <li>Scroll down and tap <strong>Add to Home Screen</strong>.</li>
              <li>Tap <strong>Add</strong>. The Woodful icon now appears on the home screen like a regular app.</li>
            </ol>
            <p className="mobile-app-note">Must be opened in Safari - Add to Home Screen isn't available in Chrome or other browsers on iOS.</p>
          </div>
        </Card>

        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>On Android (Chrome)</h3>
            <ol className="mobile-app-steps">
              <li>Scan the code with the Android Camera app, or open the link above in Chrome.</li>
              <li>Tap the menu (three dots, top right) or look for an "Install app" banner.</li>
              <li>Tap <strong>Install app</strong> (or <strong>Add to Home screen</strong>).</li>
              <li>Confirm. The Woodful icon now appears on the home screen and app drawer.</li>
            </ol>
          </div>
        </Card>
      </div>
    </div>
  );
}

// --- NotFoundPage.jsx ---
function NotFoundPage() {
  return (
    <div className="page" style={{ textAlign: 'center', paddingTop: 'var(--space-8, 4rem)' }}>
      <h1 style={{ fontSize: '4rem', margin: 0 }}>404</h1>
      <p style={{ fontSize: '1.2rem', color: 'var(--text-secondary)', marginTop: 'var(--space-2, 0.5rem)' }}>
        Page not found
      </p>
      <Link to="/" className="btn-primary" style={{ display: 'inline-block', marginTop: 'var(--space-4, 1.5rem)', textDecoration: 'none' }}>
        Back to Dashboard
      </Link>
    </div>
  );
}

// --- SettingsPage.jsx ---
const LABELS = {
  'units': 'Units', 'material-categories': 'Material Categories', 'stock-statuses': 'Stock Statuses',
  'stock-payment-statuses': 'Stock Payment Statuses', 'locations': 'Locations', 'supplier-terms': 'Supplier Terms',
  'departments': 'Departments', 'task-statuses': 'Task Statuses', 'attendance-statuses': 'Attendance Statuses',
  'machines': 'Machines', 'project-statuses': 'Project Statuses', 'priorities': 'Priorities',
  'payment-modes': 'Payment Modes', 'lead-sources': 'Lead Sources', 'project-types': 'Project Types',
  'expense-categories': 'Expense Categories',
};

function SettingsPage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [lookupTypes, setLookupTypes] = useState([]);
  const [selected, setSelected] = useState('');
  const [values, setValues] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [typesError, setTypesError] = useState(null);
  const [valuesError, setValuesError] = useState(null);
  const [emailStatus, setEmailStatus] = useState(null);
  const [emailStatusError, setEmailStatusError] = useState('');
  const [testRecipient, setTestRecipient] = useState('');
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState('');
  const [testError, setTestError] = useState('');

  useEffect(() => {
    if (!isPrivileged) return;
    communicationAPI.emailStatus()
      .then((res) => setEmailStatus(res.data))
      .catch(() => setEmailStatusError('Unable to load email integration status.'));
  }, [isPrivileged]);

  const handleSendTestEmail = async () => {
    if (!testRecipient) return;
    setTestSending(true);
    setTestResult('');
    setTestError('');
    try {
      const res = await communicationAPI.sendTestEmail(testRecipient);
      setTestResult(res.data.message);
    } catch (err) {
      setTestError(err.response?.data?.detail || 'Failed to send test email.');
    } finally {
      setTestSending(false);
    }
  };

  const loadTypes = () => {
    setTypesError(null);
    settingsAPI.types().then((res) => {
      setLookupTypes(res.data.lookup_types);
      setSelected(res.data.lookup_types[0]);
    }).catch((err) => setTypesError(classifyLoadError(err, 'settings')));
  };

  useEffect(loadTypes, []);

  const loadValues = (type) => {
    if (!type) return;
    setValuesError(null);
    settingsAPI.list(type).then((res) => setValues(res.data)).catch((err) => setValuesError(classifyLoadError(err, 'these values')));
  };

  useEffect(() => loadValues(selected), [selected]);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await settingsAPI.create(selected, formData);
      setShowAdd(false);
      loadValues(selected);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add value');
    } finally {
      setLoading(false);
    }
  };

  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const handleDelete = (row) => setPendingDelete(row);
  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await settingsAPI.remove(selected, pendingDelete.id);
      setPendingDelete(null);
      loadValues(selected);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete value');
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    { key: 'name', label: 'Name' }, { key: 'description', label: 'Description' },
    { key: 'id', label: '', render: (v, row) => (isPrivileged ? <button className="btn-link" onClick={() => handleDelete(row)}>Delete</button> : null) },
  ];

  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'description', label: 'Description' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Settings</h1>
          <p className="page-summary">Manage the dropdown values used throughout the system.</p>
        </div>
        {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)} disabled={!selected}>Add Value</button>}
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {isPrivileged && (
        <Card title="Email Integration">
            {emailStatusError && <Alert type="error" message={emailStatusError} />}
            {emailStatus && (
              <>
                <div className="detail-meta">
                  <div className="detail-meta-item">
                    <span className="detail-meta-label">Status</span>
                    <span className={`status-badge ${emailStatus.is_configured ? 'status-ok' : 'status-warning'}`}>
                      {emailStatus.is_configured ? 'Configured' : 'Not Configured'}
                    </span>
                  </div>
                  <div className="detail-meta-item">
                    <span className="detail-meta-label">Sending As</span>
                    <span className="detail-meta-value">
                      {emailStatus.sender_name} &lt;{emailStatus.sender_email || 'not set'}&gt;
                    </span>
                  </div>
                  <div className="detail-meta-item">
                    <span className="detail-meta-label">SMTP Server</span>
                    <span className="detail-meta-value">{emailStatus.smtp_server}:{emailStatus.smtp_port}</span>
                  </div>
                </div>
                <p className="page-summary" style={{ margin: 'var(--space-3) 0' }}>
                  All business emails (invoices, receipts, estimates) are sent from this one Woodful
                  account. Individual users never need this account's password.
                </p>
                {testResult && <Alert type="success" message={testResult} onClose={() => setTestResult('')} />}
                {testError && <Alert type="error" message={testError} onClose={() => setTestError('')} />}
                <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
                  <input
                    type="email" placeholder="Send a test email to..." value={testRecipient}
                    onChange={(e) => setTestRecipient(e.target.value)}
                    style={{ padding: '8px 10px', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', background: 'var(--surface)', color: 'var(--text-primary)', minWidth: '220px' }}
                  />
                  <button type="button" className="btn-secondary" onClick={handleSendTestEmail} disabled={testSending || !testRecipient}>
                    {testSending ? 'Sending...' : 'Send Test Email'}
                  </button>
                </div>
              </>
            )}
        </Card>
      )}
      {typesError && (
        <div>
          <Alert type="error" message={typesError.message} />
          <button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)', marginBottom: 'var(--space-4)' }} onClick={loadTypes}>Retry</button>
        </div>
      )}
      {!typesError && (
        <div className="settings-layout">
          <div className="settings-list">
            {lookupTypes.map((type) => (
              <button
                key={type}
                className={type === selected ? 'settings-nav-item active' : 'settings-nav-item'}
                onClick={() => setSelected(type)}
              >
                {LABELS[type] || type}
              </button>
            ))}
          </div>
          <div className="settings-content">
            {valuesError ? (
              <div>
                <Alert type="error" message={valuesError.message} />
                <button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={() => loadValues(selected)}>Retry</button>
              </div>
            ) : (
              <Table columns={columns} data={values} emptyMessage="No values configured for this list yet." />
            )}
          </div>
        </div>
      )}
      <Modal isOpen={showAdd} title={`Add ${LABELS[selected] || selected}`} onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add" />
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDelete}
        message={pendingDelete ? `Delete "${pendingDelete.name}"? This cannot be undone.` : ''}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
        loading={deleting}
      />
    </div>
  );
}

export { AuditLogsPage, MobileAppPage, NotFoundPage, SettingsPage };
