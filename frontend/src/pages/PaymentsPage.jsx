import React, { useEffect, useState } from 'react';
import { paymentsAPI, ordersAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function PaymentsPage() {
  const [payments, setPayments] = useState([]);
  const [orders, setOrders] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => {
    paymentsAPI.list().then((res) => setPayments(res.data)).catch(() => setError('You do not have permission to view payments.'));
    ordersAPI.list().then((res) => setOrders(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await paymentsAPI.create({
        ...formData,
        order_id: Number(formData.order_id),
        date: new Date(formData.date).toISOString(),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record payment');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'receipt_code', label: 'Receipt ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'order_id', label: 'Order', render: (v) => orders.find((o) => o.id === v)?.order_code || v },
    { key: 'payment_type', label: 'Payment Type' }, { key: 'payment_mode', label: 'Payment Mode' },
    { key: 'amount', label: 'Amount', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'reference_number', label: 'Reference No.' }, { key: 'received_by', label: 'Received By' },
  ];

  const fields = [
    { name: 'receipt_code', label: 'Receipt Code', required: true, placeholder: 'RCPT-008' },
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'order_id', label: 'Order', type: 'select', required: true, options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'payment_type', label: 'Payment Type', type: 'select', required: true, options: [
      { value: 'Advance', label: 'Advance' }, { value: 'Progress Payment', label: 'Progress Payment' }, { value: 'Internal', label: 'Internal' },
    ] },
    { name: 'payment_mode', label: 'Payment Mode', type: 'select', required: true, options: [
      { value: 'Cash', label: 'Cash' }, { value: 'UPI', label: 'UPI' }, { value: 'Bank', label: 'Bank' }, { value: 'Credit Card', label: 'Credit Card' },
    ] },
    { name: 'amount', label: 'Amount', type: 'number', required: true },
    { name: 'reference_number', label: 'Reference No.' },
    { name: 'received_by', label: 'Received By' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Payments</h1>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('payments.xlsx')} target="_blank" rel="noreferrer">Export</a>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>Record Payment</button>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={payments} />
      <Modal isOpen={showAdd} title="Record Payment" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Record Payment" />
      </Modal>
    </div>
  );
}

export default PaymentsPage;
