import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
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
  const isPrivileged = user?.role === 'master';
  const [payments, setPayments] = useState([]);
  const [orders, setOrders] = useState([]);
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingPayment, setEditingPayment] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = () => {
    setPageLoading(true);
    paymentsAPI.list().then((res) => setPayments(res.data)).catch(() => setError('You do not have permission to view payments.')).finally(() => setPageLoading(false));
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
    { key: 'business_id', label: 'Receipt ID', render: (v) => v || '-' },
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

  // Reference-number field is context-aware per payment mode: Cash is
  // system-generated (never user-typed, see backend OrderService), while
  // other modes ask for whatever real-world reference identifies that
  // transaction - the label changes so the user isn't guessing what to enter.
  const referenceFieldFor = (mode) => {
    switch (mode) {
      case 'UPI': return { label: 'UPI Transaction ID', placeholder: 'e.g. 402812345678' };
      case 'Bank Transfer': return { label: 'Bank Reference / UTR Number', placeholder: 'e.g. UTR1234567890' };
      case 'Cheque': return { label: 'Cheque Number', placeholder: 'e.g. 000123' };
      case 'Card': return { label: 'Transaction ID', placeholder: 'e.g. auth code / last 4 digits' };
      default: return { label: 'Reference Number', placeholder: '' };
    }
  };

  const createFields = [
    { name: 'order_id', label: 'Order', type: 'select', required: true, section: 'Client & Order', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'date', label: 'Date', type: 'date', required: true, section: 'Client & Order' },
    { name: 'payment_type', label: 'Payment Type', type: 'select', required: true, section: 'Payment Details', options: [
      { value: 'Advance', label: 'Advance' }, { value: 'Progress Payment', label: 'Progress Payment' }, { value: 'Internal', label: 'Internal' },
    ] },
    { name: 'payment_mode', label: 'Payment Mode', type: 'select', required: true, section: 'Payment Details', options: [
      { value: 'Cash', label: 'Cash' }, { value: 'UPI', label: 'UPI' }, { value: 'Bank Transfer', label: 'Bank Transfer' },
      { value: 'Cheque', label: 'Cheque' }, { value: 'Card', label: 'Card' }, { value: 'Other', label: 'Other' },
    ] },
    { name: 'amount', label: 'Amount', type: 'number', required: true, section: 'Payment Details' },
    {
      // Cash: hidden entirely - the backend generates CASH-YYYYMMDD-001
      // automatically, so there's nothing for the user to type.
      name: 'cash_note', type: 'computed', section: 'Reference',
      label: 'Reference Number',
      hint: 'Generated automatically for cash payments (e.g. CASH-20260812-001) - you do not need to enter one.',
      compute: () => 'Auto-generated on save',
      visibleIf: (fd) => fd.payment_mode === 'Cash',
    },
    {
      name: 'reference_number', section: 'Reference',
      getLabel: (fd) => referenceFieldFor(fd.payment_mode).label,
      visibleIf: (fd) => fd.payment_mode && fd.payment_mode !== 'Cash',
    },
    { name: 'received_by', label: 'Received By', section: 'Reference' },
  ];

  const editFields = createFields
    .filter((f) => !['receipt_code', 'date', 'order_id'].includes(f.name))
    .map(({ section, ...f }) => f);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Payments</h1>
          <p className="page-summary">Record and review payments received against orders.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('payments.xlsx')} target="_blank" rel="noreferrer">Export</a>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Record Payment</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={payments} loading={pageLoading} emptyMessage="No payments recorded yet." />
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
