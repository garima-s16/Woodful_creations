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
  const [editingEstimate, setEditingEstimate] = useState(null);
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

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await estimatesAPI.update(editingEstimate.id, {
        material_cost: formData.material_cost, labor_cost: formData.labor_cost,
        tax_percent: formData.tax_percent, status: formData.status,
        valid_until: formData.valid_until ? new Date(formData.valid_until).toISOString() : null,
        remarks: formData.remarks,
      });
      setEditingEstimate(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update estimate');
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
      key: 'quote_pdf', label: 'Quote', render: (v, row) => (
        <a href={reportsAPI.downloadUrl(`estimates/${row.id}/quote.pdf`)} target="_blank" rel="noreferrer">Download PDF</a>
      ),
    },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={() => setEditingEstimate(row)}>Edit</button>
      ),
    },
  ];

  const createFields = [
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

  const editFields = [
    { name: 'material_cost', label: 'Material Cost', type: 'number', required: true },
    { name: 'labor_cost', label: 'Labor Cost', type: 'number', required: true },
    { name: 'tax_percent', label: 'Tax %', type: 'number' },
    { name: 'status', label: 'Status', type: 'select', options: [
      { value: 'draft', label: 'Draft' }, { value: 'sent', label: 'Sent' },
      { value: 'approved', label: 'Approved' }, { value: 'rejected', label: 'Rejected' },
    ] },
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
      <Table columns={columns} data={estimates} emptyMessage="No estimates yet. Create your first estimate to get started." />
      <Modal isOpen={showAdd} title="New Estimate" onClose={() => setShowAdd(false)}>
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Create Estimate" />
      </Modal>
      <Modal isOpen={!!editingEstimate} title={`Edit ${editingEstimate?.estimate_code || ''}`} onClose={() => setEditingEstimate(null)}>
        {editingEstimate && (
          <Form
            fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
            initialValues={{
              material_cost: editingEstimate.material_cost, labor_cost: editingEstimate.labor_cost,
              tax_percent: editingEstimate.tax_percent, status: editingEstimate.status,
              valid_until: editingEstimate.valid_until ? editingEstimate.valid_until.slice(0, 10) : '',
              remarks: editingEstimate.remarks || '',
            }}
          />
        )}
      </Modal>
    </div>
  );
}

export default EstimatesPage;
