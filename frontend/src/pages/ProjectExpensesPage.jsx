import React, { useEffect, useState } from 'react';
import { projectExpensesAPI, ordersAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function ProjectExpensesPage() {
  const [expenses, setExpenses] = useState([]);
  const [orders, setOrders] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => {
    projectExpensesAPI.list().then((res) => setExpenses(res.data)).catch(() => setError('You do not have permission to view expenses.'));
    ordersAPI.list().then((res) => setOrders(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await projectExpensesAPI.create({
        ...formData,
        order_id: Number(formData.order_id),
        date: new Date(formData.date).toISOString(),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add expense');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'expense_code', label: 'Expense ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'order_id', label: 'Order', render: (v) => orders.find((o) => o.id === v)?.order_code || v },
    { key: 'category', label: 'Category' }, { key: 'description', label: 'Description' },
    { key: 'paid_to', label: 'Paid To' },
    { key: 'amount', label: 'Amount', render: (v) => `Rs ${Number(v).toLocaleString()}` },
  ];

  const fields = [
    { name: 'expense_code', label: 'Expense Code', required: true, placeholder: 'EXP-008' },
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'order_id', label: 'Order', type: 'select', required: true, options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'category', label: 'Category', required: true },
    { name: 'description', label: 'Description' },
    { name: 'paid_to', label: 'Paid To' },
    { name: 'amount', label: 'Amount', type: 'number', required: true },
    { name: 'approved_by', label: 'Approved By' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Project Expenses</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Expense</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={expenses} />
      <Modal isOpen={showAdd} title="Add Expense" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Expense" />
      </Modal>
    </div>
  );
}

export default ProjectExpensesPage;
