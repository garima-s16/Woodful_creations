import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { settingsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { classifyLoadError } from '../utils/loadError';

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

export default SettingsPage;
