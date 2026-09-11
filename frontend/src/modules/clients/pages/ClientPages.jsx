// Client pages: list/CRUD and Excel import. Combines the former
// ClientsPage.jsx and ClientImportPage.jsx. ClientDetailPage.jsx
// remains separate.
import React, { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { clientImportAPI, clientsAPI, reportsAPI, settingsAPI } from '../../../utils/api';
import { Alert, Card, ConfirmDialog, Form, KpiCard, Modal, Pagination, Table } from '../../../components/common/UI';

// --- ClientsPage.jsx ---
const PAGE_SIZE = 25;

function ClientsPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isStrictlyMaster = user?.role === 'master';
  const [clients, setClients] = useState([]);
  const [leadSources, setLeadSources] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingClient, setEditingClient] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  // Possible-duplicate check on create: the backend already exposes
  // GET /api/clients/check-duplicates (fuzzy name match), but nothing
  // in the UI ever called it, so two "Sanket"s could be entered by
  // accident with no warning at all. Non-blocking by design, matching
  // the backend's own intent - it flags, the user decides.
  const [duplicateMatches, setDuplicateMatches] = useState(null);
  const [pendingCreateData, setPendingCreateData] = useState(null);

  const load = (searchTerm, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    const params = { limit: PAGE_SIZE, offset };
    if (searchTerm) params.search = searchTerm;
    setPageLoading(true);
    setLoadError(false);
    clientsAPI.list(params).then((res) => {
      setClients(res.data);
      setTotalCount(Number(res.headers['x-total-count'] || res.data.length));
    }).catch(() => {
      setLoadError(true);
    }).finally(() => setPageLoading(false));
  };

  useEffect(() => {
    load();
    settingsAPI.list('lead-sources').then((res) => setLeadSources(res.data)).catch(() => setLeadSources([]));
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    load(search, 1);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(search, pageNum);
  };

  const createClient = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await clientsAPI.create(formData);
      setShowAdd(false);
      setDuplicateMatches(null);
      setPendingCreateData(null);
      setSuccess('Client created.');
      load(search, page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add client');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (formData) => {
    setError('');
    try {
      const res = await clientsAPI.checkDuplicates(formData.name);
      const matches = res.data?.possible_duplicates || [];
      if (matches.length > 0) {
        setDuplicateMatches(matches);
        setPendingCreateData(formData);
        return;
      }
    } catch {
      // Duplicate check is advisory only - if it fails, don't block adding the client.
    }
    createClient(formData);
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await clientsAPI.update(editingClient.id, formData);
      setEditingClient(null);
      setSuccess('Client updated.');
      load(search, page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update client');
    } finally {
      setLoading(false);
    }
  };

  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const handleDelete = (clientRow) => setPendingDelete(clientRow);
  const confirmDelete = async () => {
    setError('');
    setDeleting(true);
    try {
      await clientsAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      load(search, page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete client');
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    {
      key: 'business_id', label: 'Client ID', render: (v, row) => (
        <div className="client-id-cell">
          <span className="business-id-badge">{row.business_id || '—'}</span>
          <span className="client-id-ref">{row.client_code}</span>
        </div>
      ),
    },
    { key: 'name', label: 'Name' },
    { key: 'client_type', label: 'Type' },
    { key: 'phone', label: 'Phone' }, { key: 'email', label: 'Email' }, { key: 'city', label: 'City' },
    { key: 'status', label: 'Status' },
    { key: 'lead_source', label: 'Lead Source' }, { key: 'address', label: 'Address' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingClient(row); }}>Edit</button>
      ),
    },
    {
      key: 'delete_action', label: '', render: (v, row) => (
        isStrictlyMaster ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); handleDelete(row); }}>Delete</button> : null
      ),
    },
  ];

  const fields = [
    { name: 'name', label: 'Client Name', required: true },
    {
      name: 'client_type', label: 'Client Type', type: 'select', required: true,
      options: [{ value: 'Individual', label: 'Individual' }, { value: 'Business', label: 'Business' }],
    },
    {
      name: 'phone', label: 'Phone', required: true,
      hint: 'Exactly 10 digits.',
      validate: (value) => (/^[0-9]{10}$/.test(value) ? '' : 'Please enter valid mobile number'),
    },
    { name: 'contact_person', label: 'Contact Person', placeholder: 'Who to actually call, if different from the client name' },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'status', label: 'Status', type: 'select', options: [
      { value: 'Active', label: 'Active' }, { value: 'Inactive', label: 'Inactive' },
    ] },
    { name: 'alternate_phone', label: 'Alternate Phone', advanced: true,
      hint: 'Exactly 10 digits.',
      validate: (value) => (/^[0-9]{10}$/.test(value) ? '' : 'Please enter valid mobile number') },
    { name: 'address', label: 'Address', type: 'textarea', advanced: true },
    { name: 'site_address', label: 'Site Address', type: 'textarea', advanced: true,
      hint: 'Where the work actually happens, if different from the address above.' },
    { name: 'city', label: 'City', advanced: true },
    { name: 'state', label: 'State', advanced: true },
    { name: 'pincode', label: 'Pincode', advanced: true },
    { name: 'gstin', label: 'GSTIN', advanced: true,
      validate: (value) => (value.length === 15 ? '' : 'GSTIN must contain 15 characters') },
    { name: 'lead_source', label: 'Lead Source', type: 'select', advanced: true,
      options: leadSources.map((s) => ({ value: s.name, label: s.name })) },
    { name: 'remarks', label: 'Notes', type: 'textarea', advanced: true },
  ];

  const editFields = fields.filter((f) => f.name !== 'client_code');

  const exportUrl = () => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    const qs = params.toString();
    return reportsAPI.downloadUrl(`clients.xlsx${qs ? `?${qs}` : ''}`);
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Clients</h1>
          <p className="page-summary">Manage client profiles, projects, and business history in one place.</p>
        </div>
        <div className="page-actions">
          <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Client</button>
          {isStrictlyMaster && (
            <>
              <a className="btn-secondary" href={clientImportAPI.templateUrl}>Download Template</a>
              <button className="btn-secondary" onClick={() => navigate('/clients/import')}>Import Excel</button>
            </>
          )}
          <a className="btn-secondary" href={exportUrl()} target="_blank" rel="noreferrer">
            {search ? 'Export Filtered' : 'Export All'}
          </a>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}
      <div className="kpi-row">
        <KpiCard label="Total Clients" value={totalCount} />
      </div>
      <form className="page-search" onSubmit={handleSearch}>
        <input
          type="text" placeholder="Search by name, code, or phone..." value={search}
          onChange={(e) => setSearch(e.target.value)} className="form-input"
        />
        <button type="submit" className="btn-secondary">Search</button>
      </form>
      <Table columns={columns} data={clients} loading={pageLoading} error={loadError} onRetry={() => load(search, page)} onRowClick={(row) => navigate(`/clients/${row.id}`)} emptyMessage="No clients yet. Add your first client to get started." emptyAction={{ label: 'Add Client', onClick: () => setShowAdd(true) }} />
      {totalCount > PAGE_SIZE && (
        <Pagination
          currentPage={page}
          totalPages={Math.ceil(totalCount / PAGE_SIZE)}
          onPageChange={goToPage}
        />
      )}
      <Modal isOpen={showAdd} title="Add Client" onClose={() => { setShowAdd(false); setDuplicateMatches(null); setPendingCreateData(null); }}>
        {duplicateMatches ? (
          <div>
            <Alert
              type="warning" onClose={() => {}}
              message={`This might be a duplicate - ${duplicateMatches.length} existing client(s) have a similar name. Review below, or continue if this is genuinely a different client.`}
            />
            <ul className="duplicate-match-list">
              {duplicateMatches.map((m) => (
                <li key={m.id}>
                  <strong>{m.name}</strong> &middot; {m.client_code} {m.phone ? `\u00b7 ${m.phone}` : ''}
                </li>
              ))}
            </ul>
            <div className="page-actions" style={{ marginTop: 16 }}>
              <button className="btn-secondary" onClick={() => { setDuplicateMatches(null); setPendingCreateData(null); }} disabled={loading}>
                Go Back
              </button>
              <button className="btn-primary" onClick={() => createClient(pendingCreateData)} disabled={loading}>
                {loading ? 'Adding...' : 'Add Anyway'}
              </button>
            </div>
          </div>
        ) : (
          <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Client" />
        )}
      </Modal>
      <Modal isOpen={!!editingClient} title={`Edit ${editingClient?.name || ''}`} onClose={() => setEditingClient(null)}>
        {editingClient && (
          <Form
            fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
            initialValues={editingClient}
          />
        )}
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDelete}
        message={pendingDelete ? `Delete ${pendingDelete.name}? This cannot be undone.` : ''}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
        loading={deleting}
      />
    </div>
  );
}

