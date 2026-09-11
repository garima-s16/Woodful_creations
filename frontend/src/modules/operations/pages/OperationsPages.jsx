// Operations pages: daily tasks, task detail, issues, and project
// expenses. Combines the former DailyTasksPage.jsx, TaskDetailPage.jsx,
// IssuesPage.jsx, and ProjectExpensesPage.jsx.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { dailyTasksAPI, employeesAPI, issuesAPI, locationsAPI, materialsAPI, ordersAPI, projectExpensesAPI, reportsAPI } from '../../../utils/api';
import { Alert, Card, Form, Modal, Table } from '../../../components/common/UI';
import { classifyLoadError, formatCurrency, statusClass, today } from '../../../utils/utils';

// --- DailyTasksPage.jsx ---
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

// --- TaskDetailPage.jsx ---
// Same category list as
// DailyTasksPage.jsx's creation form, not a second one.


function TaskDetailPage() {
  const { taskId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [task, setTask] = useState(null);
  const [employee, setEmployee] = useState(null);
  const [order, setOrder] = useState(null);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [comments, setComments] = useState([]);
  const [commentsError, setCommentsError] = useState(false);
  const [newComment, setNewComment] = useState('');
  const [showAssignNext, setShowAssignNext] = useState(false);
  const [showEditTask, setShowEditTask] = useState(false);
  const [employees, setEmployees] = useState([]);
  const [orders, setOrders] = useState([]);
  // Tracks the order currently selected WITHIN the edit form (may
  // differ from task.order_id while the form is open, before saving) -
  // drives which Order Items are offered, same pattern as
  // DailyTasksPage.jsx's formOrderId for task creation (item 9).
  const [editOrderId, setEditOrderId] = useState('');

  const load = useCallback(() => {
    setLoadError(null);
    dailyTasksAPI.get(taskId).then((res) => {
      setTask(res.data);
      if (res.data.employee_id) employeesAPI.get(res.data.employee_id).then((r) => setEmployee(r.data)).catch(() => setEmployee('error'));
      if (res.data.order_id) ordersAPI.get(res.data.order_id).then((r) => setOrder(r.data)).catch(() => setOrder('error'));
    }).catch((err) => setLoadError(classifyLoadError(err, 'task')));
    setCommentsError(false);
    dailyTasksAPI.listComments(taskId).then((res) => setComments(res.data)).catch(() => { setComments([]); setCommentsError(true); });
  }, [taskId]);

  useEffect(load, [load]);

  // Employees/orders lists are reference data for the reassign/relink
  // dropdowns, not specific to this task - fetched once per page visit
  // rather than on every load() call.
  useEffect(() => {
    employeesAPI.list().then((res) => setEmployees(res.data)).catch(() => setEmployees([]));
    ordersAPI.list().then((res) => setOrders(res.data)).catch(() => setOrders([]));
  }, []);

  const handleAddComment = async (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    try {
      await dailyTasksAPI.addComment(taskId, { text: newComment.trim() });
      setNewComment('');
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add comment');
    }
  };

  const handleAssignNext = async (formData) => {
    setLoading(true);
    setError('');
    try {
      const next = await dailyTasksAPI.completeAndAssignNext(taskId, {
        next_employee_id: Number(formData.next_employee_id),
        next_task_description: formData.next_task_description,
        // Empty string, not just undefined, means "leave blank" here -
        // send null so the backend's Optional[datetime] inherits the
        // current task's due date instead of rejecting
        // an empty string as an invalid datetime.
        next_due_date: formData.next_due_date ? new Date(formData.next_due_date).toISOString() : null,
        next_priority: formData.next_priority || undefined,
        note: formData.note,
      });
      setShowAssignNext(false);
      // The existing route is /daily-tasks/<id>, not
      // /tasks/<id> (there is no /tasks route - see App.jsx). This was
      // sending Complete & Assign Next to a 404.
      window.location.href = `/daily-tasks/${next.data.id}`;
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to complete and assign next action');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      const payload = isPrivileged
        ? {
            status: formData.status, completion_percent: Number(formData.completion_percent || 0),
            delay_reason: formData.delay_reason, remarks: formData.remarks,
          }
        // The backend already allows a normal user to
        // update status/completion_percent/delay_reason/remarks on their
        // own task (EMPLOYEE_SELF_SERVICE_FIELDS in daily_tasks.py); this
        // was only sending status/delay_reason, silently dropping the
        // other two fields the person had just filled in.
        : {
            status: formData.status, completion_percent: Number(formData.completion_percent || 0),
            delay_reason: formData.delay_reason, remarks: formData.remarks,
          };
      await dailyTasksAPI.update(task.id, payload);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update task');
    } finally {
      setLoading(false);
    }
  };

  const handleEditTask = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await dailyTasksAPI.update(task.id, {
        employee_id: Number(formData.employee_id),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        order_item_id: formData.order_item_id ? Number(formData.order_item_id) : null,
        task_description: formData.task_description,
        task_category: formData.task_category || null,
        priority: formData.priority || null,
        date: formData.date ? new Date(formData.date).toISOString() : undefined,
        planned_start: formData.planned_start || null,
        planned_end: formData.planned_end || null,
        // Sending due_date only when the Master actually changed it -
        // an empty/unchanged value here must NOT be interpreted by the
        // backend as "clear the due date" (see daily_tasks.py: any
        // due_date key present at all is treated as an explicit
        // override decision).
        ...(formData.due_date ? { due_date: new Date(formData.due_date).toISOString() } : {}),
        status: formData.status,
        completion_percent: Number(formData.completion_percent || 0),
        delay_reason: formData.delay_reason || null,
        remarks: formData.remarks || null,
        checked_by: formData.checked_by || null,
      });
      setShowEditTask(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save changes');
    } finally {
      setLoading(false);
    }
  };

  const isOwnTask = task?.employee_id != null && user?.employee_id === task.employee_id;
  const canHandoff = isPrivileged || isOwnTask;

  if (loadError) return (
    <div className="page">
      <Alert type="error" message={loadError.message} />
      {!loadError.isNotFound && (
        <button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button>
      )}
    </div>
  );
  if (!task) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/daily-tasks" className="btn-link">&larr; Back to Tasks</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{task.task_code}</h1>
          <div className="detail-subtitle">{task.task_description}</div>
          <div className="detail-meta">
            <div className="detail-meta-item">
              <span className="detail-meta-label">Status</span>
              <span className={`status-badge ${statusClass(task.status)}`}>{task.status}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Priority</span>
              <span className="detail-meta-value">{task.priority || '-'}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Completion</span>
              <span className="detail-meta-value">{task.completion_percent}%</span>
            </div>
          </div>
        </div>
        <div className="detail-header-actions">
          {isPrivileged && <button className="btn-secondary" onClick={() => { setEditOrderId(task.order_id ? String(task.order_id) : ''); setShowEditTask(true); }}>Edit Task</button>}
          {canHandoff && <button className="btn-secondary" onClick={() => setShowAssignNext(true)}>Complete &amp; Assign Next</button>}
        </div>
      </div>

      <div className="dashboard-grid">
        <Card title="Task Details">
          <div className="card-body">
            <div className="detail-meta">
              {/* Only the
                  fields the spec calls "immediately visible": Client,
                  Order, Product, Assigned To, Task Date, Due Date.
                  Everything else moves to Additional Details below.
                  Never duplicated onto DailyTask itself - always the
                  live client_name/product_name the backend derives
                  from Order/OrderItem at response time. */}
              {task.client_name && <div className="detail-meta-item"><span className="detail-meta-label">Client</span><span className="detail-meta-value">{task.client_name}</span></div>}
              <div className="detail-meta-item"><span className="detail-meta-label">Order</span><span className="detail-meta-value">{order === 'error' ? 'Unavailable' : order ? <Link to={`/orders/${order.id}`}>{order.order_code}</Link> : '-'}</span></div>
              {task.product_name && <div className="detail-meta-item"><span className="detail-meta-label">Product</span><span className="detail-meta-value">{task.product_name}</span></div>}
              <div className="detail-meta-item"><span className="detail-meta-label">Assigned To</span><span className="detail-meta-value">{employee === 'error' ? 'Unavailable' : employee ? <Link to={`/employees/${employee.id}`}>{employee.name}</Link> : '-'}</span></div>
              {/* Task Date (when it's assigned/planned) vs Due Date (the
                  deadline) are kept visually distinct per B9. */}
              <div className="detail-meta-item"><span className="detail-meta-label">Task Date</span><span className="detail-meta-value">{new Date(task.date).toLocaleDateString()}</span></div>
              <div className="detail-meta-item">
                <span className="detail-meta-label">Due Date</span>
                <span className="detail-meta-value">
                  {task.due_date ? new Date(task.due_date).toLocaleDateString() : '-'}
                  {task.due_date_overridden && <span className="business-id-badge" style={{ marginLeft: 6 }}>Overridden</span>}
                </span>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Additional Details">
          <div className="card-body">
            <div className="detail-meta">
              {task.task_category && <div className="detail-meta-item"><span className="detail-meta-label">Category</span><span className="detail-meta-value">{task.task_category}</span></div>}
              {task.planned_start && <div className="detail-meta-item"><span className="detail-meta-label">Planned Start</span><span className="detail-meta-value">{task.planned_start}</span></div>}
              {task.planned_end && <div className="detail-meta-item"><span className="detail-meta-label">Planned End</span><span className="detail-meta-value">{task.planned_end}</span></div>}
              {task.checked_by && <div className="detail-meta-item"><span className="detail-meta-label">Checked By</span><span className="detail-meta-value">{task.checked_by}</span></div>}
              {task.delay_reason && <div className="detail-meta-item"><span className="detail-meta-label">Delay / Block Reason</span><span className="detail-meta-value">{task.delay_reason}</span></div>}
              {task.remarks && <div className="detail-meta-item"><span className="detail-meta-label">Remarks</span><span className="detail-meta-value">{task.remarks}</span></div>}
              {task.previous_task_id && <div className="detail-meta-item"><span className="detail-meta-label">Handed Off From</span><span className="detail-meta-value"><Link to={`/daily-tasks/${task.previous_task_id}`}>View previous task</Link></span></div>}
              {!task.task_category && !task.planned_start && !task.planned_end && !task.checked_by && !task.delay_reason && !task.remarks && !task.previous_task_id && (
                <p className="page-summary" style={{ margin: 0 }}>Nothing additional recorded yet.</p>
              )}
            </div>
          </div>
        </Card>

        <Card title="Update Progress">
          <div className="card-body">
            {error && <Alert type="error" message={error} onClose={() => setError('')} />}
            <Form
              fields={(() => {
                const statusField = { name: 'status', label: 'Status', type: 'select', required: true, options: [
                  { value: 'TO DO', label: 'To Do' }, { value: 'DOING', label: 'Doing' },
                  { value: 'DONE', label: 'Done' }, { value: 'BLOCKED', label: 'Blocked' },
                ] };
                const delayField = { name: 'delay_reason', label: 'Block Reason (if Blocked)' };
                return isPrivileged
                  ? [
                      statusField,
                      { name: 'completion_percent', label: 'Completion %', type: 'number', required: true },
                      delayField,
                      { name: 'remarks', label: 'Remarks', type: 'textarea' },
                    ]
                  // Same self-service field set the
                  // backend actually allows for a normal user's own task.
                  : [
                      statusField,
                      { name: 'completion_percent', label: 'Completion %', type: 'number', required: true },
                      delayField,
                      { name: 'remarks', label: 'Remarks', type: 'textarea' },
                    ];
              })()}
              onSubmit={handleUpdate}
              loading={loading}
              submitText="Save Progress"
              initialValues={{
                status: task.status, completion_percent: task.completion_percent,
                delay_reason: task.delay_reason || '', remarks: task.remarks || '',
              }}
            />
          </div>
        </Card>
      </div>

      <Card title="Comments">
        <div className="card-body">
          {commentsError && (
            <p className="page-summary">
              Unable to load comments.{' '}
              <button type="button" className="btn-link" onClick={load}>Retry</button>
            </p>
          )}
          {!commentsError && comments.length === 0 && <p className="page-summary">No comments yet.</p>}
          {comments.map((c) => (
            <div key={c.id} className="detail-meta-item" style={{ marginBottom: 12 }}>
              <span className="detail-meta-label">{c.author} &middot; {new Date(c.date).toLocaleDateString()}</span>
              <span className="detail-meta-value">{c.text}</span>
            </div>
          ))}
          <form onSubmit={handleAddComment} style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <input
              className="form-input" style={{ flex: 1 }} placeholder="Add a comment"
              value={newComment} onChange={(e) => setNewComment(e.target.value)}
            />
            <button type="submit" className="btn-secondary">Post</button>
          </form>
        </div>
      </Card>

      {isPrivileged && (() => {
        const editSelectedOrder = orders.find((o) => String(o.id) === String(editOrderId));
        return (
          <Modal isOpen={showEditTask} title={`Edit ${task.task_code}`} onClose={() => setShowEditTask(false)}>
            <Form
              fields={[
                { name: 'employee_id', label: 'Assign To', type: 'select', required: true, options: employees.map((e) => ({ value: e.id, label: e.name })) },
                { name: 'task_description', label: 'Work', required: true, type: 'textarea' },
                { name: 'date', label: 'Task Date', type: 'date', required: true },
                { name: 'status', label: 'Status', type: 'select', required: true, options: [
                  { value: 'TO DO', label: 'To Do' }, { value: 'DOING', label: 'Doing' },
                  { value: 'DONE', label: 'Done' }, { value: 'BLOCKED', label: 'Blocked' },
                ] },
                { name: 'completion_percent', label: 'Completion %', type: 'number' },
                { name: 'due_date', label: 'Due Date', type: 'date',
                  hint: 'Leave as-is to keep the current due date. Changing this sets an explicit override that won\u2019t be replaced by a later Order date change.' },
                {
                  name: 'order_id', label: 'Order / Project', type: 'select', advanced: true,
                  options: orders.map((o) => ({
                    value: o.id,
                    label: [o.client?.name, o.project_type, o.order_code].filter(Boolean).join(' \u2013 '),
                  })),
                  getHint: () => (editSelectedOrder?.delivery_date
                    ? `Order delivery date: ${new Date(editSelectedOrder.delivery_date).toLocaleDateString()}. Leave Due below unchanged to keep the task's current due date.`
                    : undefined),
                },
                {
                  name: 'order_item_id', label: 'Order Item / Product', type: 'select', advanced: true,
                  visibleIf: () => !!editSelectedOrder,
                  options: (editSelectedOrder?.items || []).map((it) => ({ value: it.id, label: it.product_name || it.description })),
                },
                { name: 'task_category', label: 'Category', type: 'select', advanced: true, options: TASK_CATEGORIES.map((c) => ({ value: c, label: c })) },
                { name: 'priority', label: 'Priority', type: 'select', advanced: true, options: [
                  { value: 'Low', label: 'Low' }, { value: 'Normal', label: 'Normal' },
                  { value: 'High', label: 'High' }, { value: 'Urgent', label: 'Urgent' },
                ] },
                { name: 'planned_start', label: 'Planned Start', type: 'time', advanced: true },
                { name: 'planned_end', label: 'Planned End', type: 'time', advanced: true },
                { name: 'delay_reason', label: 'Delay / Block Reason', advanced: true },
                { name: 'remarks', label: 'Remarks', type: 'textarea', advanced: true },
                { name: 'checked_by', label: 'Checked By', advanced: true },
              ]}
              onSubmit={handleEditTask}
              loading={loading}
              submitText="Save Changes"
              onFieldChange={(name, value) => { if (name === 'order_id') setEditOrderId(value); }}
              initialValues={{
                employee_id: task.employee_id, order_id: task.order_id || '', order_item_id: task.order_item_id || '',
                task_description: task.task_description, task_category: task.task_category || '',
                priority: task.priority || '', date: task.date ? task.date.slice(0, 10) : '',
                due_date: task.due_date ? task.due_date.slice(0, 10) : '',
                planned_start: task.planned_start || '', planned_end: task.planned_end || '',
                status: task.status, completion_percent: task.completion_percent,
                delay_reason: task.delay_reason || '', remarks: task.remarks || '', checked_by: task.checked_by || '',
              }}
            />
          </Modal>
        );
      })()}

      <Modal isOpen={showAssignNext && canHandoff} title="Complete & Assign Next" onClose={() => setShowAssignNext(false)}>
        <Form
          fields={[
            { name: 'next_employee_id', label: 'Next Person', type: 'select', required: true,
              options: employees.map((e) => ({ value: e.id, label: e.name })) },
            { name: 'next_task_description', label: 'Next Action', required: true },
            { name: 'next_due_date', label: 'Due Date', type: 'date',
              hint: `Leave blank to keep this task's due date${task.due_date ? ` (${new Date(task.due_date).toLocaleDateString()})` : ''}.` },
            { name: 'next_priority', label: 'Priority', type: 'select', options: [
              { value: 'Low', label: 'Low' }, { value: 'Normal', label: 'Normal' },
              { value: 'High', label: 'High' }, { value: 'Urgent', label: 'Urgent' },
            ] },
            { name: 'note', label: 'Note (optional)', type: 'textarea' },
          ]}
          onSubmit={handleAssignNext}
          loading={loading}
          submitText="Complete & Assign Next"
        />
      </Modal>
    </div>
  );
}

