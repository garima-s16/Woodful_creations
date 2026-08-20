import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { clientsAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import KpiCard from '../components/common/KpiCard';
import Pagination from '../components/common/Pagination';

const PAGE_SIZE = 25;

function ClientsPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isStrictlyMaster = user?.role === 'master';
  const [clients, setClients] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingClient, setEditingClient] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
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
    clientsAPI.list(params).then((res) => {
      setClients(res.data);
      setTotalCount(Number(res.headers['x-total-count'] || res.data.length));
    }).catch(() => {}).finally(() => setPageLoading(false));
  };

  useEffect(() => {
    load();
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
      load(search, page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update client');
    } finally {
      setLoading(false);
    }
  };

  const [pendingDelete, setPendingDelete] = useState(null);
  const handleDelete = (clientRow) => setPendingDelete(clientRow);
  const confirmDelete = async () => {
    setError('');
    try {
      await clientsAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      load(search, page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete client');
      setPendingDelete(null);
    }
  };

  const columns = [
    { key: 'client_code', label: 'Client ID' }, { key: 'name', label: 'Name' },
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
    { name: 'name', label: 'Name', required: true },
    { name: 'status', label: 'Status', type: 'select', options: [
      { value: 'Active', label: 'Active' }, { value: 'Inactive', label: 'Inactive' },
    ] },
    { name: 'phone', label: 'Phone' },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'address', label: 'Address', type: 'textarea', advanced: true },
    { name: 'city', label: 'City', advanced: true },
    { name: 'lead_source', label: 'Lead Source', advanced: true },
    { name: 'remarks', label: 'Remarks', type: 'textarea', advanced: true },
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
          <a className="btn-secondary" href={exportUrl()} target="_blank" rel="noreferrer">
            {search ? 'Export Filtered' : 'Export All'}
          </a>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Client</button>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
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
      <Table columns={columns} data={clients} loading={pageLoading} onRowClick={(row) => navigate(`/clients/${row.id}`)} emptyMessage="No clients yet. Add your first client to get started." />
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
      />
    </div>
  );
}

export default ClientsPage;
