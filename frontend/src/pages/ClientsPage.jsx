import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { clientsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import KpiCard from '../components/common/KpiCard';
import Pagination from '../components/common/Pagination';

const PAGE_SIZE = 25;

function ClientsPage() {
  const navigate = useNavigate();
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

  const load = (searchTerm, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    const params = { limit: PAGE_SIZE, offset };
    if (searchTerm) params.search = searchTerm;
    setPageLoading(true);
    clientsAPI.list(params).then((res) => {
      setClients(res.data);
      setTotalCount(Number(res.headers['x-total-count'] || res.data.length));
    }).finally(() => setPageLoading(false));
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

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await clientsAPI.create(formData);
      setShowAdd(false);
      load(search, page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add client');
    } finally {
      setLoading(false);
    }
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

  const columns = [
    { key: 'client_code', label: 'Client ID' }, { key: 'name', label: 'Name' },
    { key: 'phone', label: 'Phone' }, { key: 'email', label: 'Email' },
    { key: 'lead_source', label: 'Lead Source' }, { key: 'address', label: 'Address' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingClient(row); }}>Edit</button>
      ),
    },
  ];

  const fields = [
    { name: 'name', label: 'Name', required: true, section: 'Client Identity' },
    { name: 'phone', label: 'Phone', section: 'Contact Details' },
    { name: 'email', label: 'Email', type: 'email', section: 'Contact Details' },
    { name: 'address', label: 'Address', type: 'textarea', section: 'Address' },
    { name: 'lead_source', label: 'Lead Source', section: 'Commercial Information' },
    { name: 'remarks', label: 'Remarks', type: 'textarea', section: 'Commercial Information' },
  ];

  const editFields = fields.filter((f) => f.name !== 'client_code').map(({ section, ...f }) => f);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Clients</h1>
          <p className="page-summary">Manage client profiles, projects, and business history in one place.</p>
        </div>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Client</button>
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
      <Modal isOpen={showAdd} title="Add Client" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Client" />
      </Modal>
      <Modal isOpen={!!editingClient} title={`Edit ${editingClient?.name || ''}`} onClose={() => setEditingClient(null)}>
        {editingClient && (
          <Form
            fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
            initialValues={editingClient}
          />
        )}
      </Modal>
    </div>
  );
}

export default ClientsPage;
