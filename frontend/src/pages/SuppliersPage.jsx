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

  const columns = [
    { key: 'supplier_code', label: 'Supplier ID' }, { key: 'name', label: 'Name' },
    { key: 'category', label: 'Category' }, { key: 'contact_person', label: 'Contact Person' },
    { key: 'phone', label: 'Phone' }, { key: 'payment_terms', label: 'Payment Terms' },
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

  return (
    <div className="page">
      <div className="page-header">
        <h1>Suppliers</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Supplier</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={suppliers} onRowClick={(row) => navigate(`/suppliers/${row.id}`)} emptyMessage="No records yet." />
      <Modal isOpen={showAdd} title="Add Supplier" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Supplier" />
      </Modal>
    </div>
  );
}

export default SuppliersPage;
