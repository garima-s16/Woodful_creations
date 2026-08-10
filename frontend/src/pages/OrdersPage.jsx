import React, { useEffect, useState } from 'react';
import { ordersAPI, clientsAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function OrdersPage() {
  const [orders, setOrders] = useState([]);
  const [clients, setClients] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => {
    ordersAPI.list().then((res) => setOrders(res.data));
    clientsAPI.list().then((res) => setClients(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await ordersAPI.create({
        ...formData,
        client_id: Number(formData.client_id),
        order_date: new Date(formData.order_date).toISOString(),
        delivery_date: formData.delivery_date ? new Date(formData.delivery_date).toISOString() : null,
        order_value: formData.order_value || '0',
        advance: formData.advance || '0',
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create order');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'order_code', label: 'Order ID' },
    { key: 'client_id', label: 'Client', render: (v) => clients.find((c) => c.id === v)?.name || v },
    { key: 'project_type', label: 'Project Type' },
    { key: 'order_value', label: 'Order Value', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'total_received', label: 'Received', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'balance', label: 'Balance', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'project_status', label: 'Status' }, { key: 'progress_percent', label: 'Progress %' },
    {
      key: 'id', label: 'Estimate', render: (v, row) => (
        <a href={reportsAPI.downloadUrl(`orders/${v}/estimate.pdf`)} target="_blank" rel="noreferrer">Download PDF</a>
      ),
    },
  ];

  const fields = [
    { name: 'order_code', label: 'Order Code', required: true, placeholder: 'WC-2026-006' },
    { name: 'client_id', label: 'Client', type: 'select', required: true, options: clients.map((c) => ({ value: c.id, label: c.name })) },
    { name: 'project_type', label: 'Project Type' },
    { name: 'order_date', label: 'Order Date', type: 'date', required: true },
    { name: 'delivery_date', label: 'Delivery Date', type: 'date' },
    { name: 'order_value', label: 'Order Value', type: 'number', required: true },
    { name: 'advance', label: 'Advance', type: 'number' },
    { name: 'priority', label: 'Priority', type: 'select', options: [
      { value: 'Low', label: 'Low' }, { value: 'Medium', label: 'Medium' },
      { value: 'High', label: 'High' }, { value: 'Urgent', label: 'Urgent' },
    ] },
    { name: 'supervisor', label: 'Supervisor' },
    { name: 'site_address', label: 'Site Address', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Orders</h1>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('order-profitability.xlsx')} target="_blank" rel="noreferrer">
            Export Profitability
          </a>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>New Order</button>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={orders} />
      <Modal isOpen={showAdd} title="New Order" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Create Order" />
      </Modal>
    </div>
  );
}

export default OrdersPage;
