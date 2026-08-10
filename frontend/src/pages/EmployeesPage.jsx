import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { employeesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function EmployeesPage() {
  const navigate = useNavigate();
  const [employees, setEmployees] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => employeesAPI.list().then((res) => setEmployees(res.data));
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await employeesAPI.create({
        ...formData,
        joining_date: formData.joining_date ? new Date(formData.joining_date).toISOString() : null,
        monthly_salary: formData.monthly_salary || '0',
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add employee');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'employee_code', label: 'Employee ID' }, { key: 'name', label: 'Name' },
    { key: 'department', label: 'Department' }, { key: 'phone', label: 'Phone' },
    { key: 'monthly_salary', label: 'Monthly Salary', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'daily_wage', label: 'Daily Wage', render: (v) => `Rs ${Number(v).toLocaleString()}` },
    { key: 'status', label: 'Status' },
  ];

  const fields = [
    { name: 'employee_code', label: 'Employee Code', required: true, placeholder: 'EMP-006' },
    { name: 'name', label: 'Name', required: true },
    { name: 'department', label: 'Department' },
    { name: 'phone', label: 'Phone' },
    { name: 'joining_date', label: 'Joining Date', type: 'date' },
    { name: 'monthly_salary', label: 'Monthly Salary', type: 'number', required: true },
    { name: 'emergency_contact', label: 'Emergency Contact' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Employees</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Employee</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={employees} onRowClick={(row) => navigate(`/employees/${row.id}`)} emptyMessage="No records yet." />
      <Modal isOpen={showAdd} title="Add Employee" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Employee" />
      </Modal>
    </div>
  );
}

export default EmployeesPage;
