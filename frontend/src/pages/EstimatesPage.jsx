import React, { useEffect, useState } from 'react';
import { estimatesAPI, clientsAPI, ordersAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function EstimatesPage() {
  const [estimates, setEstimates] = useState([]);
  const [clients, setClients] = useState([]);
  const [orders, setOrders] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => {
    estimatesAPI.list().then((res) => setEstimates(res.data));
    clientsAPI.list().then((res) => setClients(res.data));
    ordersAPI.list().then((res) => setOrders(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await estimatesAPI.create({
        ...formData,
        client_id: Number(formData.client_id),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        material_cost: formData.material_cost || '0',
        labor_cost: formData.labor_cost || '0',
        tax_percent: formData.tax_percent || '18',
        valid_until: formData.valid_until ? new Date(formData.valid_until).toISOString() : null,
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create estimate');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'estimate_code', label: 'Estimate ID' },
    { key: 'client_id', label: 'Client', render: (v) => clients.find((c) => c.id === v)?.name || v },
    { key: 'material_cost', label: 'Material', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'labor_cost', label: 'Labor', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'total_cost', label: 'Total', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'status', label: 'Status' },
    {
      key: 'id', label: 'Quote', render: (v) => (
        <a href={reportsAPI.downloadUrl(`estimates/${v}/quote.pdf`)} target="_blank" rel="noreferrer">Download PDF</a>
      ),
    },
  ];

  const fields = [
    { name: 'estimate_code', label: 'Estimate Code', required: true, placeholder: 'EST-001' },
    { name: 'client_id', label: 'Client', type: 'select', required: true, options: clients.map((c) => ({ value: c.id, label: c.name })) },
    { name: 'order_id', label: 'Related Order (optional)', type: 'select', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'description', label: 'Scope / Description', type: 'textarea' },
    { name: 'material_cost', label: 'Material Cost', type: 'number', required: true },
    { name: 'labor_cost', label: 'Labor Cost', type: 'number', required: true },
    { name: 'tax_percent', label: 'Tax %', type: 'number', placeholder: '18' },
    { name: 'valid_until', label: 'Valid Until', type: 'date' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Estimates</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>New Estimate</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={estimates} />
      <Modal isOpen={showAdd} title="New Estimate" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Create Estimate" />
      </Modal>
    </div>
  );
}

export default EstimatesPage;