// --- IssuesPage.jsx ---
function IssuesPage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const routeLocation = useLocation();
  const [issues, setIssues] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [orders, setOrders] = useState([]);
  const [locations, setLocations] = useState([]);
  // Lets other pages (Inventory's "Issue Stock" quick action) open
  // this same existing create form pre-filled, instead of
  // building a second issue-creation UI - mirrors the pattern already
  // used by PurchasesPage's location.state?.openCreate/prefill.
  const [showAdd, setShowAdd] = useState(!!routeLocation.state?.openCreate);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    issuesAPI.list().then((res) => setIssues(res.data)).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
    materialsAPI.list().then((res) => setMaterials(res.data));
    ordersAPI.list().then((res) => setOrders(res.data));
    locationsAPI.list().then((res) => setLocations(res.data)).catch(() => setLocations([]));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await issuesAPI.create({
        ...formData,
        material_id: Number(formData.material_id),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        location_id: formData.location_id ? Number(formData.location_id) : null,
        date: new Date(formData.date).toISOString(),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record issue');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'issue_code', label: 'Issue ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'order_id', label: 'Order', render: (v) => orders.find((o) => o.id === v)?.order_code || '-' },
    { key: 'material_id', label: 'Material', render: (v) => materials.find((m) => m.id === v)?.name || v },
    { key: 'quantity_issued', label: 'Quantity' }, { key: 'unit', label: 'Unit' },
    { key: 'issued_to', label: 'Issued To' }, { key: 'department', label: 'Department' },
  ];

  const fields = [
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'material_id', label: 'Material', type: 'select', required: true, options: materials.map((m) => ({ value: m.id, label: `${m.name} (${m.current_stock} in stock)` })) },
    { name: 'order_id', label: 'Order (Project)', type: 'select', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'quantity_issued', label: 'Quantity Issued', type: 'number', required: true },
    { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets' },
    { name: 'location_id', label: 'Issue From Location', type: 'select', options: locations.map((l) => ({ value: l.id, label: l.full_path })), placeholder: 'Primary location' },
    { name: 'issued_to', label: 'Issued To' },
    { name: 'department', label: 'Department' },
    { name: 'purpose', label: 'Purpose' },
    { name: 'approved_by', label: 'Approved By' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Issues (Stock Out)</h1>
          <p className="page-summary">Record materials issued from stock for production and project use.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('issues.xlsx')} target="_blank" rel="noreferrer">Export</a>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Record Issue</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={issues} loading={pageLoading} error={loadError} onRetry={load} emptyMessage="No materials issued yet. Issued materials will appear here." />
      <Modal isOpen={showAdd} title="Record Issue" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Record Issue"
          initialValues={{ date: today(), ...(routeLocation.state?.prefill || {}) }} />
      </Modal>
    </div>
  );
}

// --- ProjectExpensesPage.jsx ---
function ProjectExpensesPage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [expenses, setExpenses] = useState([]);
  const [orders, setOrders] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editingExpense, setEditingExpense] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    projectExpensesAPI.list().then((res) => setExpenses(res.data)).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view expenses.' : 'Unable to load expenses. Please try again.');
    }).finally(() => setPageLoading(false));
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
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingExpense(row); }}>Edit</button> : null
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
        <div>
          <h1>Project Expenses</h1>
          <p className="page-summary">Track costs recorded against each project, separate from material purchases.</p>
        </div>
        {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Expense</button>}
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={expenses} loading={pageLoading} error={loadError} onRetry={load} emptyMessage="No project expenses recorded yet." />
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

export { DailyTasksPage, TaskDetailPage, IssuesPage, ProjectExpensesPage };
