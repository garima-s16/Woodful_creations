import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { employeesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import KpiCard from '../components/common/KpiCard';
import { formatCurrency } from '../utils/currency';

function EmployeesPage() {
  const navigate = useNavigate();
  const [employees, setEmployees] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => employeesAPI.list().then((res) => setEmployees(res.data));
  useEffect(() => {
    load();
  }, []);

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

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await employeesAPI.update(editingEmployee.id, {
        name: formData.name, department: formData.department, phone: formData.phone,
        monthly_salary: formData.monthly_salary, status: formData.status,
        emergency_contact: formData.emergency_contact, remarks: formData.remarks,
      });
      setEditingEmployee(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update employee');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'employee_code', label: 'Employee ID' }, { key: 'name', label: 'Name' },
    { key: 'department', label: 'Department' }, { key: 'phone', label: 'Phone' },
    { key: 'monthly_salary', label: 'Monthly Salary', render: (v) => formatCurrency(v) },
    { key: 'daily_wage', label: 'Daily Wage', render: (v) => formatCurrency(v) },
    { key: 'status', label: 'Status' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingEmployee(row); }}>Edit</button>
      ),
    },
  ];

  const createFields = [
    { name: 'name', label: 'Name', required: true, section: 'Personal' },
    { name: 'phone', label: 'Phone', section: 'Personal' },
    { name: 'department', label: 'Department', section: 'Employment' },
    { name: 'joining_date', label: 'Joining Date', type: 'date', section: 'Employment' },
    { name: 'monthly_salary', label: 'Monthly Salary', type: 'number', required: true, section: 'Compensation' },
    { name: 'emergency_contact', label: 'Emergency Contact', section: 'Emergency Contact' },
    { name: 'remarks', label: 'Remarks', type: 'textarea', section: 'Emergency Contact' },
  ];

  const editFields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'department', label: 'Department' },
    { name: 'phone', label: 'Phone' },
    { name: 'monthly_salary', label: 'Monthly Salary', type: 'number', required: true },
    { name: 'status', label: 'Status', type: 'select', options: [
      { value: 'Active', label: 'Active' }, { value: 'Inactive', label: 'Inactive' },
    ] },
    { name: 'emergency_contact', label: 'Emergency Contact' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Employees</h1>
          <p className="page-summary">Manage your team's roles, compensation, and department assignments.</p>
        </div>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Employee</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <div className="kpi-row">
        <KpiCard label="Total Employees" value={employees.length} />
        <KpiCard label="Active" value={employees.filter((e) => e.status === 'Active').length} tone="success" />
      </div>
      <Table columns={columns} data={employees} onRowClick={(row) => navigate(`/employees/${row.id}`)} emptyMessage="No employees yet. Add your first employee to get started." />
      <Modal isOpen={showAdd} title="Add Employee" onClose={() => setShowAdd(false)}>
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Add Employee" />
      </Modal>
      <Modal isOpen={!!editingEmployee} title={`Edit ${editingEmployee?.name || ''}`} onClose={() => setEditingEmployee(null)}>
        {editingEmployee && (
          <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingEmployee} />
        )}
      </Modal>
    </div>
  );
}

export default EmployeesPage;
