import React, { useEffect, useState } from 'react';
import { materialsAPI, suppliersAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function MaterialsPage() {
  const [materials, setMaterials] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => {
    materialsAPI.list().then((res) => setMaterials(res.data));
    suppliersAPI.list().then((res) => setSuppliers(res.data));
  };

  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await materialsAPI.create({
        ...formData,
        minimum_stock: Number(formData.minimum_stock || 0),
        opening_stock: Number(formData.opening_stock || 0),
        average_rate: formData.average_rate || '0',
        supplier_id: formData.supplier_id ? Number(formData.supplier_id) : null,
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add material');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'material_code', label: 'Material ID' }, { key: 'name', label: 'Name' },
    { key: 'category', label: 'Category' }, { key: 'unit', label: 'Unit' },
    { key: 'current_stock', label: 'Current Stock' }, { key: 'minimum_stock', label: 'Minimum' },
    { key: 'stock_status', label: 'Status' },
    { key: 'average_rate', label: 'Avg Rate', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'stock_value', label: 'Stock Value', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'location', label: 'Location' },
  ];

  const fields = [
    { name: 'material_code', label: 'Material Code', required: true, placeholder: 'MAT-011' },
    { name: 'name', label: 'Name', required: true },
    { name: 'category', label: 'Category' },
    { name: 'brand_grade', label: 'Brand/Grade' },
    { name: 'thickness_size', label: 'Thickness/Size' },
    { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets' },
    { name: 'opening_stock', label: 'Opening Stock', type: 'number' },
    { name: 'minimum_stock', label: 'Minimum Stock', type: 'number' },
    { name: 'average_rate', label: 'Average Rate', type: 'number' },
    {
      name: 'supplier_id', label: 'Primary Supplier', type: 'select',
      options: suppliers.map((s) => ({ value: s.id, label: s.name })),
    },
    { name: 'location', label: 'Location' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Materials</h1>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('stock-dashboard.xlsx')} target="_blank" rel="noreferrer">
            Export Stock Dashboard
          </a>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Material</button>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={materials} />

      <Modal isOpen={showAdd} title="Add Material" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Material" />
      </Modal>
    </div>
  );
}

export default MaterialsPage;
