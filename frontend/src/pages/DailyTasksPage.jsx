import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { dailyTasksAPI, employeesAPI, ordersAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { today } from '../utils/dates';

const VIEWS = ['All', 'My Tasks', 'Overdue', 'Doing', 'Done'];

function DailyTasksPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const [tasks, setTasks] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [orders, setOrders] = useState([]);
  const [view, setView] = useState('All');
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = () => {
    setPageLoading(true);
    dailyTasksAPI.list().then((res) => setTasks(res.data)).finally(() => setPageLoading(false));
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
        date: new Date(formData.date).toISOString(),
        completion_percent: Number(formData.completion_percent || 0),
      });
      setShowAdd(false);
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
    const taskDate = new Date(task.date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return taskDate < today;
  };

  const filteredTasks = tasks.filter((t) => {
    if (view === 'My Tasks') return myEmployeeMatch(t);
    if (view === 'Overdue') return isOverdue(t);
    if (view === 'Doing') return t.status === 'DOING';
    if (view === 'Done') return t.status === 'DONE';
    return true;
  });

  const columns = [
    { key: 'task_code', label: 'Task ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'employee_id', label: 'Employee', render: (v) => employees.find((e) => e.id === v)?.name || v },
    { key: 'order_id', label: 'Project', render: (v) => orders.find((o) => o.id === v)?.order_code || '-' },
    { key: 'task_description', label: 'Task' }, { key: 'priority', label: 'Priority' },
    { key: 'status', label: 'Status' }, { key: 'completion_percent', label: 'Completion %' },
  ];

  const fields = [
    { name: 'order_id', label: 'Project (Order)', type: 'select', section: 'Project', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'employee_id', label: 'Employee', type: 'select', required: true, section: 'Assignment', options: employees.map((e) => ({ value: e.id, label: e.name })) },
    { name: 'checked_by', label: 'Checked By', section: 'Assignment' },
    { name: 'date', label: 'Date', type: 'date', required: true, section: 'Schedule' },
    { name: 'task_description', label: 'Task Description', required: true, type: 'textarea', section: 'Schedule' },
    { name: 'priority', label: 'Priority', type: 'select', section: 'Priority', options: [
      { value: 'Low', label: 'Low' }, { value: 'Medium', label: 'Medium' },
      { value: 'High', label: 'High' }, { value: 'Urgent', label: 'Urgent' },
    ] },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Tasks</h1>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('tasks.xlsx')} target="_blank" rel="noreferrer">
            Export Tasks &amp; Production
          </a>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>Assign Task</button>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <div className="tab-bar">
        {VIEWS.map((v) => (
          <button key={v} className={view === v ? 'tab active' : 'tab'} onClick={() => setView(v)}>{v}</button>
        ))}
      </div>
      <Table
        columns={columns} data={filteredTasks} loading={pageLoading}
        onRowClick={(row) => navigate(`/daily-tasks/${row.id}`)}
        emptyMessage={
          view === 'Overdue' ? "Nothing overdue - you're on top of it."
          : view === 'My Tasks' ? 'No work assigned to you right now.'
          : view === 'Doing' ? 'Nothing in progress at the moment.'
          : view === 'Done' ? 'Nothing completed in this view yet.'
          : 'No tasks yet. Assign the first one to get started.'
        }
      />
      <Modal isOpen={showAdd} title="Assign Task" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Assign Task"
          initialValues={{ date: today(), checked_by: user?.full_name || user?.username || '' }} />
      </Modal>
    </div>
  );
}

export default DailyTasksPage;
