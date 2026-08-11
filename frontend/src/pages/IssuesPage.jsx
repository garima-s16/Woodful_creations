import React, { useEffect, useState } from 'react';
import { issuesAPI, materialsAPI, ordersAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function IssuesPage() {
  const [issues, setIssues] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [orders, setOrders] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => {
    issuesAPI.list().then((res) => setIssues(res.data));
    materialsAPI.list().then((res) => setMaterials(res.data));
    ordersAPI.list().then((res) => setOrders(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await issuesAPI.create({
        ...formData,
        material_id: Number(formData.material_id),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        date: new Date(formData.date).toISOString(),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record issue');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'issue_code', label: 'Issue ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'order_id', label: 'Order', render: (v) => orders.find((o) => o.id === v)?.order_code || '-' },
    { key: 'material_id', label: 'Material', render: (v) => materials.find((m) => m.id === v)?.name || v },
    { key: 'quantity_issued', label: 'Quantity' }, { key: 'unit', label: 'Unit' },
    { key: 'issued_to', label: 'Issued To' }, { key: 'department', label: 'Department' },
  ];

  const fields = [
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'material_id', label: 'Material', type: 'select', required: true, options: materials.map((m) => ({ value: m.id, label: `${m.name} (${m.current_stock} in stock)` })) },
    { name: 'order_id', label: 'Order (Project)', type: 'select', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'quantity_issued', label: 'Quantity Issued', type: 'number', required: true },
    { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets' },
    { name: 'issued_to', label: 'Issued To' },
    { name: 'department', label: 'Department' },
    { name: 'purpose', label: 'Purpose' },
    { name: 'approved_by', label: 'Approved By' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Issues (Stock Out)</h1>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('issues.xlsx')} target="_blank" rel="noreferrer">Export</a>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>Record Issue</button>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={issues} emptyMessage="No materials issued yet. Issued materials will appear here." />
      <Modal isOpen={showAdd} title="Record Issue" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Record Issue" />
      </Modal>
    </div>
  );
}

export default IssuesPage;
