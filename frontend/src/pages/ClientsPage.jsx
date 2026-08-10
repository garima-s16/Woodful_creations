import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function ClientsPage() {
  const navigate = useNavigate();
  const [clients, setClients] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => clientsAPI.list().then((res) => setClients(res.data));
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await clientsAPI.create(formData);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add client');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'client_code', label: 'Client ID' }, { key: 'name', label: 'Name' },
    { key: 'phone', label: 'Phone' }, { key: 'email', label: 'Email' },
    { key: 'lead_source', label: 'Lead Source' }, { key: 'address', label: 'Address' },
  ];

  const fields = [
    { name: 'client_code', label: 'Client Code', required: true, placeholder: 'CL-006' },
    { name: 'name', label: 'Name', required: true },
    { name: 'phone', label: 'Phone' },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'address', label: 'Address', type: 'textarea' },
    { name: 'lead_source', label: 'Lead Source' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Clients</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Client</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={clients} onRowClick={(row) => navigate(`/clients/${row.id}`)} emptyMessage="No records yet." />
      <Modal isOpen={showAdd} title="Add Client" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Client" />
      </Modal>
    </div>
  );
}

export default ClientsPage;
