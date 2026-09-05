import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { usersAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { statusClass } from '../utils/format';

function UsersPage() {
  const { user } = useSelector((state) => state.auth);
  const isStrictlyMaster = user?.role === 'master';
  const [users, setUsers] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    usersAPI.list().then((res) => setUsers(res.data)).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to manage users.' : 'Unable to load users. Please try again.');
    }).finally(() => setPageLoading(false));
  };
  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await usersAPI.create(formData);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await usersAPI.update(editingUser.id, {
        full_name: formData.full_name, phone: formData.phone, role: formData.role,
        is_active: formData.is_active === 'true' || formData.is_active === true,
      });
      setEditingUser(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update user');
    } finally {
      setLoading(false);
    }
  };

  const [pendingDeactivate, setPendingDeactivate] = useState(null);
  const [deactivating, setDeactivating] = useState(false);
  const handleDeactivate = (user) => setPendingDeactivate(user);
  const confirmDeactivate = async () => {
    setError('');
    setDeactivating(true);
    try {
      await usersAPI.remove(pendingDeactivate.id);
      setPendingDeactivate(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove user');
      setPendingDeactivate(null);
    } finally {
      setDeactivating(false);
    }
  };

  const columns = [
    { key: 'username', label: 'Username' }, { key: 'full_name', label: 'Full Name' },
    { key: 'email', label: 'Email' }, { key: 'role', label: 'Role' },
    { key: 'is_active', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v ? 'Active' : 'Inactive')}`}>{v ? 'Active' : 'Inactive'}</span> },
    { key: 'cannot_be_deleted', label: 'Protected', render: (v) => v ? 'Yes' : 'No' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isStrictlyMaster ? <button className="btn-link" onClick={() => setEditingUser(row)}>Edit</button> : null
      ),
    },
    {
      key: 'remove_action', label: '', render: (v, row) => (
        !row.cannot_be_deleted && row.role !== 'master' && <button className="btn-link" onClick={() => handleDeactivate(row)} style={{ color: 'var(--danger)' }}>Remove</button>
      ),
    },
  ];

  const createFields = [
    { name: 'username', label: 'Username', required: true },
    { name: 'full_name', label: 'Full Name', required: true },
    { name: 'email', label: 'Email', type: 'email', required: true },
    { name: 'phone', label: 'Phone' },
    { name: 'password', label: 'Temporary Password', type: 'password', required: true, hint: 'The user should change this after first login.' },
    { name: 'role', label: 'Role', type: 'select', required: true, options: [
      { value: 'user', label: 'Employee (Limited Access)' }, { value: 'master', label: 'Master (Full Access)' },
    ] },
  ];

  const editFields = [
    { name: 'full_name', label: 'Full Name', required: true },
    { name: 'phone', label: 'Phone' },
    { name: 'role', label: 'Role', type: 'select', required: true, options: [
      { value: 'user', label: 'Employee (Limited Access)' }, { value: 'master', label: 'Master (Full Access)' },
    ] },
    { name: 'is_active', label: 'Status', type: 'select', options: [
      { value: 'true', label: 'Active' }, { value: 'false', label: 'Inactive' },
    ] },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Users</h1>
          <p className="page-summary">Manage login accounts and their Master/User access level.</p>
        </div>
        {isStrictlyMaster && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add User</button>}
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={users} loading={pageLoading} error={loadError} onRetry={load} emptyMessage="No users found." />

      <Modal isOpen={showAdd} title="Add User" onClose={() => setShowAdd(false)}>
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Create User" />
      </Modal>

      <Modal isOpen={!!editingUser} title={`Edit ${editingUser?.username || ''}`} onClose={() => setEditingUser(null)}>
        {editingUser && (
          <Form
            fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
            initialValues={{
              full_name: editingUser.full_name, phone: editingUser.phone,
              role: editingUser.role, is_active: String(editingUser.is_active),
            }}
          />
        )}
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDeactivate}
        title="Remove Access"
        message={pendingDeactivate ? `Remove ${pendingDeactivate.username}'s access? This can be reversed by an administrator.` : ''}
        confirmLabel="Remove Access"
        onConfirm={confirmDeactivate}
        onCancel={() => setPendingDeactivate(null)}
        loading={deactivating}
      />
    </div>
  );
}

export default UsersPage;
