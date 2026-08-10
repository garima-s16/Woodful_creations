import React, { useEffect, useState } from 'react';
import { settingsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

const LABELS = {
  'units': 'Units', 'material-categories': 'Material Categories', 'stock-statuses': 'Stock Statuses',
  'stock-payment-statuses': 'Stock Payment Statuses', 'locations': 'Locations', 'supplier-terms': 'Supplier Terms',
  'departments': 'Departments', 'task-statuses': 'Task Statuses', 'attendance-statuses': 'Attendance Statuses',
  'machines': 'Machines', 'project-statuses': 'Project Statuses', 'priorities': 'Priorities',
  'payment-modes': 'Payment Modes', 'lead-sources': 'Lead Sources', 'project-types': 'Project Types',
  'expense-categories': 'Expense Categories',
};

function SettingsPage() {
  const [lookupTypes, setLookupTypes] = useState([]);
  const [selected, setSelected] = useState('');
  const [values, setValues] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    settingsAPI.types().then((res) => {
      setLookupTypes(res.data.lookup_types);
      setSelected(res.data.lookup_types[0]);
    });
  }, []);

  const loadValues = (type) => {
    if (!type) return;
    settingsAPI.list(type).then((res) => setValues(res.data));
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

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this value?')) return;
    try {
      await settingsAPI.remove(selected, id);
      loadValues(selected);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete value');
    }
  };

  const columns = [
    { key: 'name', label: 'Name' }, { key: 'description', label: 'Description' },
    { key: 'id', label: '', render: (v) => <button className="btn-link" onClick={() => handleDelete(v)}>Delete</button> },
  ];

  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'description', label: 'Description' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)} disabled={!selected}>Add Value</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
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
          <Table columns={columns} data={values} />
        </div>
      </div>
      <Modal isOpen={showAdd} title={`Add ${LABELS[selected] || selected}`} onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add" />
      </Modal>
    </div>
  );
}

export default SettingsPage;
