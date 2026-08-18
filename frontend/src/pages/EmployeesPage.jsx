import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { employeesAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import KpiCard from '../components/common/KpiCard';
import { formatCurrency } from '../utils/currency';

function EmployeesPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [employees, setEmployees] = useState([]);
  const [search, setSearch] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = (searchTerm) => {
    setPageLoading(true);
    const params = {};
    if (searchTerm) params.search = searchTerm;
    employeesAPI.list(params).then((res) => setEmployees(res.data)).finally(() => setPageLoading(false));
  };
  useEffect(() => {
    load();
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    load(search);
  };

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
      load(search);
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
        name: formData.name, designation: formData.designation, department: formData.department,
        phone: formData.phone, email: formData.email, manager: formData.manager,
        monthly_salary: formData.monthly_salary, status: formData.status,
        emergency_contact: formData.emergency_contact, remarks: formData.remarks,
      });
      setEditingEmployee(null);
      load(search);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update employee');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'employee_code', label: 'Employee ID' }, { key: 'name', label: 'Name' },
    { key: 'designation', label: 'Designation' },
    { key: 'department', label: 'Department' }, { key: 'phone', label: 'Phone' },
    { key: 'email', label: 'Email' },
    { key: 'joining_date', label: 'Joining Date', render: (v) => (v ? new Date(v).toLocaleDateString() : '-') },
    { key: 'monthly_salary', label: 'Monthly Salary', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'daily_wage', label: 'Daily Wage', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'manager', label: 'Manager' },
    { key: 'status', label: 'Status' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingEmployee(row); }}>Edit</button> : null
      ),
    },
  ];

  const createFields = [
    { name: 'name', label: 'Name', required: true, section: 'Personal' },
    { name: 'phone', label: 'Phone', section: 'Personal' },
    { name: 'email', label: 'Email', type: 'email', section: 'Personal' },
    { name: 'designation', label: 'Designation', section: 'Employment' },
    { name: 'department', label: 'Department', section: 'Employment' },
    { name: 'manager', label: 'Manager/Supervisor', section: 'Employment' },
    { name: 'joining_date', label: 'Joining Date', type: 'date', section: 'Employment' },
    { name: 'monthly_salary', label: 'Monthly Salary', type: 'number', required: true, section: 'Compensation' },
    { name: 'emergency_contact', label: 'Emergency Contact', section: 'Emergency Contact' },
    { name: 'remarks', label: 'Remarks', type: 'textarea', section: 'Emergency Contact' },
  ];

  const editFields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'designation', label: 'Designation' },
    { name: 'department', label: 'Department' },
    { name: 'phone', label: 'Phone' },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'manager', label: 'Manager/Supervisor' },
    { name: 'monthly_salary', label: 'Monthly Salary', type: 'number', required: true },
    { name: 'status', label: 'Status', type: 'select', options: [
      { value: 'Active', label: 'Active' }, { value: 'Inactive', label: 'Inactive' },
    ] },
    { name: 'emergency_contact', label: 'Emergency Contact' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  const exportUrl = () => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    const qs = params.toString();
    return reportsAPI.downloadUrl(`employees.xlsx${qs ? `?${qs}` : ''}`);
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Employees</h1>
          <p className="page-summary">Manage your team's roles, compensation, and department assignments.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={exportUrl()} target="_blank" rel="noreferrer">
            {search ? 'Export Filtered' : 'Export All'}
          </a>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Employee</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <div className="kpi-row">
        <KpiCard label="Total Employees" value={employees.length} />
        <KpiCard label="Active" value={employees.filter((e) => e.status === 'Active').length} tone="success" />
      </div>
      <form className="page-search" onSubmit={handleSearch}>
        <input
          type="text" placeholder="Search by name, ID, designation, phone, or email..." value={search}
          onChange={(e) => setSearch(e.target.value)} className="form-input"
        />
        <button type="submit" className="btn-secondary">Search</button>
      </form>
      <Table columns={columns} data={employees} loading={pageLoading} onRowClick={(row) => navigate(`/employees/${row.id}`)} emptyMessage="No employees yet. Add your first employee to get started." />
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
