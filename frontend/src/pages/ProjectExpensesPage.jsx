import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { projectExpensesAPI, ordersAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { formatCurrency } from '../utils/currency';
import { today } from '../utils/dates';

function ProjectExpensesPage() {
  const { user } = useSelector((state) => state.auth);
  const [expenses, setExpenses] = useState([]);
  const [orders, setOrders] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editingExpense, setEditingExpense] = useState(null);
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

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await projectExpensesAPI.update(editingExpense.id, {
        category: formData.category, description: formData.description, paid_to: formData.paid_to,
        amount: formData.amount, approved_by: formData.approved_by, remarks: formData.remarks,
      });
      setEditingExpense(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update expense');
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
    { key: 'amount', label: 'Amount', render: (v) => formatCurrency(v) },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingExpense(row); }}>Edit</button>
      ),
    },
  ];

  const fields = [
    { name: 'order_id', label: 'Order', type: 'select', required: true, section: 'Project', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'date', label: 'Date', type: 'date', required: true, section: 'Project' },
    { name: 'category', label: 'Category', required: true, section: 'Expense Details' },
    { name: 'description', label: 'Description', section: 'Expense Details' },
    { name: 'amount', label: 'Amount', type: 'number', required: true, section: 'Expense Details' },
    { name: 'paid_to', label: 'Paid To', section: 'Approval' },
    { name: 'approved_by', label: 'Approved By', section: 'Approval' },
  ];

  const editFields = fields.filter((f) => !['expense_code', 'order_id'].includes(f.name)).map(({ section, ...f }) => f);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Project Expenses</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Expense</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={expenses} emptyMessage="No project expenses recorded yet." />
      <Modal isOpen={showAdd} title="Add Expense" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Expense"
          initialValues={{ date: today(), approved_by: user?.full_name || user?.username || '' }} />
      </Modal>
      <Modal isOpen={!!editingExpense} title={`Edit ${editingExpense?.expense_code || ''}`} onClose={() => setEditingExpense(null)}>
        {editingExpense && (
          <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingExpense} />
        )}
      </Modal>
    </div>
  );
}

export default ProjectExpensesPage;
