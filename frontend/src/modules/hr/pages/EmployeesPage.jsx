import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { employeesAPI, reportsAPI, usersAPI } from '../../../utils/api';
import Table from '../../../components/common/Table';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import KpiCard from '../../../components/common/KpiCard';
import { formatCurrency } from '../../../utils/format';

function EmployeesPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [employees, setEmployees] = useState([]);
  const [users, setUsers] = useState([]);
  const [loginAccessEmployee, setLoginAccessEmployee] = useState(null); // the employee whose Login Access modal is open
  const [justCreatedEmployee, setJustCreatedEmployee] = useState(null); // Section 9's onboarding prompt after Add Employee
  const [search, setSearch] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = (searchTerm) => {
    setPageLoading(true);
    setLoadError(false);
    const params = {};
    if (searchTerm) params.search = searchTerm;
    employeesAPI.list(params).then((res) => setEmployees(res.data)).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
    if (isPrivileged) {
      usersAPI.list().then((res) => setUsers(res.data)).catch(() => setUsers([]));
    }
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
      const res = await employeesAPI.create({
        ...formData,
        joining_date: formData.joining_date ? new Date(formData.joining_date).toISOString() : null,
        monthly_salary: formData.monthly_salary || '0',
      });
      setShowAdd(false);
      load(search);
      setJustCreatedEmployee(res.data); // offer Login Access next, per the intended onboarding flow
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add employee');
    } finally {
      setLoading(false);
    }
  };

  const userForEmployee = (employeeId) => users.find((u) => u.employee_id === employeeId && !u.is_deleted);
  const activeMasterCount = () => users.filter((u) => u.role === 'master' && u.is_active).length;

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

  const handleLoginAccessSave = async (formData) => {
    setLoading(true);
    setError('');
    try {
      const existingUser = userForEmployee(loginAccessEmployee.id);
      if (existingUser) {
        await usersAPI.update(existingUser.id, {
          full_name: formData.full_name, phone: formData.phone, role: formData.role,
          is_active: formData.is_active === 'true' || formData.is_active === true,
        });
      } else {
        await usersAPI.create({ ...formData, employee_id: loginAccessEmployee.id });
      }
      setLoginAccessEmployee(null);
      load(search);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save login access');
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
      key: 'login_access', label: 'Login Access', render: (v, row) => {
        const linked = userForEmployee(row.id);
        if (!linked) return isPrivileged ? <span style={{ color: 'var(--text-secondary)' }}>No login</span> : '-';
        return (
          <span className={`status-badge ${linked.is_active ? 'status-ok' : 'status-neutral'}`}>
            {linked.username} ({linked.role === 'master' ? 'Master' : 'User'}{linked.is_active ? '' : ', Inactive'})
          </span>
        );
      },
    },
    {
      key: 'login_action', label: '', render: (v, row) => (
        isPrivileged
          ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setLoginAccessEmployee(row); }}>
              {userForEmployee(row.id) ? 'Manage Login' : 'Create Login'}
            </button>
          : null
      ),
    },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingEmployee(row); }}>Edit</button> : null
      ),
    },
  ];

  const createFields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'phone', label: 'Phone', hint: 'Exactly 10 digits.',
      validate: (value) => (/^[0-9]{10}$/.test(value) ? '' : 'Please enter valid mobile number') },
    { name: 'monthly_salary', label: 'Monthly Salary', type: 'number', required: true },
    { name: 'email', label: 'Email', type: 'email', advanced: true },
    { name: 'designation', label: 'Designation', advanced: true },
    { name: 'department', label: 'Department', advanced: true },
    { name: 'manager', label: 'Manager/Supervisor', advanced: true },
    { name: 'joining_date', label: 'Joining Date', type: 'date', advanced: true },
    { name: 'emergency_contact', label: 'Emergency Contact', advanced: true },
    { name: 'remarks', label: 'Remarks', type: 'textarea', advanced: true },
  ];

  const editFields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'designation', label: 'Designation' },
    { name: 'department', label: 'Department' },
    { name: 'phone', label: 'Phone', hint: 'Exactly 10 digits.',
      validate: (value) => (/^[0-9]{10}$/.test(value) ? '' : 'Please enter valid mobile number') },
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
      <Table columns={columns} data={employees} loading={pageLoading} error={loadError} onRetry={() => load(search)} onRowClick={(row) => navigate(`/employees/${row.id}`)} emptyMessage="No employees yet. Add your first employee to get started." emptyAction={isPrivileged ? { label: 'Add Employee', onClick: () => setShowAdd(true) } : undefined} />
      <Modal isOpen={showAdd} title="Add Employee" onClose={() => setShowAdd(false)}>
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Add Employee" />
      </Modal>
      <Modal isOpen={!!editingEmployee} title={`Edit ${editingEmployee?.name || ''}`} onClose={() => setEditingEmployee(null)}>
        {editingEmployee && (
          <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingEmployee} />
        )}
      </Modal>

      <Modal isOpen={!!justCreatedEmployee} title="Employee Added" onClose={() => setJustCreatedEmployee(null)}>
        {justCreatedEmployee && (
          <div>
            <p>{justCreatedEmployee.name} has been added. Does this employee need application login access?</p>
            <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
              <button className="btn-primary" onClick={() => { setLoginAccessEmployee(justCreatedEmployee); setJustCreatedEmployee(null); }}>
                Create Login Access
              </button>
              <button className="btn-secondary" onClick={() => setJustCreatedEmployee(null)}>Skip for Now</button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={!!loginAccessEmployee}
        title={loginAccessEmployee ? `Login Access - ${loginAccessEmployee.name}` : ''}
        onClose={() => setLoginAccessEmployee(null)}
      >
        {loginAccessEmployee && (() => {
          const linked = userForEmployee(loginAccessEmployee.id);
          // Reflect the backend's last-active-master protection here too,
          // not just as an error after submitting - a linked account that
          // IS the last active master can't be demoted or deactivated
          // through this form, so those options are simply not offered.
          const isLastActiveMaster = linked && linked.role === 'master' && linked.is_active && activeMasterCount() <= 1;
          const roleOptions = isLastActiveMaster
            ? [{ value: 'master', label: 'Master (Full Access)' }]
            : [{ value: 'user', label: 'Employee (Limited Access)' }, { value: 'master', label: 'Master (Full Access)' }];
          const statusOptions = isLastActiveMaster
            ? [{ value: 'true', label: 'Active' }]
            : [{ value: 'true', label: 'Active' }, { value: 'false', label: 'Inactive' }];

          if (linked) {
            return (
              <div>
                {isLastActiveMaster && (
                  <Alert type="info" message="This is the last active Master account and cannot be deactivated or changed to a non-Master role." onClose={() => {}} />
                )}
                <Form
                  fields={[
                    { name: 'full_name', label: 'Full Name', required: true },
                    { name: 'phone', label: 'Phone' },
                    { name: 'role', label: 'Role', type: 'select', required: true, options: roleOptions },
                    { name: 'is_active', label: 'Status', type: 'select', options: statusOptions },
                  ]}
                  onSubmit={handleLoginAccessSave} loading={loading} submitText="Save Changes"
                  initialValues={{ full_name: linked.full_name, phone: linked.phone, role: linked.role, is_active: String(linked.is_active) }}
                />
                <p style={{ marginTop: 12, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  Username: {linked.username} &middot; To reset the password, use the Users page.
                </p>
              </div>
            );
          }
          return (
            <Form
              fields={[
                { name: 'username', label: 'Username', required: true },
                { name: 'full_name', label: 'Full Name', required: true },
                { name: 'email', label: 'Email', type: 'email', required: true },
                { name: 'phone', label: 'Phone' },
                { name: 'password', label: 'Temporary Password', type: 'password', required: true, hint: 'The employee should change this after first login.' },
                { name: 'role', label: 'Role', type: 'select', required: true, options: [
                  { value: 'user', label: 'Employee (Limited Access)' }, { value: 'master', label: 'Master (Full Access)' },
                ] },
              ]}
              onSubmit={handleLoginAccessSave} loading={loading} submitText="Create Login Access"
              initialValues={{ full_name: loginAccessEmployee.name, email: loginAccessEmployee.email || '', phone: loginAccessEmployee.phone || '' }}
            />
          );
        })()}
      </Modal>
    </div>
  );
}

export default EmployeesPage;
