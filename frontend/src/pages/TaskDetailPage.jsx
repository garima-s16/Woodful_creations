import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { dailyTasksAPI, employeesAPI, ordersAPI } from '../utils/api';
import Card from '../components/common/Card';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function statusClass(status) {
  const s = (status || '').toLowerCase();
  if (s === 'completed') return 'status-ok';
  if (s === 'in progress') return 'status-warning';
  if (s === 'not started') return 'status-info';
  return 'status-danger';
}

function TaskDetailPage() {
  const { taskId } = useParams();
  const [task, setTask] = useState(null);
  const [employee, setEmployee] = useState(null);
  const [order, setOrder] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    dailyTasksAPI.get(taskId).then((res) => {
      setTask(res.data);
      if (res.data.employee_id) employeesAPI.get(res.data.employee_id).then((r) => setEmployee(r.data)).catch(() => {});
      if (res.data.order_id) ordersAPI.get(res.data.order_id).then((r) => setOrder(r.data)).catch(() => {});
    }).catch(() => setError('Unable to load this task.'));
  }, [taskId]);

  useEffect(load, [load]);

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await dailyTasksAPI.update(task.id, {
        status: formData.status,
        completion_percent: Number(formData.completion_percent || 0),
        delay_reason: formData.delay_reason,
        remarks: formData.remarks,
      });
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
              fields={[
                { name: 'status', label: 'Status', type: 'select', required: true, options: [
                  { value: 'Not Started', label: 'Not Started' }, { value: 'In Progress', label: 'In Progress' },
                  { value: 'Completed', label: 'Completed' }, { value: 'On Hold', label: 'On Hold' },
                ] },
                { name: 'completion_percent', label: 'Completion %', type: 'number', required: true },
                { name: 'delay_reason', label: 'Delay Reason (if any)' },
                { name: 'remarks', label: 'Remarks', type: 'textarea' },
              ]}
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
    </div>
  );
}

export default TaskDetailPage;
