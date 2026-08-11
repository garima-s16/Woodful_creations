import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { candidatesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function CandidatesPage() {
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => candidatesAPI.list().then((res) => setCandidates(res.data)).catch(() => setError('You do not have permission to view candidates.'));
  useEffect(() => {
    load();
  }, []);

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
        <select value={v} onClick={(e) => e.stopPropagation()} onChange={(e) => handleStatusChange(row.id, e.target.value)}>
          {['Applied', 'Shortlisted', 'Selected', 'Rejected'].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      ),
    },
  ];

  const fields = [
    { name: 'name', label: 'Name', required: true, section: 'Candidate Identity' },
    { name: 'position', label: 'Position', section: 'Candidate Identity' },
    { name: 'experience', label: 'Experience', section: 'Candidate Identity' },
    { name: 'email', label: 'Email', type: 'email', section: 'Contact Details' },
    { name: 'phone', label: 'Phone', section: 'Contact Details' },
    { name: 'resume_url', label: 'Resume URL', section: 'Application' },
    { name: 'remarks', label: 'Remarks', type: 'textarea', section: 'Application' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Candidates</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Candidate</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={candidates} onRowClick={(row) => navigate(`/candidates/${row.id}`)} emptyMessage="No candidates yet. Add your first candidate to start the hiring pipeline." />
      <Modal isOpen={showAdd} title="Add Candidate" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Candidate" />
      </Modal>
    </div>
  );
}

export default CandidatesPage;
