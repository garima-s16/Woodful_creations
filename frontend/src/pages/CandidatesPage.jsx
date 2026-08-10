import React, { useEffect, useState } from 'react';
import { candidatesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function CandidatesPage() {
  const [candidates, setCandidates] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => candidatesAPI.list().then((res) => setCandidates(res.data)).catch(() => setError('You do not have permission to view candidates.'));
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await candidatesAPI.create(formData);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add candidate');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (id, status) => {
    try {
      await candidatesAPI.update(id, { status });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update status');
    }
  };

  const columns = [
    { key: 'name', label: 'Name' }, { key: 'position', label: 'Position' },
    { key: 'phone', label: 'Phone' }, { key: 'email', label: 'Email' }, { key: 'experience', label: 'Experience' },
    {
      key: 'status', label: 'Status', render: (v, row) => (
        <select value={v} onChange={(e) => handleStatusChange(row.id, e.target.value)}>
          {['Applied', 'Shortlisted', 'Selected', 'Rejected'].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      ),
    },
  ];

  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'phone', label: 'Phone' },
    { name: 'position', label: 'Position' },
    { name: 'experience', label: 'Experience' },
    { name: 'resume_url', label: 'Resume URL' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Candidates</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Candidate</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={candidates} />
      <Modal isOpen={showAdd} title="Add Candidate" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Candidate" />
      </Modal>
    </div>
  );
}

export default CandidatesPage;
