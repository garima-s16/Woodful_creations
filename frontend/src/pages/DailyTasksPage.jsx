import React, { useEffect, useState } from 'react';
import { dailyTasksAPI, employeesAPI, ordersAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function DailyTasksPage() {
  const [tasks, setTasks] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [orders, setOrders] = useState([]);
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

  const columns = [
    { key: 'task_code', label: 'Task ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'employee_id', label: 'Employee', render: (v) => employees.find((e) => e.id === v)?.name || v },
    { key: 'order_id', label: 'Project', render: (v) => orders.find((o) => o.id === v)?.order_code || '-' },
    { key: 'task_description', label: 'Task' }, { key: 'priority', label: 'Priority' },
    { key: 'status', label: 'Status' }, { key: 'completion_percent', label: 'Completion %' },
  ];

  const fields = [
    { name: 'task_code', label: 'Task Code', required: true, placeholder: 'TSK-011' },
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'employee_id', label: 'Employee', type: 'select', required: true, options: employees.map((e) => ({ value: e.id, label: e.name })) },
    { name: 'order_id', label: 'Project (Order)', type: 'select', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'task_description', label: 'Task Description', required: true, type: 'textarea' },
    { name: 'priority', label: 'Priority', type: 'select', options: [
      { value: 'Low', label: 'Low' }, { value: 'Medium', label: 'Medium' },
      { value: 'High', label: 'High' }, { value: 'Urgent', label: 'Urgent' },
    ] },
    { name: 'status', label: 'Status', type: 'select', options: [
      { value: 'Not Started', label: 'Not Started' }, { value: 'In Progress', label: 'In Progress' },
      { value: 'Completed', label: 'Completed' }, { value: 'On Hold', label: 'On Hold' },
    ] },
    { name: 'completion_percent', label: 'Completion %', type: 'number' },
    { name: 'checked_by', label: 'Checked By' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Daily Tasks</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Task</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={tasks} />
      <Modal isOpen={showAdd} title="Add Task" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Task" />
      </Modal>
    </div>
  );
}

export default DailyTasksPage;
