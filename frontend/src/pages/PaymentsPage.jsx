import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { paymentsAPI, ordersAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { formatCurrency } from '../utils/currency';
import { today } from '../utils/dates';

function PaymentsPage() {
  const { user } = useSelector((state) => state.auth);
  const isTrueMaster = user?.role === 'master';
  const [payments, setPayments] = useState([]);
  const [orders, setOrders] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editingPayment, setEditingPayment] = useState(null);
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

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await paymentsAPI.update(editingPayment.id, {
        payment_type: formData.payment_type, payment_mode: formData.payment_mode,
        amount: formData.amount, reference_number: formData.reference_number,
        received_by: formData.received_by, remarks: formData.remarks,
      });
      setEditingPayment(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update payment');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'receipt_code', label: 'Receipt ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'order_id', label: 'Order', render: (v) => orders.find((o) => o.id === v)?.order_code || v },
    { key: 'payment_type', label: 'Payment Type' }, { key: 'payment_mode', label: 'Payment Mode' },
    { key: 'amount', label: 'Amount', render: (v) => formatCurrency(v) },
    { key: 'reference_number', label: 'Reference No.' }, { key: 'received_by', label: 'Received By' },
    {
      key: 'invoice_action', label: '', render: (v, row) => (
        <a href={reportsAPI.downloadUrl(`orders/${row.order_id}/invoice.pdf`)} target="_blank" rel="noreferrer">Invoice</a>
      ),
    },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isTrueMaster && <button className="btn-link" onClick={() => setEditingPayment(row)}>Edit</button>
      ),
    },
  ];

  const createFields = [
    { name: 'order_id', label: 'Order', type: 'select', required: true, section: 'Client & Order', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'date', label: 'Date', type: 'date', required: true, section: 'Client & Order' },
    { name: 'payment_type', label: 'Payment Type', type: 'select', required: true, section: 'Payment Details', options: [
      { value: 'Advance', label: 'Advance' }, { value: 'Progress Payment', label: 'Progress Payment' }, { value: 'Internal', label: 'Internal' },
    ] },
    { name: 'payment_mode', label: 'Payment Mode', type: 'select', required: true, section: 'Payment Details', options: [
      { value: 'Cash', label: 'Cash' }, { value: 'UPI', label: 'UPI' }, { value: 'Bank', label: 'Bank' }, { value: 'Credit Card', label: 'Credit Card' },
    ] },
    { name: 'amount', label: 'Amount', type: 'number', required: true, section: 'Payment Details' },
    { name: 'reference_number', label: 'Reference No.', section: 'Reference' },
    { name: 'received_by', label: 'Received By', section: 'Reference' },
  ];

  const editFields = createFields
    .filter((f) => !['receipt_code', 'date', 'order_id'].includes(f.name))
    .map(({ section, ...f }) => f);

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
      <Table columns={columns} data={payments} emptyMessage="No payments recorded yet." />
      <Modal isOpen={showAdd} title="Record Payment" onClose={() => setShowAdd(false)}>
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Record Payment"
          initialValues={{ date: today(), received_by: user?.full_name || user?.username || '' }} />
      </Modal>
      <Modal isOpen={!!editingPayment} title={`Edit ${editingPayment?.receipt_code || ''}`} onClose={() => setEditingPayment(null)}>
        {editingPayment && (
          <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingPayment} />
        )}
      </Modal>
    </div>
  );
}

export default PaymentsPage;
