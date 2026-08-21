import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { suppliersAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import KpiCard from '../components/common/KpiCard';

function SuppliersPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const isStrictlyMaster = user?.role === 'master';
  const [suppliers, setSuppliers] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = () => {
    setPageLoading(true);
    suppliersAPI.list().then((res) => setSuppliers(res.data)).finally(() => setPageLoading(false));
  };
  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await suppliersAPI.create(formData);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add supplier');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await suppliersAPI.update(editingSupplier.id, formData);
      setEditingSupplier(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update supplier');
    } finally {
      setLoading(false);
    }
  };

  const [pendingDelete, setPendingDelete] = useState(null);
  const handleDelete = (supplier) => setPendingDelete(supplier);
  const confirmDelete = async () => {
    setError('');
    try {
      await suppliersAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete supplier');
      setPendingDelete(null);
    }
  };

  const columns = [
    { key: 'supplier_code', label: 'Supplier ID' }, { key: 'name', label: 'Name' },
    { key: 'category', label: 'Category' }, { key: 'contact_person', label: 'Contact Person' },
    { key: 'phone', label: 'Phone' }, { key: 'payment_terms', label: 'Payment Terms' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingSupplier(row); }}>Edit</button> : null
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
    { name: 'category', label: 'Category' },
    { name: 'phone', label: 'Phone', hint: 'Exactly 10 digits.',
      validate: (value) => (/^[0-9]{10}$/.test(value) ? '' : 'Please enter valid mobile number') },
    { name: 'contact_person', label: 'Contact Person', advanced: true },
    {
      name: 'gstin', label: 'GSTIN', advanced: true,
      hint: '15-character GST identification number',
      validate: (value) => (value.length !== 15 ? 'GSTIN must contain 15 characters.' : null),
    },
    { name: 'payment_terms', label: 'Payment Terms', advanced: true },
    { name: 'address', label: 'Address', type: 'textarea', advanced: true },
    { name: 'remarks', label: 'Remarks', type: 'textarea', advanced: true },
  ];

  const editFields = fields.filter((f) => f.name !== 'supplier_code');

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Suppliers</h1>
          <p className="page-summary">Track supplier relationships and purchase history.</p>
        </div>
        {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Supplier</button>}
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <div className="kpi-row">
        <KpiCard label="Total Suppliers" value={suppliers.length} />
      </div>
      <Table
        columns={columns} data={suppliers} loading={pageLoading}
        onRowClick={(row) => navigate(`/suppliers/${row.id}`)}
        emptyMessage="No suppliers added yet. Add your first supplier to start managing purchase relationships."
        emptyAction={isPrivileged ? { label: 'Add Supplier', onClick: () => setShowAdd(true) } : undefined}
      />
      <Modal isOpen={showAdd} title="Add Supplier" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Supplier" />
      </Modal>
      <Modal isOpen={!!editingSupplier} title={`Edit ${editingSupplier?.name || ''}`} onClose={() => setEditingSupplier(null)}>
        {editingSupplier && (
          <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingSupplier} />
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

export default SuppliersPage;
