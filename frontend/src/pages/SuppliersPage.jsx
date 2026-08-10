import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { suppliersAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function SuppliersPage() {
  const navigate = useNavigate();
  const [suppliers, setSuppliers] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => suppliersAPI.list().then((res) => setSuppliers(res.data));
  useEffect(load, []);

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

  const columns = [
    { key: 'supplier_code', label: 'Supplier ID' }, { key: 'name', label: 'Name' },
    { key: 'category', label: 'Category' }, { key: 'contact_person', label: 'Contact Person' },
    { key: 'phone', label: 'Phone' }, { key: 'payment_terms', label: 'Payment Terms' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingSupplier(row); }}>Edit</button>
      ),
    },
  ];

  const fields = [
    { name: 'supplier_code', label: 'Supplier Code', required: true, placeholder: 'SUP-006' },
    { name: 'name', label: 'Name', required: true },
    { name: 'category', label: 'Category' },
    { name: 'contact_person', label: 'Contact Person' },
    { name: 'phone', label: 'Phone' },
    { name: 'gstin', label: 'GSTIN' },
    { name: 'payment_terms', label: 'Payment Terms' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  const editFields = fields.filter((f) => f.name !== 'supplier_code');

  return (
    <div className="page">
      <div className="page-header">
        <h1>Suppliers</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Supplier</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={suppliers} onRowClick={(row) => navigate(`/suppliers/${row.id}`)} emptyMessage="No suppliers yet. Add your first supplier to get started." />
      <Modal isOpen={showAdd} title="Add Supplier" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Supplier" />
      </Modal>
      <Modal isOpen={!!editingSupplier} title={`Edit ${editingSupplier?.name || ''}`} onClose={() => setEditingSupplier(null)}>
        {editingSupplier && (
          <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingSupplier} />
        )}
      </Modal>
    </div>
  );
}

export default SuppliersPage;
