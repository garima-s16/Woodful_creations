import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { dailyTasksAPI, employeesAPI, ordersAPI } from '../../../utils/api';
import Card from '../../../components/common/Card';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import { statusClass } from '../../../utils/format';
import { classifyLoadError } from '../../../utils/loadError';

// Same category list as
// DailyTasksPage.jsx's creation form, not a second one.
const TASK_CATEGORIES = [
  'Design', 'Material Preparation', 'Cutting', 'CNC', 'Laser', 'Assembly',
  'Finishing', 'Installation', 'Procurement', 'Quality Check', 'Workshop',
  'Administration', 'Other',
];

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

export default TaskDetailPage;
