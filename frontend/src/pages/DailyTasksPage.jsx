import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { dailyTasksAPI, employeesAPI, ordersAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

const VIEWS = ['All', 'My Tasks', 'Overdue', 'In Progress', 'Completed'];

function DailyTasksPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const [tasks, setTasks] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [orders, setOrders] = useState([]);
  const [view, setView] = useState('All');
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => {
    dailyTasksAPI.list().then((res) => setTasks(res.data));
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
    // "My Tasks" matches by the logged-in user's full name against the
    // assigned employee's name - there is no direct user-to-employee link
    // in the data model, so this is a best-effort match on name.
    const emp = employees.find((e) => e.id === task.employee_id);
    return emp && user?.full_name && emp.name.toLowerCase() === user.full_name.toLowerCase();
  };

  const isOverdue = (task) => {
    if (task.status === 'Completed') return false;
    const taskDate = new Date(task.date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return taskDate < today;
  };

  const filteredTasks = tasks.filter((t) => {
    if (view === 'My Tasks') return myEmployeeMatch(t);
    if (view === 'Overdue') return isOverdue(t);
    if (view === 'In Progress') return t.status === 'In Progress';
    if (view === 'Completed') return t.status === 'Completed';
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
    { name: 'task_code', label: 'Task Code', required: true, placeholder: 'TSK-011', section: 'Project' },
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
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Assign Task</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <div className="tab-bar">
        {VIEWS.map((v) => (
          <button key={v} className={view === v ? 'tab active' : 'tab'} onClick={() => setView(v)}>{v}</button>
        ))}
      </div>
      <Table columns={columns} data={filteredTasks} onRowClick={(row) => navigate(`/daily-tasks/${row.id}`)} emptyMessage="No tasks in this view." />
      <Modal isOpen={showAdd} title="Assign Task" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Assign Task" />
      </Modal>
    </div>
  );
}

export default DailyTasksPage;
