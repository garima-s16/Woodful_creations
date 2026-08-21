import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { dailyTasksAPI, employeesAPI, ordersAPI } from '../utils/api';
import Card from '../components/common/Card';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { statusClass } from '../utils/statusColors';

function TaskDetailPage() {
  const { taskId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [task, setTask] = useState(null);
  const [employee, setEmployee] = useState(null);
  const [order, setOrder] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState('');
  const [showAssignNext, setShowAssignNext] = useState(false);
  const [employees, setEmployees] = useState([]);

  const load = useCallback(() => {
    dailyTasksAPI.get(taskId).then((res) => {
      setTask(res.data);
      if (res.data.employee_id) employeesAPI.get(res.data.employee_id).then((r) => setEmployee(r.data)).catch(() => {});
      if (res.data.order_id) ordersAPI.get(res.data.order_id).then((r) => setOrder(r.data)).catch(() => {});
    }).catch(() => setError('Unable to load this task.'));
    dailyTasksAPI.listComments(taskId).then((res) => setComments(res.data)).catch(() => setComments([]));
    employeesAPI.list().then((res) => setEmployees(res.data)).catch(() => setEmployees([]));
  }, [taskId]);

  useEffect(load, [load]);

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
        next_due_date: formData.next_due_date,
        next_priority: formData.next_priority,
        note: formData.note,
      });
      setShowAssignNext(false);
      window.location.href = `/tasks/${next.data.id}`;
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
        : { status: formData.status, delay_reason: formData.delay_reason };
      await dailyTasksAPI.update(task.id, payload);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update task');
    } finally {
      setLoading(false);
    }
  };

  if (error) return <div className="page"><Alert type="error" message={error} /></div>;
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
          <button className="btn-secondary" onClick={() => setShowAssignNext(true)}>Complete &amp; Assign Next</button>
        </div>
      </div>

      <div className="dashboard-grid">
        <Card title="Task Details">
          <div className="card-body">
            <div className="detail-meta">
              <div className="detail-meta-item"><span className="detail-meta-label">Employee</span><span className="detail-meta-value">{employee ? <Link to={`/employees/${employee.id}`}>{employee.name}</Link> : '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Project</span><span className="detail-meta-value">{order ? <Link to={`/orders/${order.id}`}>{order.order_code}</Link> : '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Date</span><span className="detail-meta-value">{new Date(task.date).toLocaleDateString()}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Planned Start</span><span className="detail-meta-value">{task.planned_start || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Planned End</span><span className="detail-meta-value">{task.planned_end || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Checked By</span><span className="detail-meta-value">{task.checked_by || '-'}</span></div>
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
                  : [statusField, delayField];
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
          {comments.length === 0 && <p className="page-summary">No comments yet.</p>}
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

      <Modal isOpen={showAssignNext} title="Complete & Assign Next" onClose={() => setShowAssignNext(false)}>
        <Form
          fields={[
            { name: 'next_employee_id', label: 'Next Person', type: 'select', required: true,
              options: employees.map((e) => ({ value: e.id, label: e.name })) },
            { name: 'next_task_description', label: 'Next Action', required: true },
            { name: 'next_due_date', label: 'Due Date', type: 'date', required: true },
            { name: 'next_priority', label: 'Priority', type: 'select', options: [
              { value: 'Low', label: 'Low' }, { value: 'Medium', label: 'Medium' },
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
