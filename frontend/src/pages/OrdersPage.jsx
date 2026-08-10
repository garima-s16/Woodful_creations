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
  const [statusOrder, setStatusOrder] = useState(null);
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

  const handleStatusUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await ordersAPI.update(statusOrder.id, {
        project_status: formData.project_status,
        design_status: formData.design_status,
        execution_status: formData.execution_status,
        delivery_status: formData.delivery_status,
        progress_percent: Number(formData.progress_percent),
      });
      setStatusOrder(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update status');
    } finally {
      setLoading(false);
    }
  };

  const STAGE_OPTIONS = ['Enquiry', 'Designing', 'Approved', 'Material Purchase', 'Cutting', 'Edge Banding',
    'Assembly', 'Painting', 'Ready for Dispatch', 'Installation', 'Completed', 'On Hold']
    .map((s) => ({ value: s, label: s }));
  const SIMPLE_STATUS_OPTIONS = ['Pending', 'In Progress', 'Completed'].map((s) => ({ value: s, label: s }));

  const columns = [
    { key: 'order_code', label: 'Order ID' },
    { key: 'client_id', label: 'Client', render: (v) => clients.find((c) => c.id === v)?.name || v },
    { key: 'project_type', label: 'Project Type' },
    { key: 'order_value', label: 'Order Value', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'total_received', label: 'Received', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'balance', label: 'Balance', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'project_status', label: 'Stage' }, { key: 'progress_percent', label: 'Progress %' },
    { key: 'design_status', label: 'Design' }, { key: 'execution_status', label: 'Execution' },
    { key: 'delivery_status', label: 'Delivery' },
    {
      key: 'estimate_pdf', label: 'Estimate', render: (v, row) => (
        <a href={reportsAPI.downloadUrl(`orders/${row.id}/estimate.pdf`)} target="_blank" rel="noreferrer">Download PDF</a>
      ),
    },
    {
      key: 'status_action', label: 'Status', render: (v, row) => (
        <button className="btn-link" onClick={() => setStatusOrder(row)}>Update Status</button>
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

      <Modal isOpen={!!statusOrder} title={`Update Status - ${statusOrder?.order_code || ''}`} onClose={() => setStatusOrder(null)}>
        {statusOrder && (
          <Form
            fields={[
              { name: 'project_status', label: 'Overall Stage', type: 'select', required: true, options: STAGE_OPTIONS },
              { name: 'design_status', label: 'Design Status', type: 'select', required: true, options: SIMPLE_STATUS_OPTIONS },
              { name: 'execution_status', label: 'Execution Status', type: 'select', required: true, options: SIMPLE_STATUS_OPTIONS },
              { name: 'delivery_status', label: 'Delivery Status', type: 'select', required: true, options: SIMPLE_STATUS_OPTIONS },
              { name: 'progress_percent', label: 'Progress %', type: 'number', required: true },
            ]}
            onSubmit={handleStatusUpdate}
            loading={loading}
            submitText="Update Status"
            initialValues={{
              project_status: statusOrder.project_status,
              design_status: statusOrder.design_status,
              execution_status: statusOrder.execution_status,
              delivery_status: statusOrder.delivery_status,
              progress_percent: statusOrder.progress_percent,
            }}
          />
        )}
      </Modal>
    </div>
  );
}

export default OrdersPage;
