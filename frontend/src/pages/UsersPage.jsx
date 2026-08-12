import React, { useEffect, useState } from 'react';
import { usersAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function UsersPage() {
  const [users, setUsers] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = () => {
    setPageLoading(true);
    usersAPI.list().then((res) => setUsers(res.data)).catch(() => setError('You do not have permission to manage users.')).finally(() => setPageLoading(false));
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

  const handleDeactivate = async (user) => {
    if (!window.confirm(`Remove ${user.username}'s access? This can be reversed by an administrator.`)) return;
    setError('');
    try {
      await usersAPI.remove(user.id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove user');
    }
  };

  const columns = [
    { key: 'username', label: 'Username' }, { key: 'full_name', label: 'Full Name' },
    { key: 'email', label: 'Email' }, { key: 'role', label: 'Role' },
    { key: 'is_active', label: 'Status', render: (v) => <span className={`status-badge ${v ? 'status-ok' : 'status-danger'}`}>{v ? 'Active' : 'Inactive'}</span> },
    { key: 'cannot_be_deleted', label: 'Protected', render: (v) => v ? 'Yes' : 'No' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={() => setEditingUser(row)}>Edit</button>
      ),
    },
    {
      key: 'remove_action', label: '', render: (v, row) => (
        !row.cannot_be_deleted && <button className="btn-link" onClick={() => handleDeactivate(row)} style={{ color: 'var(--danger)' }}>Remove</button>
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
      { value: 'user', label: 'User (Limited Access)' }, { value: 'manager', label: 'Manager' }, { value: 'master', label: 'Master (Full Access)' },
    ] },
  ];

  const editFields = [
    { name: 'full_name', label: 'Full Name', required: true },
    { name: 'phone', label: 'Phone' },
    { name: 'role', label: 'Role', type: 'select', required: true, options: [
      { value: 'user', label: 'User (Limited Access)' }, { value: 'manager', label: 'Manager' }, { value: 'master', label: 'Master (Full Access)' },
    ] },
    { name: 'is_active', label: 'Status', type: 'select', options: [
      { value: 'true', label: 'Active' }, { value: 'false', label: 'Inactive' },
    ] },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Users</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add User</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={users} loading={pageLoading} emptyMessage="No users found." />

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
    </div>
  );
}

export default UsersPage;