// --- ClientImportPage.jsx ---
function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function rowStatus(row, resolution) {
  if (row.errors.length > 0) return { label: 'ERROR', className: 'status-danger' };
  if (row.is_duplicate) return { label: 'EXISTING CLIENT', className: 'status-info' };
  if (row.possible_match_client_id && resolution === 'existing') return { label: 'WILL USE EXISTING', className: 'status-info' };
  if (row.possible_match_client_id && resolution !== 'new') return { label: 'POSSIBLE MATCH - REVIEW', className: 'status-warning' };
  return { label: 'NEW', className: 'status-gold' };
}

function ClientImportPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [lastUploadedFile, setLastUploadedFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({}); // row_number -> true if user opted out
  // A possible (fuzzy) match is never auto-resolved.
  // row_number -> 'existing' | 'new', unset until the user picks one.
  const [matchResolutions, setMatchResolutions] = useState({});
  const [stage, setStage] = useState('empty'); // empty | selected | validating | preview | importing | success | error
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  const resetFile = () => {
    setFile(null);
    setPreview(null);
    setExcludedRows({});
    setMatchResolutions({});
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
      setMatchResolutions({});
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
        .map((r) => {
          const resolution = matchResolutions[r.row_number];
          const usingExisting = r.possible_match_client_id && resolution === 'existing';
          // A possible (not exact) match that hasn't been explicitly resolved
          // yet is never imported silently as either choice - skip it until
          // the user picks "Use Existing" or "Create New".
          const unresolvedPossibleMatch = r.possible_match_client_id && !resolution;
          return {
            name: r.name, client_type: r.client_type, contact_person: r.contact_person, phone: r.phone,
            alternate_phone: r.alternate_phone, email: r.email, address: r.address,
            site_address: r.site_address, city: r.city, state: r.state, pincode: r.pincode, gstin: r.gstin,
            lead_source: r.lead_source, remarks: r.remarks,
            matched_client_id: usingExisting ? r.possible_match_client_id : r.matched_client_id,
            skip: !!excludedRows[r.row_number] || unresolvedPossibleMatch,
          };
        });
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
  const importableCount = preview ? preview.rows.filter((r) => {
    if (r.errors.length > 0 || excludedRows[r.row_number]) return false;
    if (r.possible_match_client_id && !matchResolutions[r.row_number]) return false;
    return true;
  }).length : 0;

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

          <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th></th><th>Client Name</th><th>Type</th><th>Phone</th><th>Email</th><th>City</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r) => {
                const resolution = matchResolutions[r.row_number];
                const status = rowStatus(r, resolution);
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
                    <td>{r.client_type || '-'}</td>
                    <td>{r.phone || '-'}</td>
                    <td>{r.email || '-'}</td>
                    <td>{r.city || '-'}</td>
                    <td>
                      <span className={`status-badge ${status.className}`}>{status.label}</span>
                      {r.errors.length > 0 && (
                        <div className="import-row-error">{r.errors.join('; ')}</div>
                      )}
                      {r.possible_match_client_id && !r.is_duplicate && r.errors.length === 0 && (
                        <div className="import-row-possible-match">
                          <span>You entered <strong>{r.name}</strong> - an existing client named{' '}
                            <strong>{r.possible_match_name}</strong> looks similar. Is this the same client?</span>
                          <div style={{ marginTop: 6, display: 'flex', gap: 8 }}>
                            <button
                              type="button" className="btn-link"
                              onClick={() => setMatchResolutions((prev) => ({ ...prev, [r.row_number]: 'existing' }))}
                            >
                              Use Existing
                            </button>
                            <button
                              type="button" className="btn-link"
                              onClick={() => setMatchResolutions((prev) => ({ ...prev, [r.row_number]: 'new' }))}
                            >
                              Create New (Different Client)
                            </button>
                          </div>
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

export { ClientsPage, ClientImportPage };
