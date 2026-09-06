import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { dailyTasksAPI, employeesAPI, ordersAPI, reportsAPI } from '../../../utils/api';
import Table from '../../../components/common/Table';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import { today } from '../../../utils/format';

const VIEWS = ['All', 'My Tasks', 'Overdue', 'Doing', 'Done'];

// Practical Woodful task categories, used consistently
// in both task creation and filtering.
const TASK_CATEGORIES = [
  'Design', 'Material Preparation', 'Cutting', 'CNC', 'Laser', 'Assembly',
  'Finishing', 'Installation', 'Procurement', 'Quality Check', 'Workshop',
  'Administration', 'Other',
];

function DailyTasksPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [tasks, setTasks] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [orders, setOrders] = useState([]);
  const [view, setView] = useState('All');
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [formOrderId, setFormOrderId] = useState('');

  // Practical operational filters - "Who is doing
  // what? What's overdue? What's assigned to Pankaj? What belongs to a
  // particular order?" answered without leaving this page.
  const [filterEmployee, setFilterEmployee] = useState('');
  const [filterOrder, setFilterOrder] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterPriority, setFilterPriority] = useState('');
  const [filterProduct, setFilterProduct] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    dailyTasksAPI.list({ include_material_risk: true }).then((res) => setTasks(res.data)).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
    employeesAPI.list().then((res) => setEmployees(res.data));
    ordersAPI.list().then((res) => setOrders(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await dailyTasksAPI.create({
        ...formData,
        employee_id: Number(formData.employee_id),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        order_item_id: formData.order_item_id ? Number(formData.order_item_id) : null,
        date: new Date().toISOString(),
        due_date: formData.due_date ? new Date(formData.due_date).toISOString() : null,
        completion_percent: Number(formData.completion_percent || 0),
      });
      setShowAdd(false);
      setFormOrderId('');
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add task');
    } finally {
      setLoading(false);
    }
  };

  const myEmployeeMatch = (task) => {
    // Resolved via the real User.employee_id link set when the account
    // was created, not by comparing names - two people can share a
    // name, and a display-name edit would otherwise silently break this.
    return user?.employee_id != null && task.employee_id === user.employee_id;
  };

  const isOverdue = (task) => {
    if (task.status === 'DONE') return false;
    const dueDate = task.due_date ? new Date(task.due_date) : new Date(task.date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return dueDate < today;
  };

  const filteredTasks = tasks.filter((t) => {
    if (view === 'My Tasks' && !myEmployeeMatch(t)) return false;
    if (view === 'Overdue' && !isOverdue(t)) return false;
    if (view === 'Doing' && t.status !== 'DOING') return false;
    if (view === 'Done' && t.status !== 'DONE') return false;
    if (filterEmployee && String(t.employee_id) !== String(filterEmployee)) return false;
    if (filterOrder && String(t.order_id) !== String(filterOrder)) return false;
    if (filterCategory && t.task_category !== filterCategory) return false;
    if (filterPriority && t.priority !== filterPriority) return false;
    if (filterProduct && t.product_name !== filterProduct) return false;
    if (filterDateFrom && (!t.due_date || t.due_date.slice(0, 10) < filterDateFrom)) return false;
    if (filterDateTo && (!t.due_date || t.due_date.slice(0, 10) > filterDateTo)) return false;
    return true;
  });

  // Product/Order Item filter options - derived from the already-loaded
  // tasks' own denormalized product_name (no separate product list
  // needed, matches whatever's actually assigned across current tasks).
  const productOptions = useMemo(
    () => [...new Set(tasks.map((t) => t.product_name).filter(Boolean))].sort(),
    [tasks],
  );

  const columns = [
    { key: 'task_code', label: 'Task ID' },
    { key: 'employee_id', label: 'Employee', render: (v, row) => row.employee_name || employees.find((e) => e.id === v)?.name || v },
    {
      key: 'order_id', label: 'Client / Order',
      render: (v, row) => v ? (
        <>
          {row.client_name ? row.client_name + ' \u2013 ' : ''}{row.order_code || orders.find((o) => o.id === v)?.order_code || '-'}
          {row.material_at_risk && <span className="status-badge status-danger" style={{ marginLeft: 6 }}>Material Short</span>}
        </>
      ) : '-',
    },
    { key: 'product_name', label: 'Product', render: (v) => v || '-' },
    { key: 'task_description', label: 'Task' },
    { key: 'task_category', label: 'Category', render: (v) => v || '-' },
    { key: 'priority', label: 'Priority' },
    { key: 'due_date', label: 'Due', render: (v) => (v ? new Date(v).toLocaleDateString() : '-') },
    { key: 'status', label: 'Status' }, { key: 'completion_percent', label: 'Completion %' },
  ];

  const selectedOrder = useMemo(() => orders.find((o) => String(o.id) === String(formOrderId)), [orders, formOrderId]);

  const fields = [
    {
      name: 'order_id', label: 'Order / Project', type: 'select',
      options: orders.map((o) => ({
        value: o.id,
        label: [o.client?.name, o.project_type, o.order_code].filter(Boolean).join(' \u2013 '),
      })),
      getHint: () => (selectedOrder?.delivery_date ? `Due date will default to the order's delivery date: ${new Date(selectedOrder.delivery_date).toLocaleDateString()}` : undefined),
    },
    {
      name: 'order_item_id', label: 'Order Item / Product', type: 'select',
      visibleIf: () => !!selectedOrder,
      options: (selectedOrder?.items || []).map((it) => ({ value: it.id, label: it.product_name || it.description })),
    },
    { name: 'employee_id', label: 'Assign To', type: 'select', required: true, options: employees.map((e) => ({ value: e.id, label: e.name })) },
    { name: 'task_description', label: 'Work', required: true, type: 'textarea', placeholder: 'e.g. Add channels to drawers' },
    {
      name: 'due_date', label: 'Due', type: 'date', advanced: true,
      hint: 'Leave blank to inherit the order\u2019s delivery date. Enter a date here to override it for this task only.',
    },
    { name: 'priority', label: 'Priority', type: 'select', advanced: true, options: [
      { value: 'Low', label: 'Low' }, { value: 'Normal', label: 'Normal' },
      { value: 'High', label: 'High' }, { value: 'Urgent', label: 'Urgent' },
    ] },
    { name: 'task_category', label: 'Category (optional)', type: 'select', advanced: true, options: TASK_CATEGORIES.map((c) => ({ value: c, label: c })) },
    { name: 'checked_by', label: 'Checked By', advanced: true },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Tasks</h1>
          <p className="page-summary">Assign and track daily work across the workshop.</p>
        </div>
        <div className="page-actions">
          <a
            className="btn-secondary"
            href={reportsAPI.downloadUrl(
              view === 'My Tasks' && user?.employee_id
                ? `tasks.xlsx?employee_id=${user.employee_id}`
                : 'tasks.xlsx'
            )}
            target="_blank" rel="noreferrer"
          >
            {view === 'My Tasks' ? 'Export My Tasks' : 'Export Tasks & Production'}
          </a>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Assign Task</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <div className="tab-bar">
        {VIEWS.map((v) => (
          <button key={v} className={view === v ? 'tab active' : 'tab'} onClick={() => setView(v)}>{v}</button>
        ))}
      </div>
      <div className="filter-bar" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <select className="form-input" value={filterEmployee} onChange={(e) => setFilterEmployee(e.target.value)}>
          <option value="">All Employees</option>
          {employees.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
        <select className="form-input" value={filterOrder} onChange={(e) => setFilterOrder(e.target.value)}>
          <option value="">All Orders</option>
          {orders.map((o) => <option key={o.id} value={o.id}>{o.order_code}</option>)}
        </select>
        <select className="form-input" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
          <option value="">All Categories</option>
          {TASK_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="form-input" value={filterPriority} onChange={(e) => setFilterPriority(e.target.value)}>
          <option value="">All Priorities</option>
          {['Low', 'Normal', 'High', 'Urgent'].map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select className="form-input" value={filterProduct} onChange={(e) => setFilterProduct(e.target.value)}>
          <option value="">All Products</option>
          {productOptions.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <input
          className="form-input" type="date" value={filterDateFrom} title="Due date from"
          onChange={(e) => setFilterDateFrom(e.target.value)}
        />
        <input
          className="form-input" type="date" value={filterDateTo} title="Due date to"
          onChange={(e) => setFilterDateTo(e.target.value)}
        />
      </div>
      <Table
        columns={columns} data={filteredTasks} loading={pageLoading} error={loadError} onRetry={load}
        onRowClick={(row) => navigate(`/daily-tasks/${row.id}`)}
        emptyMessage={
          view === 'Overdue' ? "Nothing overdue - you're on top of it."
          : view === 'My Tasks' ? 'No work assigned to you right now.'
          : view === 'Doing' ? 'Nothing in progress at the moment.'
          : view === 'Done' ? 'Nothing completed in this view yet.'
          : 'No tasks yet. Assign the first one to get started.'
        }
      />
      {isPrivileged && (
        <Modal isOpen={showAdd} title="Assign Task" onClose={() => { setShowAdd(false); setFormOrderId(''); }}>
          <Form
            fields={fields} onSubmit={handleCreate} loading={loading} submitText="Assign Task"
            onFieldChange={(name, value) => { if (name === 'order_id') setFormOrderId(value); }}
            initialValues={{ checked_by: user?.full_name || user?.username || '', priority: 'Normal' }}
          />
        </Modal>
      )}
    </div>
  );
}

export default DailyTasksPage;
