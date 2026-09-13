// HR workforce pages: employees list/detail, attendance, leaves,
// company holidays, and holiday import. Combines the former
// EmployeesPage.jsx, EmployeeDetailPage.jsx, AttendancePage.jsx,
// LeavesPage.jsx, CompanyHolidaysPage.jsx, and HolidayImportPage.jsx.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { attendanceAPI, dailyTasksAPI, documentsAPI, employeesAPI, holidayImportAPI, holidaysAPI, leavesAPI, ordersAPI, overtimeRequestsAPI, productionJobsAPI, reportsAPI, salaryAdvancesAPI, salarySlipsAPI, usersAPI } from '../../../utils/api';
import { Alert, Card, ConfirmDialog, Form, KpiCard, Modal, Table } from '../../../components/common/UI';
import { formatCurrency, statusClass, today } from '../../../utils/utils';
import { DocumentsPanel } from '../../../components/Assistant';
import { openWithMessage } from '../../../redux/slices';

// --- EmployeesPage.jsx ---
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

// --- EmployeeDetailPage.jsx ---
// Family 137 - Employee 360 / HR Command Center (section 13):
// Overview/Attendance/Leave/Tasks/Production/Salary/Onboarding/Activity
// give the "coherent Employee 360 experience with appropriate
// sections/tabs" section 13.15 asks for, built entirely on top of the
// existing tabs/endpoints already below plus the new Employee 360
// aggregation endpoints (see hr/services.py).
const TABS = ['Overview', 'Attendance', 'Leave', 'Tasks', 'Production', 'Salary', 'Documents', 'Onboarding', 'Activity'];

function EmployeeDetailPage() {
  const { employeeId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const dispatch = useDispatch();
  const isPrivileged = user?.role === 'master';
  const isOwnProfile = String(user?.employee_id) === String(employeeId);
  const canViewHrDetails = isPrivileged || isOwnProfile;
  const [employee, setEmployee] = useState(null);
  const [attendance, setAttendance] = useState([]);
  const [leaves, setLeaves] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [productionJobs, setProductionJobs] = useState([]);
  const [orders, setOrders] = useState([]);
  const [tab, setTab] = useState('Overview');
  const [activeAction, setActiveAction] = useState(null); // 'attendance' | 'task' | 'production'
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [attendanceError, setAttendanceError] = useState(false);
  const [leavesError, setLeavesError] = useState(false);
  const [tasksError, setTasksError] = useState(false);
  const [productionJobsError, setProductionJobsError] = useState(false);

  // Family 137 (Employee 360) - the Overview tab's single aggregation
  // call plus organizational relationships, loaded alongside the rest
  // (cheap, and both back the Overview tab shown by default).
  const [overview360, setOverview360] = useState(null);
  const [overview360Error, setOverview360Error] = useState(false);
  const [relationships, setRelationships] = useState(null);

  // Calendar, salary, onboarding/offboarding, and activity are each
  // fetched only when their tab is actually opened - same lazy-load
  // pattern as ClientDetailPage's Relationship Timeline tab.
  const now = new Date();
  const [calendarYear, setCalendarYear] = useState(now.getFullYear());
  const [calendarMonth, setCalendarMonth] = useState(now.getMonth() + 1);
  const [calendar, setCalendar] = useState(null);
  const [calendarLoading, setCalendarLoading] = useState(false);

  const [salarySlips, setSalarySlips] = useState(null);
  const [salaryAdvances, setSalaryAdvances] = useState(null);
  const [salaryLoading, setSalaryLoading] = useState(false);

  const [lifecyclePhase, setLifecyclePhase] = useState('onboarding');
  const [lifecycle, setLifecycle] = useState(null);
  const [lifecycleLoading, setLifecycleLoading] = useState(false);
  const [lifecycleError, setLifecycleError] = useState('');

  const [activityTimeline, setActivityTimeline] = useState(null);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState('');

  const load = useCallback(() => {
    setLoadError('');
    setAttendanceError(false);
    setLeavesError(false);
    setTasksError(false);
    setProductionJobsError(false);
    setOverview360Error(false);
    employeesAPI.get(employeeId).then((res) => setEmployee(res.data)).catch(() => setLoadError('Unable to load this employee.'));
    attendanceAPI.list({ employee_id: employeeId }).then((res) => setAttendance(res.data)).catch(() => { setAttendance([]); setAttendanceError(true); });
    leavesAPI.list({ employee_id: employeeId }).then((res) => setLeaves(res.data)).catch(() => { setLeaves([]); setLeavesError(true); });
    dailyTasksAPI.list({ employee_id: employeeId }).then((res) => setTasks(res.data)).catch(() => { setTasks([]); setTasksError(true); });
    // Defect repair (P1-7): production-jobs now supports a server-side
    // employee_id filter - was previously the entire, ever-growing
    // production_jobs table fetched and filtered down to one
    // employee's jobs here in React.
    productionJobsAPI.list({ employee_id: employeeId }).then((res) => setProductionJobs(res.data)).catch(() => { setProductionJobs([]); setProductionJobsError(true); });
    // Defect repair (P1-8): this is only a "Project (Order)" picker
    // for the task/production-job forms below, not a report - a
    // Completed order is never a valid assignment target anyway.
    // active_only scopes it to orders that can actually be assigned
    // to, and an explicit limit means this call no longer silently
    // relies on the generic list endpoint's own default page size
    // (100) - which, unfiltered, would start missing older but still-
    // active orders once the business has more than 100 orders total.
    ordersAPI.list({ active_only: true, limit: 200 }).then((res) => setOrders(res.data)).catch(() => setOrders([]));
    if (canViewHrDetails) {
      employeesAPI.overview360(employeeId).then((res) => setOverview360(res.data)).catch(() => { setOverview360(null); setOverview360Error(true); });
      employeesAPI.relationships(employeeId).then((res) => setRelationships(res.data)).catch(() => setRelationships(null));
    }
  }, [employeeId, canViewHrDetails]);

  useEffect(() => {
    // Defect repair (F138 P4.2): employeeId changing (e.g. via the
    // Direct Reports / Department Peers links on the Overview tab
    // below, which point at /employees/:id while staying on this same
    // route/component) means this is a different employee now, not a
    // background refresh of the one already on screen - reset every
    // employee-scoped state, including the tab-lazy calendar/salary/
    // lifecycle/activity data, so the previous employee's information
    // can never flash under the new employee's URL while the new
    // employee's data is still loading. load() itself (called again
    // for the SAME employeeId elsewhere) must keep doing the opposite
    // and never clear already-good data.
    setEmployee(null);
    setAttendance([]);
    setLeaves([]);
    setTasks([]);
    setProductionJobs([]);
    setOverview360(null);
    setRelationships(null);
    setCalendar(null);
    setSalarySlips(null);
    setSalaryAdvances(null);
    setLifecycle(null);
    setActivityTimeline(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employeeId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (tab === 'Attendance' && canViewHrDetails && !calendar && !calendarLoading) {
      setCalendarLoading(true);
      employeesAPI.calendar(employeeId, calendarYear, calendarMonth)
        .then((res) => setCalendar(res.data)).catch(() => setCalendar(null)).finally(() => setCalendarLoading(false));
    }
  }, [tab, employeeId, canViewHrDetails, calendarYear, calendarMonth, calendar, calendarLoading]);

  const reloadCalendar = (year, month) => {
    setCalendarYear(year); setCalendarMonth(month); setCalendar(null);
    employeesAPI.calendar(employeeId, year, month).then((res) => setCalendar(res.data)).catch(() => setCalendar(null));
  };

  useEffect(() => {
    if (tab === 'Salary' && canViewHrDetails && salarySlips === null && !salaryLoading) {
      setSalaryLoading(true);
      Promise.all([
        salarySlipsAPI.list({ employee_id: employeeId }).then((res) => res.data).catch(() => []),
        salaryAdvancesAPI.list({ employee_id: employeeId }).then((res) => res.data).catch(() => []),
      ]).then(([slips, advances]) => { setSalarySlips(slips); setSalaryAdvances(advances); }).finally(() => setSalaryLoading(false));
    }
  }, [tab, employeeId, canViewHrDetails, salarySlips, salaryLoading]);

  const loadLifecycle = useCallback((phase) => {
    setLifecycleLoading(true);
    setLifecycleError('');
    employeesAPI.lifecycle(employeeId, phase)
      .then((res) => setLifecycle(res.data))
      .catch(() => setLifecycleError('Unable to load this checklist.'))
      .finally(() => setLifecycleLoading(false));
  }, [employeeId]);

  useEffect(() => {
    if (tab === 'Onboarding' && canViewHrDetails) loadLifecycle(lifecyclePhase);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, lifecyclePhase, canViewHrDetails]);

  useEffect(() => {
    if (tab === 'Activity' && canViewHrDetails && !activityTimeline && !activityLoading) {
      setActivityLoading(true);
      setActivityError('');
      employeesAPI.activityTimeline(employeeId)
        .then((res) => setActivityTimeline(res.data))
        .catch(() => setActivityError('Unable to load the activity timeline.'))
        .finally(() => setActivityLoading(false));
    }
  }, [tab, employeeId, canViewHrDetails, activityTimeline, activityLoading]);

  const handleToggleLifecycleItem = async (item, isComplete) => {
    try {
      await employeesAPI.updateLifecycleItem(employeeId, item.id, { is_complete: isComplete });
      loadLifecycle(lifecyclePhase);
    } catch (err) {
      setLifecycleError(err.response?.data?.detail || 'Unable to update this checklist item.');
    }
  };

  // Family 137 (Employee 360, section 13.9) - exit_date/exit_reason are
  // set explicitly by a master, never inferred from the status change
  // itself, matching this project's human-in-the-loop rule.
  const [exitDetailsSaving, setExitDetailsSaving] = useState(false);
  const [exitDetailsError, setExitDetailsError] = useState('');
  const handleSaveExitDetails = async (formData) => {
    setExitDetailsSaving(true); setExitDetailsError('');
    try {
      await employeesAPI.update(employeeId, {
        exit_date: formData.exit_date ? new Date(formData.exit_date).toISOString() : null,
        exit_reason: formData.exit_reason || null,
      });
      load();
    } catch (err) {
      setExitDetailsError(err.response?.data?.detail || 'Unable to save exit details.');
    } finally {
      setExitDetailsSaving(false);
    }
  };

  const askCai = (question) => dispatch(openWithMessage(question));

  const closeAction = () => { setActiveAction(null); setActionError(''); };

  const handleRecordAttendance = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await attendanceAPI.create({
        ...formData, employee_id: Number(employeeId),
        date: new Date(formData.date).toISOString(),
        in_time: formData.in_time ? new Date(`${formData.date}T${formData.in_time}`).toISOString() : null,
        out_time: formData.out_time ? new Date(`${formData.date}T${formData.out_time}`).toISOString() : null,
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to record attendance'); }
    finally { setActionLoading(false); }
  };

  const handleAssignTask = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await dailyTasksAPI.create({
        ...formData, employee_id: Number(employeeId),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        date: new Date(formData.date).toISOString(),
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to assign task'); }
    finally { setActionLoading(false); }
  };

  const handleCreateProductionJob = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await productionJobsAPI.create({
        ...formData, employee_id: Number(employeeId),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        date: new Date(formData.date).toISOString(),
        planned_qty: Number(formData.planned_qty || 0),
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to create production job'); }
    finally { setActionLoading(false); }
  };

  if (loadError) return <div className="page"><Alert type="error" message={loadError} /><button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button></div>;
  if (!employee) return <div className="page">Loading...</div>;

  const totalHours = attendance.reduce((sum, a) => sum + (a.working_hours || 0), 0);
  const totalOvertime = attendance.reduce((sum, a) => sum + (a.overtime_hours || 0), 0);
  const completedTasks = tasks.filter((t) => t.status === 'DONE').length;
  const overdueTasks = tasks.filter((t) => t.status !== 'DONE' && new Date(t.date) < new Date(today())).length;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/employees" className="btn-link">&larr; Back to Employees</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{employee.name}</h1>
          <div className="detail-subtitle">
            {employee.employee_code} &middot; {employee.department || 'No department'}
            {employee.business_id && <span className="business-id-badge">{employee.business_id}</span>}
          </div>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => setActiveAction('attendance')}>Record Attendance</button>
          <button className="btn-secondary" onClick={() => setActiveAction('task')}>Assign Task</button>
          <button className="btn-secondary" onClick={() => setActiveAction('production')}>Create Production Job</button>
        </div>
      </div>

      <div className="kpi-row">
        {canViewHrDetails && (
          <>
            <Card><div className="card-body"><div className="detail-meta-label">Total Hours</div><h3>{totalHours.toFixed(1)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Overtime Hours</div><h3>{totalOvertime.toFixed(1)}</h3></div></Card>
          </>
        )}
        <Card><div className="card-body"><div className="detail-meta-label">Tasks Completed</div><h3>{completedTasks}/{tasks.length}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Overdue Tasks</div><h3 style={overdueTasks > 0 ? { color: 'var(--warning)' } : undefined}>{overdueTasks}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Status</div><h3 style={{ fontSize: '1.1rem' }}>{employee.status}</h3></div></Card>
      </div>

      <div className="tab-bar">
        {(canViewHrDetails ? TABS : TABS.filter((t) => !['Attendance', 'Leave', 'Salary', 'Onboarding', 'Activity'].includes(t)))
          .filter((t) => t !== 'Documents' || isPrivileged)
          .map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && (
        <>
          <Card title="Employee Details">
            <div className="card-body">
              <div className="detail-meta">
                <div className="detail-meta-item"><span className="detail-meta-label">Phone</span><span className="detail-meta-value">{employee.phone ? <a href={`tel:${employee.phone}`}>{employee.phone}</a> : '-'}</span></div>
                <div className="detail-meta-item"><span className="detail-meta-label">Email</span><span className="detail-meta-value">{employee.email || '-'}</span></div>
                <div className="detail-meta-item"><span className="detail-meta-label">Manager</span><span className="detail-meta-value">{relationships?.manager?.name || employee.manager || '-'}</span></div>
                <div className="detail-meta-item"><span className="detail-meta-label">Joining Date</span><span className="detail-meta-value">{employee.joining_date ? new Date(employee.joining_date).toLocaleDateString() : '-'}</span></div>
                <div className="detail-meta-item"><span className="detail-meta-label">Employment Status</span><span className="detail-meta-value">{employee.status}{employee.status === 'Inactive' && employee.exit_date ? ` (exited ${new Date(employee.exit_date).toLocaleDateString()})` : ''}</span></div>
                <div className="detail-meta-item"><span className="detail-meta-label">Monthly Salary</span><span className="detail-meta-value">{employee.monthly_salary != null ? formatCurrency(employee.monthly_salary) : 'Restricted'}</span></div>
                <div className="detail-meta-item"><span className="detail-meta-label">Daily Wage</span><span className="detail-meta-value">{employee.daily_wage != null ? formatCurrency(employee.daily_wage) : 'Restricted'}</span></div>
                <div className="detail-meta-item"><span className="detail-meta-label">Emergency Contact</span><span className="detail-meta-value">{employee.emergency_contact || '-'}</span></div>
              </div>
            </div>
          </Card>

          {canViewHrDetails && (
            <>
              {overview360Error && <Alert type="error" message="Unable to load the Employee 360 summary." onClose={() => setOverview360Error(false)} />}
              {overview360 && (
                <div className="kpi-row">
                  <KpiCard label="Attendance %" value={overview360.attendance_summary?.attendance_percent != null ? `${overview360.attendance_summary.attendance_percent}%` : '-'} />
                  <KpiCard label="Active Tasks" value={overview360.work_summary?.active ?? 0} />
                  <KpiCard label="Completion Rate" value={overview360.work_summary?.completion_rate_percent != null ? `${overview360.work_summary.completion_rate_percent}%` : '-'} />
                  <KpiCard label="Pending Leave Requests" value={overview360.leave_summary?.pending_requests ?? 0} />
                  <KpiCard label="Onboarding Progress" value={`${overview360.onboarding_progress?.complete ?? 0}/${overview360.onboarding_progress?.total ?? 0}`} />
                </div>
              )}

              <Card title="Needs Attention">
                <div className="card-body">
                  {!overview360 && <p className="detail-meta-value">Loading...</p>}
                  {overview360 && (!overview360.needs_attention || overview360.needs_attention.total === 0) && (
                    <p className="detail-meta-value">Nothing needs attention right now.</p>
                  )}
                  {overview360?.needs_attention?.total > 0 && (
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                      {overview360.needs_attention.items.map((item, i) => (
                        <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                          <span className={`status-badge ${item.severity === 'high' ? 'status-danger' : item.severity === 'medium' ? 'status-warning' : 'status-neutral'}`}>{item.severity}</span>
                          {item.path ? <Link to={item.path}>{item.text}</Link> : <span>{item.text}</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </Card>

              <Card title="Ask Cai about this employee">
                <div className="card-body" style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                  <button type="button" className="btn-secondary" onClick={() => askCai(`Summarize ${employee.name}`)}>Summarize this employee</button>
                  <button type="button" className="btn-secondary" onClick={() => askCai(`What requires attention for ${employee.name}?`)}>What requires attention?</button>
                  <button type="button" className="btn-secondary" onClick={() => askCai(`Summarize workload and outstanding work for ${employee.name}`)}>Summarize workload</button>
                  <button type="button" className="btn-secondary" onClick={() => askCai(`Summarize recent attendance and work activity for ${employee.name}`)}>Summarize attendance</button>
                </div>
              </Card>

              {relationships && (relationships.direct_reports?.length > 0 || relationships.department_peers?.length > 0 || relationships.related_orders?.length > 0) && (
                <Card title="Relationships">
                  <div className="card-body">
                    {relationships.direct_reports?.length > 0 && (
                      <div className="detail-meta-item" style={{ marginBottom: 'var(--space-3)' }}>
                        <span className="detail-meta-label">Direct Reports</span>
                        <div>{relationships.direct_reports.map((r) => <Link key={r.id} to={`/employees/${r.id}`} style={{ marginRight: 'var(--space-2)' }}>{r.name}</Link>)}</div>
                      </div>
                    )}
                    {relationships.department_peers?.length > 0 && (
                      <div className="detail-meta-item" style={{ marginBottom: 'var(--space-3)' }}>
                        <span className="detail-meta-label">Department Peers</span>
                        <div>{relationships.department_peers.map((r) => <Link key={r.id} to={`/employees/${r.id}`} style={{ marginRight: 'var(--space-2)' }}>{r.name}</Link>)}</div>
                      </div>
                    )}
                    {relationships.related_orders?.length > 0 && (
                      <div className="detail-meta-item">
                        <span className="detail-meta-label">Related Projects</span>
                        <div>{relationships.related_orders.map((o) => <Link key={o.id} to={`/orders/${o.id}`} style={{ marginRight: 'var(--space-2)' }}>{o.order_code}</Link>)}</div>
                      </div>
                    )}
                  </div>
                </Card>
              )}

              {isPrivileged && overview360?.cost_contribution && (
                <Card title="Cost / Work Contribution">
                  <div className="card-body">
                    <p className="page-summary">{overview360.cost_contribution.disclaimer}</p>
                    <div className="detail-meta">
                      <div className="detail-meta-item"><span className="detail-meta-label">Total Salary Cost (finalized/paid)</span><span className="detail-meta-value">{formatCurrency(overview360.cost_contribution.total_salary_cost_all_time_finalized_or_paid)}</span></div>
                      <div className="detail-meta-item"><span className="detail-meta-label">Total Overtime Amount</span><span className="detail-meta-value">{formatCurrency(overview360.cost_contribution.total_overtime_amount_all_time_finalized_or_paid)}</span></div>
                      <div className="detail-meta-item"><span className="detail-meta-label">Completed Tasks ({overview360.cost_contribution.window_months}mo)</span><span className="detail-meta-value">{overview360.cost_contribution.completed_tasks_in_window}</span></div>
                      <div className="detail-meta-item"><span className="detail-meta-label">Completed Production Jobs ({overview360.cost_contribution.window_months}mo)</span><span className="detail-meta-value">{overview360.cost_contribution.completed_production_jobs_in_window}</span></div>
                    </div>
                  </div>
                </Card>
              )}
            </>
          )}
        </>
      )}

      {tab === 'Attendance' && (
        <>
          {canViewHrDetails && (
            <Card title="Attendance Intelligence (trailing 6 months)">
              <div className="card-body">
                {overview360 ? (
                  <div className="kpi-row" style={{ marginBottom: 0 }}>
                    <KpiCard label="Present Days" value={overview360.attendance_summary?.present_days ?? 0} />
                    <KpiCard label="Absent Days" value={overview360.attendance_summary?.absent_days ?? 0} />
                    <KpiCard label="Half Days" value={overview360.attendance_summary?.half_days ?? 0} />
                    <KpiCard label="Overtime Hours" value={overview360.attendance_summary?.overtime_hours_total ?? 0} />
                    <KpiCard label="Avg. Working Hours" value={overview360.attendance_summary?.average_working_hours ?? '-'} />
                  </div>
                ) : <p className="detail-meta-value">Loading...</p>}
              </div>
            </Card>
          )}
          {canViewHrDetails && (
            <Card title="Employee Calendar">
              <div className="card-body">
                <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', marginBottom: 'var(--space-3)' }}>
                  <button className="btn-secondary" onClick={() => reloadCalendar(calendarMonth === 1 ? calendarYear - 1 : calendarYear, calendarMonth === 1 ? 12 : calendarMonth - 1)}>&larr;</button>
                  <span>{calendarYear}-{String(calendarMonth).padStart(2, '0')}</span>
                  <button className="btn-secondary" onClick={() => reloadCalendar(calendarMonth === 12 ? calendarYear + 1 : calendarYear, calendarMonth === 12 ? 1 : calendarMonth + 1)}>&rarr;</button>
                </div>
                {calendarLoading && <p className="detail-meta-value">Loading calendar...</p>}
                {calendar && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(32px, 1fr))', gap: 4 }}>
                    {calendar.days.map((d) => {
                      const tone = {
                        present: 'var(--success)', half_day: 'var(--warning)', absent: 'var(--danger)',
                        leave: 'var(--warning)', holiday: 'var(--text-secondary)', week_off: 'var(--border-subtle)', work_day: 'var(--surface)',
                      }[d.event_type] || 'var(--surface)';
                      return (
                        <div key={d.date} title={`${d.date}: ${d.event_type.replace('_', ' ')}${d.holiday_name ? ` (${d.holiday_name})` : ''}`}
                          style={{ padding: 4, textAlign: 'center', fontSize: '0.75rem', borderRadius: 4, background: tone, border: '1px solid var(--border-subtle)' }}>
                          {new Date(d.date).getDate()}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </Card>
          )}
          <Table
            columns={[
              { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
              { key: 'working_hours', label: 'Working Hours' }, { key: 'overtime_hours', label: 'Overtime' },
              { key: 'attendance_status', label: 'Status' },
            ]}
            data={attendance}
            error={attendanceError}
            onRetry={load}
            emptyMessage="No attendance records for this employee yet."
          />
        </>
      )}

      {tab === 'Leave' && (
        <>
          {overview360?.leave_summary && (
            <Card title="Leave Summary">
              <div className="card-body">
                <p className="page-summary">{overview360.leave_summary.note}</p>
                <div className="detail-meta">
                  <div className="detail-meta-item"><span className="detail-meta-label">Pending Requests</span><span className="detail-meta-value">{overview360.leave_summary.pending_requests}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Approved This Year</span><span className="detail-meta-value">{overview360.leave_summary.approved_days_this_year} day(s)</span></div>
                  {Object.entries(overview360.leave_summary.approved_this_year_by_type || {}).map(([type, days]) => (
                    <div className="detail-meta-item" key={type}><span className="detail-meta-label">{type}</span><span className="detail-meta-value">{days} day(s)</span></div>
                  ))}
                </div>
              </div>
            </Card>
          )}
          <Table
            columns={[
              { key: 'leave_type', label: 'Type' },
              { key: 'start_date', label: 'From', render: (v) => new Date(v).toLocaleDateString() },
              { key: 'end_date', label: 'To', render: (v) => new Date(v).toLocaleDateString() },
              { key: 'days', label: 'Days' }, { key: 'reason', label: 'Reason' },
              { key: 'status', label: 'Status' },
            ]}
            data={leaves}
            error={leavesError}
            onRetry={load}
            emptyMessage="No leave requests for this employee yet."
          />
        </>
      )}

      {tab === 'Tasks' && (
        <>
          {overview360?.work_summary && (
            <div className="kpi-row">
              <KpiCard label="Active" value={overview360.work_summary.active} />
              <KpiCard label="Completed" value={overview360.work_summary.completed} />
              <KpiCard label="Blocked" value={overview360.work_summary.blocked} />
              <KpiCard label="Overdue" value={overview360.work_summary.overdue} />
              <KpiCard label="Upcoming" value={overview360.work_summary.upcoming} />
            </div>
          )}
          <Table
            columns={[
              { key: 'task_code', label: 'Task' }, { key: 'task_description', label: 'Description' },
              { key: 'status', label: 'Status' }, { key: 'completion_percent', label: 'Completion %' },
            ]}
            data={tasks}
            error={tasksError}
            onRetry={load}
            emptyMessage="No tasks assigned to this employee yet."
          />
        </>
      )}

      {tab === 'Production' && (
        <Table
          columns={[
            { key: 'job_code', label: 'Job' }, { key: 'machine', label: 'Machine' },
            { key: 'operation', label: 'Operation' }, { key: 'status', label: 'Status' },
          ]}
          data={productionJobs}
          error={productionJobsError}
          onRetry={load}
          emptyMessage="No production jobs for this employee yet."
        />
      )}

      {tab === 'Salary' && canViewHrDetails && (
        <>
          <Card title="Salary Slips">
            <div className="card-body">
              {salaryLoading && <p className="detail-meta-value">Loading...</p>}
              {!salaryLoading && salarySlips && (
                <Table
                  columns={[
                    { key: 'month', label: 'Month' }, { key: 'year', label: 'Year' },
                    { key: 'net_salary', label: 'Net Salary', render: (v) => formatCurrency(v) },
                    { key: 'advance_deduction', label: 'Advance Recovery', render: (v) => formatCurrency(v) },
                    { key: 'status', label: 'Status', render: (v) => <span className={statusClass(v)}>{v}</span> },
                  ]}
                  data={salarySlips}
                  emptyMessage="No salary slips for this employee yet."
                />
              )}
            </div>
          </Card>
          <Card title="Salary Advances">
            <div className="card-body">
              {!salaryLoading && salaryAdvances && (
                <Table
                  columns={[
                    { key: 'requested_amount', label: 'Requested', render: (v) => formatCurrency(v) },
                    { key: 'approved_amount', label: 'Approved', render: (v) => (v != null ? formatCurrency(v) : '-') },
                    { key: 'outstanding_amount', label: 'Outstanding', render: (v) => formatCurrency(v) },
                    { key: 'status', label: 'Status', render: (v) => <span className={statusClass(v)}>{v}</span> },
                  ]}
                  data={salaryAdvances}
                  emptyMessage="No salary advance requests for this employee yet."
                />
              )}
              <p className="page-summary" style={{ marginTop: 'var(--space-3)' }}>
                To create or finalize a slip, or approve/reject an advance, use <Link to="/salary-slips">Salary Slips</Link> or <Link to="/salary-advances">Salary Advances</Link>.
              </p>
            </div>
          </Card>
        </>
      )}

      {tab === 'Onboarding' && canViewHrDetails && (
        <Card title="Onboarding / Offboarding Checklist">
          <div className="card-body">
            <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
              <button className={lifecyclePhase === 'onboarding' ? 'btn-primary' : 'btn-secondary'} onClick={() => setLifecyclePhase('onboarding')}>Onboarding</button>
              <button className={lifecyclePhase === 'offboarding' ? 'btn-primary' : 'btn-secondary'} onClick={() => setLifecyclePhase('offboarding')}>Offboarding</button>
            </div>
            {lifecyclePhase === 'offboarding' && isPrivileged && (
              <div style={{ marginBottom: 'var(--space-4)', paddingBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-subtle)' }}>
                {exitDetailsError && <Alert type="error" message={exitDetailsError} onClose={() => setExitDetailsError('')} />}
                <Form
                  fields={[
                    { name: 'exit_date', label: 'Exit Date', type: 'date' },
                    { name: 'exit_reason', label: 'Exit Reason', type: 'textarea' },
                  ]}
                  onSubmit={handleSaveExitDetails} loading={exitDetailsSaving} submitText="Save Exit Details"
                  initialValues={{
                    exit_date: employee.exit_date ? employee.exit_date.slice(0, 10) : '',
                    exit_reason: employee.exit_reason || '',
                  }}
                />
              </div>
            )}
            {lifecycleError && <Alert type="error" message={lifecycleError} onClose={() => setLifecycleError('')} />}
            {lifecycleLoading && <p className="detail-meta-value">Loading...</p>}
            {!lifecycleLoading && lifecycle && lifecycle.items.length === 0 && (
              <p className="detail-meta-value">
                {lifecyclePhase === 'offboarding' ? 'No offboarding checklist yet - this starts once the employee is marked Inactive.' : 'No checklist items.'}
              </p>
            )}
            {!lifecycleLoading && lifecycle && lifecycle.items.length > 0 && (
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                {lifecycle.items.map((item) => (
                  <li key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-subtle)' }}>
                    <input
                      type="checkbox" checked={item.is_complete} disabled={item.auto_computed || !isPrivileged}
                      onChange={(e) => handleToggleLifecycleItem(item, e.target.checked)}
                    />
                    <span style={{ flex: 1, textDecoration: item.is_complete ? 'line-through' : 'none', color: item.is_complete ? 'var(--text-secondary)' : undefined }}>
                      {item.label}{item.auto_computed && <span className="detail-meta-label"> (automatic)</span>}
                    </span>
                    {item.completed_date && <span className="detail-meta-label">{new Date(item.completed_date).toLocaleDateString()}</span>}
                  </li>
                ))}
              </ul>
            )}
            <p className="page-summary" style={{ marginTop: 'var(--space-3)' }}>
              Progress: {lifecycle ? lifecycle.items.filter((i) => i.is_complete).length : 0}/{lifecycle ? lifecycle.items.length : 0} complete.
            </p>
          </div>
        </Card>
      )}

      {tab === 'Activity' && canViewHrDetails && (
        <Card title="Activity Timeline">
          <div className="card-body">
            {activityLoading && <p className="detail-meta-value">Loading timeline...</p>}
            {activityError && <Alert type="error" message={activityError} onClose={() => setActivityError('')} />}
            {activityTimeline && activityTimeline.entries.length === 0 && (
              <p className="detail-meta-value">Nothing recorded yet for this employee.</p>
            )}
            {activityTimeline && activityTimeline.entries.length > 0 && (
              <div className="table-container">
                <table className="data-table">
                  <thead><tr><th>Date</th><th>Type</th><th>Details</th></tr></thead>
                  <tbody>
                    {activityTimeline.entries.map((e, i) => (
                      <tr key={i}>
                        <td>{e.date ? new Date(e.date).toLocaleString() : '-'}</td>
                        <td><span className="status-badge status-neutral">{e.type.replace('_', ' ')}</span></td>
                        <td>
                          {e.path ? <Link to={e.path}>{e.text}</Link> : e.text}
                          {e.author ? <span className="detail-meta-label"> - {e.author}</span> : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Card>
      )}

      <Modal isOpen={activeAction === 'attendance'} title="Record Attendance" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'in_time', label: 'In Time', type: 'time' },
            { name: 'out_time', label: 'Out Time', type: 'time' },
            { name: 'attendance_status', label: 'Status', type: 'select', options: [
              { value: 'Present', label: 'Present' }, { value: 'Absent', label: 'Absent' },
              { value: 'Half Day', label: 'Half Day' }, { value: 'Leave', label: 'Leave' },
            ] },
            { name: 'remarks', label: 'Remarks' },
          ]}
          onSubmit={handleRecordAttendance} loading={actionLoading} submitText="Record Attendance"
          initialValues={{ date: today() }}
        />
      </Modal>

      <Modal isOpen={activeAction === 'task'} title="Assign Task" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'order_id', label: 'Project (Order)', type: 'select', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
            { name: 'task_description', label: 'Task Description', required: true, type: 'textarea' },
            { name: 'priority', label: 'Priority', type: 'select', options: [
              { value: 'Low', label: 'Low' }, { value: 'Medium', label: 'Medium' },
              { value: 'High', label: 'High' }, { value: 'Urgent', label: 'Urgent' },
            ] },
          ]}
          onSubmit={handleAssignTask} loading={actionLoading} submitText="Assign Task"
          initialValues={{ date: today() }}
        />
      </Modal>

      <Modal isOpen={activeAction === 'production'} title="Create Production Job" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'order_id', label: 'Project (Order)', type: 'select', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
            { name: 'machine', label: 'Machine' },
            { name: 'operation', label: 'Operation' },
            { name: 'planned_qty', label: 'Planned Quantity', type: 'number', required: true },
          ]}
          onSubmit={handleCreateProductionJob} loading={actionLoading} submitText="Create Production Job"
          initialValues={{ date: today() }}
        />
      </Modal>

      {tab === 'Documents' && isPrivileged && (
        <DocumentsPanel title="Employee Document Vault" enableCategorization api={{
          list: () => documentsAPI.list('employee', employeeId),
          upload: (file, description, extra) => documentsAPI.upload('employee', employeeId, file, description, extra),
          downloadUrl: (documentId) => documentsAPI.downloadUrl('employee', employeeId, documentId),
          remove: (documentId) => documentsAPI.remove('employee', employeeId, documentId),
        }} canUpload={isPrivileged} />
      )}
    </div>
  );
}

// --- AttendancePage.jsx (Attendance & Overtime Command Center) ---
// Redesigned per the confirmed proposal: a calendar-first, backend-
// aggregated view (attendance_period_summary/day_detail/team_grid/
// exceptions - see hr/services.py) replacing the old plain "every
// attendance record in a flat table" page. Every widget below loads
// independently (F138 P4 - one slow/failing panel must never block a
// sibling one), and every figure comes from a real backend calculation
// - nothing here re-derives attendance math client-side (see each
// service function's own docstring for the exact formula it owns).
function currentMonthKey() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function shiftMonthKey(key, delta) {
  const [y, m] = key.split('-').map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function monthKeyToRange(key) {
  const [y, m] = key.split('-').map(Number);
  const start = new Date(y, m - 1, 1);
  const end = new Date(y, m, 0);
  // Built from local Y/M/D rather than toISOString(), which converts
  // to UTC first and can silently shift the date by a day depending
  // on the viewer's timezone.
  const toISO = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { start: toISO(start), end: toISO(end) };
}

function monthKeyLabel(key) {
  const [y, m] = key.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

function monthKeyNameOnly(key) {
  const [y, m] = key.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: 'long' });
}

// Same event-type -> color mapping already established for the
// Employee 360 "Employee Calendar" widget above, reused here rather
// than invented a second time.
const ATTENDANCE_EVENT_TONE = {
  present: 'var(--success)', half_day: 'var(--warning)', absent: 'var(--danger)',
  leave: 'var(--warning)', holiday: 'var(--text-secondary)', week_off: 'var(--border-subtle)', work_day: 'var(--surface)',
};
const ATTENDANCE_EVENT_LABEL = {
  present: 'Present', half_day: 'Half Day', absent: 'Absent', leave: 'Leave',
  holiday: 'Holiday', week_off: 'Week Off', work_day: 'Unmarked working day',
};

const EXCEPTION_TYPE_LABEL = {
  missing_attendance: 'Missing attendance', holiday_conflict: 'Holiday conflict', leave_conflict: 'Leave conflict',
  missing_checkout: 'Missing checkout', shortfall: 'Hours shortfall', overtime_without_request: 'Unrequested overtime',
  unapproved_overtime: 'Pending overtime approval',
};
const EXCEPTION_SEVERITY_CLASS = { high: 'status-danger', medium: 'status-warning', low: 'status-info' };

const OVERTIME_STATUS_TABS = ['', 'Draft', 'Submitted', 'Approved', 'Rejected'];

function AttendancePage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';

  const [employees, setEmployees] = useState([]);
  // Which employee's Calendar/day-detail is being viewed - a Master
  // can switch this; a non-master is always locked to themselves.
  const [viewEmployeeId, setViewEmployeeId] = useState(isPrivileged ? '' : (user?.employee_id ? String(user.employee_id) : ''));
  const effectiveEmployeeId = isPrivileged ? viewEmployeeId : (user?.employee_id ? String(user.employee_id) : '');

  const [monthKey, setMonthKey] = useState(currentMonthKey());
  const { start, end } = useMemo(() => monthKeyToRange(monthKey), [monthKey]);

  const [activeTab, setActiveTab] = useState('calendar');
  const [error, setError] = useState('');

  // --- Calendar tab ---
  const [periodSummary, setPeriodSummary] = useState(null);
  const [periodLoading, setPeriodLoading] = useState(true);
  const [periodError, setPeriodError] = useState(false);
  const [dayDetail, setDayDetail] = useState(null); // { date, loading, error, data }

  const loadPeriodSummary = useCallback(() => {
    if (!effectiveEmployeeId) { setPeriodLoading(false); return; }
    setPeriodLoading(true);
    setPeriodError(false);
    attendanceAPI.periodSummary(effectiveEmployeeId, start, end)
      .then((res) => setPeriodSummary(res.data))
      .catch(() => setPeriodError(true))
      .finally(() => setPeriodLoading(false));
  }, [effectiveEmployeeId, start, end]);

  useEffect(() => { loadPeriodSummary(); }, [loadPeriodSummary]);

  const openDayDetail = (dateStr) => {
    if (!effectiveEmployeeId) return;
    setDayDetail({ date: dateStr, loading: true, error: false, data: null });
    attendanceAPI.dayDetail(effectiveEmployeeId, dateStr)
      .then((res) => setDayDetail({ date: dateStr, loading: false, error: false, data: res.data }))
      .catch(() => setDayDetail({ date: dateStr, loading: false, error: true, data: null }));
  };

  // --- Team Grid tab (master only) ---
  const [teamGrid, setTeamGrid] = useState(null);
  const [teamGridLoading, setTeamGridLoading] = useState(false);
  const [teamGridError, setTeamGridError] = useState(false);
  const [departmentFilter, setDepartmentFilter] = useState('');

  const loadTeamGrid = useCallback(() => {
    if (!isPrivileged) return;
    setTeamGridLoading(true);
    setTeamGridError(false);
    attendanceAPI.teamGrid(start, end, departmentFilter || undefined)
      .then((res) => setTeamGrid(res.data))
      .catch(() => setTeamGridError(true))
      .finally(() => setTeamGridLoading(false));
  }, [isPrivileged, start, end, departmentFilter]);

  useEffect(() => {
    if (activeTab === 'team' && isPrivileged) loadTeamGrid();
  }, [activeTab, isPrivileged, loadTeamGrid]);

  // --- Exceptions tab ---
  const [exceptions, setExceptions] = useState(null);
  const [exceptionsLoading, setExceptionsLoading] = useState(false);
  const [exceptionsError, setExceptionsError] = useState(false);

  const loadExceptions = useCallback(() => {
    if (!isPrivileged && !effectiveEmployeeId) { setExceptions({ exceptions: [] }); return; }
    setExceptionsLoading(true);
    setExceptionsError(false);
    attendanceAPI.exceptions(start, end, isPrivileged ? undefined : effectiveEmployeeId)
      .then((res) => setExceptions(res.data))
      .catch(() => setExceptionsError(true))
      .finally(() => setExceptionsLoading(false));
  }, [isPrivileged, effectiveEmployeeId, start, end]);

  useEffect(() => {
    if (activeTab === 'exceptions') loadExceptions();
  }, [activeTab, loadExceptions]);

  // --- Overtime Requests tab ---
  const [overtimeRequests, setOvertimeRequests] = useState([]);
  const [overtimeLoading, setOvertimeLoading] = useState(false);
  const [overtimeError, setOvertimeError] = useState(false);
  const [overtimeStatusFilter, setOvertimeStatusFilter] = useState('');
  const [overtimeEmployeeFilter, setOvertimeEmployeeFilter] = useState('');

  const loadOvertimeRequests = useCallback(() => {
    setOvertimeLoading(true);
    setOvertimeError(false);
    const params = {};
    if (overtimeStatusFilter) params.status = overtimeStatusFilter;
    if (isPrivileged && overtimeEmployeeFilter) params.employee_id = overtimeEmployeeFilter;
    overtimeRequestsAPI.list(params)
      .then((res) => setOvertimeRequests(res.data))
      .catch(() => setOvertimeError(true))
      .finally(() => setOvertimeLoading(false));
  }, [overtimeStatusFilter, overtimeEmployeeFilter, isPrivileged]);

  useEffect(() => {
    if (activeTab === 'overtime') loadOvertimeRequests();
  }, [activeTab, loadOvertimeRequests]);

  // Employees list - master only (employee selector + form options).
  // A non-master never sees anyone else's data, so there is nothing
  // for them to select here.
  useEffect(() => {
    if (!isPrivileged) return;
    employeesAPI.list().then((res) => {
      setEmployees(res.data);
      setViewEmployeeId((prev) => prev || String(res.data[0]?.id || ''));
    }).catch(() => {});
  }, [isPrivileged]);

  const departments = useMemo(
    () => Array.from(new Set(employees.map((e) => e.department).filter(Boolean))).sort(),
    [employees]
  );

  const refreshAfterMutation = () => {
    loadPeriodSummary();
    if (activeTab === 'team') loadTeamGrid();
    if (activeTab === 'exceptions') loadExceptions();
    if (activeTab === 'overtime') loadOvertimeRequests();
  };

  // --- Mark Attendance (existing single-record action, unchanged) ---
  const [showMarkAttendance, setShowMarkAttendance] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const handleMarkAttendance = async (formData) => {
    setActionLoading(true);
    setError('');
    try {
      await attendanceAPI.create({
        ...formData,
        employee_id: Number(formData.employee_id),
        date: new Date(formData.date).toISOString(),
        in_time: formData.in_time ? new Date(`${formData.date}T${formData.in_time}`).toISOString() : null,
        out_time: formData.out_time ? new Date(`${formData.date}T${formData.out_time}`).toISOString() : null,
      });
      setShowMarkAttendance(false);
      refreshAfterMutation();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to mark attendance');
    } finally {
      setActionLoading(false);
    }
  };

  // --- Adjust Overtime (the existing bulk "Manage Overtime" action -
  // POST /api/attendance/overtime - had a working backend route but no
  // frontend UI anywhere in the app; wired in here as part of this
  // redesign since it's the Master's direct multi-date correction
  // tool, distinct from the employee-initiated request workflow
  // below). ---
  const [showAdjustOvertime, setShowAdjustOvertime] = useState(false);

  const handleAdjustOvertime = async (formData) => {
    setActionLoading(true);
    setError('');
    const dates = String(formData.dates || '')
      .split(',')
      .map((d) => d.trim())
      .filter(Boolean);
    if (dates.length === 0) {
      setError('Enter at least one date.');
      setActionLoading(false);
      return;
    }
    try {
      await attendanceAPI.overtime({
        employee_id: Number(formData.employee_id),
        dates: dates.map((d) => new Date(d).toISOString()),
        hours: formData.hours,
        mode: formData.mode || 'add',
      });
      setShowAdjustOvertime(false);
      refreshAfterMutation();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update overtime hours.');
    } finally {
      setActionLoading(false);
    }
  };

  // --- Overtime Request workflow (Draft -> Submitted -> Approved/Rejected) ---
  const [showRequestOvertime, setShowRequestOvertime] = useState(false);
  const [editingRequest, setEditingRequest] = useState(null);
  const [cancelingRequest, setCancelingRequest] = useState(null);
  const [actioningRequest, setActioningRequest] = useState(null); // { request, type: 'approve'|'reject' }

  const handleCreateOrEditRequest = async (formData) => {
    setActionLoading(true);
    setError('');
    try {
      if (editingRequest) {
        await overtimeRequestsAPI.update(editingRequest.id, {
          date: new Date(formData.date).toISOString(),
          requested_hours: formData.requested_hours,
          reason: formData.reason,
          remarks: formData.remarks,
        });
      } else {
        await overtimeRequestsAPI.create({
          employee_id: isPrivileged ? Number(formData.employee_id) : Number(user.employee_id),
          date: new Date(formData.date).toISOString(),
          requested_hours: formData.requested_hours,
          reason: formData.reason,
          remarks: formData.remarks,
        });
      }
      setShowRequestOvertime(false);
      setEditingRequest(null);
      loadOvertimeRequests();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save this overtime request.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSubmitRequest = async (request) => {
    setActionLoading(true);
    setError('');
    try {
      await overtimeRequestsAPI.submit(request.id);
      loadOvertimeRequests();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit this overtime request.');
    } finally {
      setActionLoading(false);
    }
  };

  const confirmCancelRequest = async () => {
    if (!cancelingRequest) return;
    setActionLoading(true);
    setError('');
    try {
      await overtimeRequestsAPI.remove(cancelingRequest.id);
      setCancelingRequest(null);
      loadOvertimeRequests();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to cancel this request.');
      setCancelingRequest(null);
    } finally {
      setActionLoading(false);
    }
  };

  const handleApproveRequest = async (formData) => {
    setActionLoading(true);
    setError('');
    try {
      await overtimeRequestsAPI.approve(actioningRequest.request.id, {
        approved_hours: formData.approved_hours || undefined,
        remarks: formData.remarks,
      });
      setActioningRequest(null);
      loadOvertimeRequests();
      loadPeriodSummary();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to approve this request.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRejectRequest = async (formData) => {
    setActionLoading(true);
    setError('');
    try {
      await overtimeRequestsAPI.reject(actioningRequest.request.id, { rejection_reason: formData.rejection_reason });
      setActioningRequest(null);
      loadOvertimeRequests();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reject this request.');
    } finally {
      setActionLoading(false);
    }
  };

  const attendanceExportUrl = (overtimeOnly = false) => {
    const params = new URLSearchParams();
    if (effectiveEmployeeId) params.set('employee_id', effectiveEmployeeId);
    params.set('month', monthKeyNameOnly(monthKey));
    params.set('year', monthKey.split('-')[0]);
    if (overtimeOnly) params.set('overtime_only', 'true');
    return reportsAPI.downloadUrl(`attendance.xlsx?${params.toString()}`);
  };

  const canGoNextMonth = monthKey < currentMonthKey() || true; // future months are allowed (planning ahead), never blocked

  const viewingEmployeeName = isPrivileged
    ? (employees.find((e) => String(e.id) === String(viewEmployeeId))?.name || '')
    : (user?.full_name || user?.username || 'My');

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Attendance &amp; Overtime</h1>
          <p className="page-summary">Calendar, exceptions, and the overtime request workflow - all backed by real, aggregated data.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={attendanceExportUrl()} target="_blank" rel="noreferrer">Export Attendance</a>
          <a className="btn-secondary" href={attendanceExportUrl(true)} target="_blank" rel="noreferrer">Export Overtime</a>
          {isPrivileged && <button className="btn-secondary" onClick={() => setShowMarkAttendance(true)}>Mark Attendance</button>}
          {isPrivileged && <button className="btn-secondary" onClick={() => setShowAdjustOvertime(true)}>Adjust Overtime</button>}
          <button className="btn-primary" onClick={() => { setEditingRequest(null); setShowRequestOvertime(true); }}>Request Overtime</button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap', marginBottom: 'var(--space-4)' }}>
        <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
          <button className="btn-secondary" onClick={() => setMonthKey((k) => shiftMonthKey(k, -1))} aria-label="Previous month">&larr;</button>
          <strong>{monthKeyLabel(monthKey)}</strong>
          <button className="btn-secondary" onClick={() => setMonthKey((k) => shiftMonthKey(k, 1))} aria-label="Next month" disabled={!canGoNextMonth}>&rarr;</button>
        </div>
        {isPrivileged && (activeTab === 'calendar') && (
          <select className="form-input" style={{ maxWidth: 240 }} value={viewEmployeeId} onChange={(e) => setViewEmployeeId(e.target.value)}>
            {employees.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
        )}
      </div>

      <div className="tab-bar">
        <button className={activeTab === 'calendar' ? 'tab active' : 'tab'} onClick={() => setActiveTab('calendar')}>Calendar</button>
        {isPrivileged && <button className={activeTab === 'team' ? 'tab active' : 'tab'} onClick={() => setActiveTab('team')}>Team Grid</button>}
        <button className={activeTab === 'exceptions' ? 'tab active' : 'tab'} onClick={() => setActiveTab('exceptions')}>Exceptions</button>
        <button className={activeTab === 'overtime' ? 'tab active' : 'tab'} onClick={() => setActiveTab('overtime')}>Overtime Requests</button>
      </div>

      {activeTab === 'calendar' && (
        <>
          {!effectiveEmployeeId ? (
            <Card><div className="card-body"><p className="detail-meta-value">No employee record is linked to your account, so there is nothing to show here.</p></div></Card>
          ) : periodLoading ? (
            <Card><div className="card-body"><p className="detail-meta-value">Loading...</p></div></Card>
          ) : periodError ? (
            <Card><div className="card-body">
              <p className="detail-meta-value">Could not load this month's attendance.</p>
              <button className="btn-secondary" onClick={loadPeriodSummary}>Retry</button>
            </div></Card>
          ) : periodSummary && (
            <>
              <div className="kpi-row">
                <KpiCard label="Scheduled Hours" value={periodSummary.summary.scheduled_hours} />
                <KpiCard label="Worked Hours" value={periodSummary.summary.worked_hours} />
                <KpiCard label="Payable Hours" value={periodSummary.summary.payable_hours} />
                <KpiCard label="Overtime Hours" value={periodSummary.summary.overtime_hours} />
                <KpiCard label="Shortfall Hours" value={periodSummary.summary.shortfall_hours} tone={periodSummary.summary.shortfall_hours > 0 ? 'warning' : 'default'} />
                <KpiCard label="Attendance %" value={periodSummary.summary.attendance_percent != null ? `${periodSummary.summary.attendance_percent}%` : '-'} />
              </div>

              <Card title={`${viewingEmployeeName}'s Calendar`}>
                <div className="card-body">
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(40px, 1fr))', gap: 4, marginBottom: 'var(--space-3)' }}>
                    {/* Leading blank cells so the 1st of the month lines up under its real weekday. */}
                    {Array.from({ length: new Date(periodSummary.days[0].date).getDay() }).map((_, i) => <div key={`pad-${i}`} />)}
                    {periodSummary.days.map((d) => (
                      <button
                        key={d.date}
                        type="button"
                        onClick={() => openDayDetail(d.date)}
                        title={`${d.date}: ${ATTENDANCE_EVENT_LABEL[d.event_type] || d.event_type}${d.holiday_name ? ` (${d.holiday_name})` : ''}${d.overtime_hours ? ` · ${d.overtime_hours}h OT` : ''}`}
                        style={{
                          padding: 4, textAlign: 'center', fontSize: '0.75rem', borderRadius: 4,
                          background: ATTENDANCE_EVENT_TONE[d.event_type] || 'var(--surface)',
                          border: d.has_missing_checkout ? '2px solid var(--danger)' : '1px solid var(--border-subtle)',
                          cursor: 'pointer', color: 'inherit', font: 'inherit', position: 'relative',
                        }}
                      >
                        {new Date(d.date).getDate()}
                        {d.overtime_hours > 0 && <div style={{ fontSize: '0.65rem', fontWeight: 700 }}>+{d.overtime_hours}h</div>}
                      </button>
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    {Object.entries(ATTENDANCE_EVENT_LABEL).map(([key, label]) => (
                      <span key={key} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ width: 10, height: 10, borderRadius: 2, background: ATTENDANCE_EVENT_TONE[key], display: 'inline-block' }} />
                        {label}
                      </span>
                    ))}
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 10, height: 10, borderRadius: 2, border: '2px solid var(--danger)', display: 'inline-block' }} />
                      Missing checkout
                    </span>
                  </div>
                </div>
              </Card>
            </>
          )}
        </>
      )}

      {activeTab === 'team' && isPrivileged && (
        <Card title="Team Attendance Grid">
          <div className="card-body">
            <div style={{ marginBottom: 'var(--space-3)' }}>
              <select className="form-input" style={{ maxWidth: 240 }} value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)}>
                <option value="">All Departments</option>
                {departments.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            {teamGridLoading ? (
              <p className="detail-meta-value">Loading...</p>
            ) : teamGridError ? (
              <>
                <p className="detail-meta-value">Could not load the team grid.</p>
                <button className="btn-secondary" onClick={loadTeamGrid}>Retry</button>
              </>
            ) : teamGrid && teamGrid.employees.length === 0 ? (
              <p className="detail-meta-value">No active employees found.</p>
            ) : teamGrid && (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Employee</th>
                      {teamGrid.employees[0].days.map((d) => (
                        <th key={d.date} scope="col" style={{ textAlign: 'center', fontSize: '0.7rem', padding: '4px 2px' }}>{new Date(d.date).getDate()}</th>
                      ))}
                      <th scope="col">Attendance %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {teamGrid.employees.map((emp) => (
                      <tr key={emp.employee_id}>
                        <td style={{ whiteSpace: 'nowrap' }}>{emp.employee_name}</td>
                        {emp.days.map((d) => (
                          <td key={d.date} style={{ padding: 2, textAlign: 'center' }}>
                            <div
                              title={`${d.date}: ${ATTENDANCE_EVENT_LABEL[d.event_type] || d.event_type}${d.overtime_hours ? ` · ${d.overtime_hours}h OT` : ''}${d.shortfall_hours ? ` · ${d.shortfall_hours}h short` : ''}`}
                              style={{
                                width: 20, height: 20, margin: '0 auto', borderRadius: 3,
                                background: ATTENDANCE_EVENT_TONE[d.event_type] || 'var(--surface)',
                                border: d.has_missing_checkout ? '2px solid var(--danger)' : '1px solid var(--border-subtle)',
                              }}
                            />
                          </td>
                        ))}
                        <td>{emp.summary.attendance_percent != null ? `${emp.summary.attendance_percent}%` : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Card>
      )}

      {activeTab === 'exceptions' && (
        <Table
          columns={[
            ...(isPrivileged ? [{ key: 'employee_name', label: 'Employee' }] : []),
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'type', label: 'Type', render: (v) => EXCEPTION_TYPE_LABEL[v] || v },
            { key: 'message', label: 'Details' },
            { key: 'severity', label: 'Severity', render: (v) => <span className={`status-badge ${EXCEPTION_SEVERITY_CLASS[v] || 'status-info'}`}>{v}</span> },
          ]}
          data={exceptions?.exceptions || []}
          loading={exceptionsLoading}
          error={exceptionsError}
          onRetry={loadExceptions}
          emptyMessage="No exceptions for this period - nothing needs attention."
        />
      )}

      {activeTab === 'overtime' && (
        <>
          <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', marginBottom: 'var(--space-3)' }}>
            <select className="form-input" style={{ maxWidth: 200 }} value={overtimeStatusFilter} onChange={(e) => setOvertimeStatusFilter(e.target.value)}>
              {OVERTIME_STATUS_TABS.map((s) => <option key={s || 'all'} value={s}>{s || 'All Statuses'}</option>)}
            </select>
            {isPrivileged && (
              <select className="form-input" style={{ maxWidth: 240 }} value={overtimeEmployeeFilter} onChange={(e) => setOvertimeEmployeeFilter(e.target.value)}>
                <option value="">All Employees</option>
                {employees.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            )}
          </div>
          <Table
            loading={overtimeLoading}
            error={overtimeError}
            onRetry={loadOvertimeRequests}
            columns={[
              ...(isPrivileged ? [{ key: 'employee_name', label: 'Employee' }] : []),
              { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
              { key: 'requested_hours', label: 'Requested' },
              { key: 'approved_hours', label: 'Approved', render: (v) => (v != null ? v : '-') },
              { key: 'status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
              { key: 'reason', label: 'Reason' },
              {
                key: 'actions', label: '',
                render: (v, row) => {
                  const canManage = isPrivileged || String(row.employee_id) === String(user?.employee_id);
                  return (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {row.status === 'Draft' && canManage && (
                        <>
                          <button className="btn-link" onClick={() => { setEditingRequest(row); setShowRequestOvertime(true); }}>Edit</button>
                          <button className="btn-link" onClick={() => handleSubmitRequest(row)}>Submit</button>
                          <button className="btn-link" style={{ color: 'var(--danger)' }} onClick={() => setCancelingRequest(row)}>Cancel</button>
                        </>
                      )}
                      {row.status === 'Submitted' && isPrivileged && (
                        <>
                          <button className="btn-link" onClick={() => setActioningRequest({ request: row, type: 'approve' })}>Approve</button>
                          <button className="btn-link" style={{ color: 'var(--danger)' }} onClick={() => setActioningRequest({ request: row, type: 'reject' })}>Reject</button>
                        </>
                      )}
                    </div>
                  );
                },
              },
            ]}
            data={overtimeRequests}
            emptyMessage={isPrivileged ? 'No overtime requests for this filter.' : "You haven't requested any overtime yet."}
          />
        </>
      )}

      {/* --- Day Detail drawer --- */}
      <Modal isOpen={!!dayDetail} title={dayDetail ? new Date(dayDetail.date).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) : ''} onClose={() => setDayDetail(null)} size="wide">
        {dayDetail?.loading && <p className="detail-meta-value">Loading...</p>}
        {dayDetail?.error && <p className="detail-meta-value">Could not load this day's detail.</p>}
        {dayDetail?.data && (
          <>
            <div className="kpi-row" style={{ marginBottom: 'var(--space-4)' }}>
              <KpiCard label="Status" value={ATTENDANCE_EVENT_LABEL[dayDetail.data.event_type] || dayDetail.data.event_type} />
              <KpiCard label="Scheduled" value={`${dayDetail.data.scheduled_hours}h`} />
              <KpiCard label="Worked" value={`${dayDetail.data.worked_hours}h`} />
              <KpiCard label="Overtime" value={`${dayDetail.data.overtime_hours}h`} />
              <KpiCard label="Shortfall" value={`${dayDetail.data.shortfall_hours}h`} />
            </div>
            {dayDetail.data.holiday_name && <p className="detail-meta-value">Holiday: {dayDetail.data.holiday_name}</p>}
            <h3 style={{ fontSize: '0.95rem', marginTop: 'var(--space-4)' }}>Timeline</h3>
            {dayDetail.data.timeline.length === 0 ? (
              <p className="detail-meta-value">No timed work items for this day.</p>
            ) : (
              <ul style={{ paddingLeft: 18 }}>
                {dayDetail.data.timeline.map((entry) => (
                  <li key={`${entry.type}-${entry.id}`} style={{ marginBottom: 4 }}>
                    <strong>{new Date(entry.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}-{new Date(entry.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong>
                    {' - '}{entry.description || entry.operation_name}
                    {entry.order_code && ` (${entry.order_code})`}
                  </li>
                ))}
              </ul>
            )}
            {dayDetail.data.unscheduled_work.length > 0 && (
              <>
                <h3 style={{ fontSize: '0.95rem', marginTop: 'var(--space-4)' }}>Other work (no fixed time)</h3>
                <ul style={{ paddingLeft: 18 }}>
                  {dayDetail.data.unscheduled_work.map((entry) => (
                    <li key={`${entry.type}-${entry.id}`}>
                      {entry.description || entry.operation_name}
                      {entry.order_code && ` (${entry.order_code})`}
                      {' - '}{entry.status}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </Modal>

      <Modal isOpen={showMarkAttendance} title="Mark Attendance" onClose={() => setShowMarkAttendance(false)}>
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'employee_id', label: 'Employee', type: 'select', required: true, options: employees.map((e) => ({ value: e.id, label: e.name })) },
            { name: 'in_time', label: 'In Time', type: 'time' },
            { name: 'out_time', label: 'Out Time', type: 'time' },
            {
              name: 'attendance_status', label: 'Status', type: 'select', options: [
                { value: 'Present', label: 'Present' }, { value: 'Absent', label: 'Absent' },
                { value: 'Half Day', label: 'Half Day' }, { value: 'Leave', label: 'Leave' },
              ],
            },
            { name: 'remarks', label: 'Remarks' },
          ]}
          onSubmit={handleMarkAttendance} loading={actionLoading} submitText="Mark Attendance"
          initialValues={{ date: today() }}
        />
      </Modal>

      <Modal isOpen={showAdjustOvertime} title="Adjust Overtime" onClose={() => setShowAdjustOvertime(false)}>
        <Form
          fields={[
            { name: 'employee_id', label: 'Employee', type: 'select', required: true, options: employees.map((e) => ({ value: e.id, label: e.name })) },
            { name: 'dates', label: 'Dates', required: true, placeholder: 'YYYY-MM-DD, YYYY-MM-DD, ...', hint: 'Comma-separated - one or more dates.' },
            { name: 'hours', label: 'Hours', type: 'number', required: true },
            {
              name: 'mode', label: 'Mode', type: 'select', options: [
                { value: 'add', label: 'Add to existing overtime' },
                { value: 'set', label: 'Set (replace) overtime' },
              ],
            },
          ]}
          onSubmit={handleAdjustOvertime} loading={actionLoading} submitText="Apply"
          initialValues={{ mode: 'add' }}
        />
      </Modal>

      <Modal isOpen={showRequestOvertime} title={editingRequest ? 'Edit Overtime Request' : 'Request Overtime'} onClose={() => { setShowRequestOvertime(false); setEditingRequest(null); }}>
        <Form
          fields={[
            ...(isPrivileged && !editingRequest ? [{ name: 'employee_id', label: 'Employee', type: 'select', required: true, options: employees.map((e) => ({ value: e.id, label: e.name })) }] : []),
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'requested_hours', label: 'Hours', type: 'number', required: true },
            { name: 'reason', label: 'Reason', type: 'textarea' },
            { name: 'remarks', label: 'Remarks', type: 'textarea' },
          ]}
          onSubmit={handleCreateOrEditRequest} loading={actionLoading} submitText={editingRequest ? 'Save' : 'Save as Draft'}
          initialValues={editingRequest ? {
            date: editingRequest.date.slice(0, 10), requested_hours: String(editingRequest.requested_hours),
            reason: editingRequest.reason || '', remarks: editingRequest.remarks || '',
          } : { date: today() }}
        />
      </Modal>

      <ConfirmDialog
        isOpen={!!cancelingRequest}
        title="Cancel Overtime Request"
        message="This will permanently withdraw this draft request."
        confirmLabel="Cancel Request"
        onConfirm={confirmCancelRequest}
        onCancel={() => setCancelingRequest(null)}
        loading={actionLoading}
      />

      <Modal isOpen={actioningRequest?.type === 'approve'} title="Approve Overtime Request" onClose={() => setActioningRequest(null)}>
        <Form
          fields={[
            { name: 'approved_hours', label: 'Approved Hours', type: 'number', placeholder: actioningRequest ? `Default: ${actioningRequest.request.requested_hours}` : '' },
            { name: 'remarks', label: 'Remarks', type: 'textarea' },
          ]}
          onSubmit={handleApproveRequest} loading={actionLoading} submitText="Approve"
        />
      </Modal>

      <Modal isOpen={actioningRequest?.type === 'reject'} title="Reject Overtime Request" onClose={() => setActioningRequest(null)}>
        <Form
          fields={[{ name: 'rejection_reason', label: 'Reason', type: 'textarea' }]}
          onSubmit={handleRejectRequest} loading={actionLoading} submitText="Reject"
        />
      </Modal>
    </div>
  );
}

// --- LeavesPage.jsx ---
function LeavesPage() {
  const { user } = useSelector((state) => state.auth);
  const [leaves, setLeaves] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [decidingId, setDecidingId] = useState(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = (status, refreshEmployees = true) => {
    setPageLoading(true);
    setLoadError(false);
    leavesAPI.list(status ? { status } : undefined).then((res) => setLeaves(res.data)).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
    if (refreshEmployees) employeesAPI.list().then((res) => setEmployees(res.data));
  };
  useEffect(() => load(), []);

  const handleFilter = (e) => {
    const value = e.target.value;
    setStatusFilter(value);
    load(value);
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    const start = new Date(formData.start_date);
    const end = new Date(formData.end_date);
    if (end < start) {
      setError('To date cannot be before From date');
      setLoading(false);
      return;
    }
    try {
      await leavesAPI.create({
        ...formData,
        employee_id: Number(formData.employee_id),
        start_date: new Date(formData.start_date).toISOString(),
        end_date: new Date(formData.end_date).toISOString(),
      });
      setShowAdd(false);
      load(statusFilter);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit leave request');
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = async (leave, status) => {
    setDecidingId(leave.id);
    setError('');
    try {
      await leavesAPI.update(leave.id, { status, approved_by: user?.full_name || user?.username });
      load(statusFilter, false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update leave request');
    } finally {
      setDecidingId(null);
    }
  };

  const columns = [
    { key: 'employee_id', label: 'Employee', render: (v) => employees.find((e) => e.id === v)?.name || v },
    { key: 'leave_type', label: 'Type' },
    { key: 'start_date', label: 'From', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'end_date', label: 'To', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'days', label: 'Days' }, { key: 'reason', label: 'Reason' },
    { key: 'status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
    {
      key: 'decision_action', label: '', render: (v, row) => (
        row.status === 'Pending' && (
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn-link" onClick={() => handleDecision(row, 'Approved')} disabled={decidingId === row.id}>
              {decidingId === row.id ? '...' : 'Approve'}
            </button>
            <button className="btn-link" style={{ color: 'var(--danger)' }} onClick={() => handleDecision(row, 'Rejected')} disabled={decidingId === row.id}>
              {decidingId === row.id ? '...' : 'Reject'}
            </button>
          </div>
        )
      ),
    },
  ];

  const fields = [
    { name: 'employee_id', label: 'Employee', type: 'select', required: true, options: employees.map((e) => ({ value: e.id, label: e.name })) },
    { name: 'leave_type', label: 'Leave Type', type: 'select', required: true, options: [
      { value: 'PL', label: 'Privileged Leave (PL)' }, { value: 'CL', label: 'Casual Leave (CL)' }, { value: 'SL', label: 'Sick Leave (SL)' },
    ] },
    { name: 'start_date', label: 'From', type: 'date', required: true },
    { name: 'end_date', label: 'To', type: 'date', required: true },
    {
      name: 'days', label: 'Number of Days', type: 'computed',
      hint: 'Calculated automatically from From/To (inclusive)',
      compute: (formData) => {
        if (!formData.start_date || !formData.end_date) return '';
        const start = new Date(formData.start_date);
        const end = new Date(formData.end_date);
        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '';
        if (end < start) return 'Invalid: To is before From';
        const msPerDay = 24 * 60 * 60 * 1000;
        const days = Math.round((end - start) / msPerDay) + 1;
        return String(days);
      },
    },
    { name: 'reason', label: 'Reason', type: 'textarea' },
  ];

  const leavesExportUrl = () => {
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);
    const qs = params.toString();
    return reportsAPI.downloadUrl(`leaves.xlsx${qs ? `?${qs}` : ''}`);
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Leave Requests</h1>
          <p className="page-summary">Review and approve employee leave requests.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={leavesExportUrl()} target="_blank" rel="noreferrer">
            {statusFilter ? 'Export Filtered' : 'Export All'}
          </a>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>Request Leave</button>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <form className="page-search" onSubmit={(e) => e.preventDefault()}>
        <select className="form-input" value={statusFilter} onChange={handleFilter}>
          <option value="">All Statuses</option>
          <option value="Pending">Pending</option>
          <option value="Approved">Approved</option>
          <option value="Rejected">Rejected</option>
        </select>
      </form>
      <Table columns={columns} data={leaves} loading={pageLoading} error={loadError} onRetry={() => load(statusFilter)} emptyMessage="No leave requests yet." />
      <Modal isOpen={showAdd} title="Request Leave" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Submit Request" />
      </Modal>
    </div>
  );
}

// --- CompanyHolidaysPage.jsx ---
function CompanyHolidaysPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';

  const [holidays, setHolidays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingHoliday, setEditingHoliday] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [yearFilter, setYearFilter] = useState('all');
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    holidaysAPI.list()
      .then((res) => setHolidays(res.data))
      .catch(() => setError('Could not load holidays.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSave = async (formData) => {
    setSaving(true);
    setError('');
    try {
      const payload = {
        date: formData.date, name: formData.name,
        is_working: formData.is_working === 'true' || formData.is_working === true,
        remarks: formData.remarks || null,
      };
      if (editingHoliday) {
        await holidaysAPI.update(editingHoliday.id, payload);
      } else {
        await holidaysAPI.create(payload);
      }
      setShowForm(false);
      setEditingHoliday(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save this holiday.');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await holidaysAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not delete this holiday.');
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  const years = [...new Set(holidays.map((h) => h.date.slice(0, 4)))].sort();
  const filteredHolidays = yearFilter === 'all' ? holidays : holidays.filter((h) => h.date.startsWith(yearFilter));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Company Holidays</h1>
          <p className="page-summary">
            Holidays and special working days affect attendance and payroll calculations across every year - not just 2026.
          </p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('company-holidays.xlsx')}>Export Excel</a>
          {isPrivileged && (
            <button className="btn-secondary" onClick={() => navigate('/company-holidays/import')}>Import Excel</button>
          )}
          {isPrivileged && (
            <button className="btn-primary" onClick={() => { setEditingHoliday(null); setShowForm(true); }}>Add Holiday</button>
          )}
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {years.length > 1 && (
        <div style={{ marginBottom: 16 }}>
          <select className="form-input" style={{ maxWidth: 160 }} value={yearFilter} onChange={(e) => setYearFilter(e.target.value)}>
            <option value="all">All Years</option>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      )}

      {loading ? (
        <p>Loading...</p>
      ) : filteredHolidays.length === 0 && !error ? (
        <Card><div className="card-body">No holidays recorded yet.</div></Card>
      ) : !error && (
        <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Date</th><th>Name</th><th>Type</th><th>Remarks</th>{isPrivileged && <th></th>}
            </tr>
          </thead>
          <tbody>
            {filteredHolidays.map((h) => (
              <tr key={h.id}>
                <td>{new Date(h.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
                <td>{h.name}</td>
                <td>
                  <span className={`status-badge ${h.is_working ? 'status-info' : 'status-gold'}`}>
                    {h.is_working ? 'Special Working Day' : 'Holiday'}
                  </span>
                </td>
                <td>{h.remarks || '-'}</td>
                {isPrivileged && (
                  <td>
                    <button className="btn-link" onClick={() => { setEditingHoliday(h); setShowForm(true); }}>Edit</button>
                    <button className="btn-link" onClick={() => setPendingDelete(h)}>Delete</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}

      <Modal isOpen={showForm} title={editingHoliday ? 'Edit Holiday' : 'Add Holiday'} onClose={() => { setShowForm(false); setEditingHoliday(null); }}>
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'name', label: 'Holiday Name', required: true },
            { name: 'is_working', label: 'Type', type: 'select', required: true, options: [
              { value: 'false', label: 'Holiday' }, { value: 'true', label: 'Special Working Day' },
            ] },
            { name: 'remarks', label: 'Remarks', type: 'textarea' },
          ]}
          onSubmit={handleSave}
          loading={saving}
          submitText={editingHoliday ? 'Save Changes' : 'Add Holiday'}
          initialValues={editingHoliday ? {
            date: editingHoliday.date, name: editingHoliday.name,
            is_working: String(editingHoliday.is_working), remarks: editingHoliday.remarks || '',
          } : {}}
        />
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDelete}
        message={pendingDelete ? `Delete "${pendingDelete.name}" (${pendingDelete.date})? This cannot be undone.` : ''}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
        loading={deleting}
      />
    </div>
  );
}

// --- HolidayImportPage.jsx ---
function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function rowStatus(row, willOverwrite) {
  if (row.errors.length > 0) return { label: 'ERROR', className: 'status-danger' };
  if (row.is_duplicate) return willOverwrite
    ? { label: 'WILL UPDATE existing holiday', className: 'status-info' }
    : { label: 'ALREADY EXISTS - will be skipped', className: 'status-warning' };
  return { label: 'NEW', className: 'status-gold' };
}

function HolidayImportPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({});
  const [overwriteRows, setOverwriteRows] = useState({});
  const [stage, setStage] = useState('empty'); // empty | selected | validating | preview | importing | success | error
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [downloadingErrors, setDownloadingErrors] = useState(false);
  const fileInputRef = useRef(null);

  const resetFile = () => {
    setFile(null);
    setPreview(null);
    setExcludedRows({});
    setOverwriteRows({});
    setStage('empty');
    setError('');
  };

  const handleFileSelected = (selected) => {
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith('.xlsx')) {
      setError('Please choose a .xlsx file - other formats are not supported.');
      return;
    }
    setFile(selected);
    setPreview(null);
    setResult(null);
    setError('');
    setStage('selected');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFileSelected(e.dataTransfer.files?.[0]);
  };

  const handleValidate = async () => {
    if (!file) return;
    setStage('validating');
    setError('');
    try {
      const res = await holidayImportAPI.preview(file);
      setPreview(res.data);
      setExcludedRows({});
      setOverwriteRows({});
      setStage('preview');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not read this file. Make sure you used the downloaded template.');
      setStage('selected');
    }
  };

  const handleImport = async () => {
    if (!preview) return;
    setStage('importing');
    setError('');
    try {
      const rowsToCommit = preview.rows
        .filter((r) => r.errors.length === 0)
        .map((r) => ({
          date: r.date, name: r.name, is_working: r.is_working, remarks: r.remarks,
          skip: !!excludedRows[r.row_number],
          overwrite_existing: r.is_duplicate ? !!overwriteRows[r.row_number] : false,
        }));
      const res = await holidayImportAPI.commit(rowsToCommit);
      setResult(res.data);
      setPreview(null);
      setFile(null);
      setStage(res.data.error ? 'error' : 'success');
    } catch (err) {
      setError(err.response?.data?.detail || 'Import failed. Please try again.');
      setStage('preview');
    }
  };

  const downloadErrorReport = async () => {
    if (!file) return;
    setDownloadingErrors(true);
    setError('');
    try {
      const res = await holidayImportAPI.errorReport(file);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Holiday_Import_Errors.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not generate the error report. Please try again.');
    } finally {
      setDownloadingErrors(false);
    }
  };

  const errorCount = preview ? preview.rows.filter((r) => r.errors.length > 0).length : 0;
  const importableCount = preview
    ? preview.rows.filter((r) => r.errors.length === 0 && !excludedRows[r.row_number]).length
    : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Import Company Holidays from Excel</h1>
          <p className="page-summary">
            Download the template, fill in one row per date, then upload it here for review before anything is saved.
            A date that already has a holiday is flagged - you choose whether to update it or leave it as-is.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => navigate('/company-holidays')}>Back to Company Holidays</button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {(stage === 'success' || stage === 'error') && result && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>{stage === 'error' ? 'Import Partially Complete' : 'Import Complete'}</h3>
            <div className="import-result-grid">
              <div><span className="import-result-number">{result.created}</span><span className="import-result-label">New Holidays</span></div>
              <div><span className="import-result-number">{result.updated}</span><span className="import-result-label">Updated</span></div>
              <div><span className="import-result-number">{result.skipped}</span><span className="import-result-label">Skipped</span></div>
            </div>
            {result.error && <Alert type="warning" message={result.error} />}
            <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
              <button className="btn-primary" onClick={() => navigate('/company-holidays')}>View Company Holidays</button>
              <button className="btn-secondary" onClick={resetFile}>Import Another File</button>
            </div>
          </div>
        </Card>
      )}

      {(stage === 'empty' || stage === 'selected' || stage === 'validating') && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={holidayImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
                Download Template
              </a>
            </p>

            {!file && (
              <div
                className={`import-dropzone ${dragOver ? 'drag-over' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
              >
                <p className="import-dropzone-title">Drag and drop your Excel file here</p>
                <p className="import-dropzone-hint">or click to choose a file &middot; accepts .xlsx only</p>
                <input
                  ref={fileInputRef} type="file" accept=".xlsx" style={{ display: 'none' }}
                  onChange={(e) => handleFileSelected(e.target.files?.[0])}
                />
              </div>
            )}

            {file && (
              <div className="import-file-selected">
                <div>
                  <span className="import-file-name">{file.name}</span>
                  <span className="import-file-size">{formatFileSize(file.size)}</span>
                </div>
                <button className="btn-link" onClick={resetFile} disabled={stage === 'validating'}>Remove</button>
              </div>
            )}

            <button
              className="btn-primary" style={{ marginTop: 16 }}
              onClick={handleValidate} disabled={!file || stage === 'validating'}
            >
              {stage === 'validating' ? 'Validating...' : 'Validate & Preview'}
            </button>
          </div>
        </Card>
      )}

      {(stage === 'preview' || stage === 'importing') && preview && (
        <>
          <Card>
            <div className="card-body">
              <h3 style={{ marginTop: 0 }}>{preview.total_rows} row{preview.total_rows !== 1 ? 's' : ''} detected</h3>
              <p>
                {preview.new_rows} new &middot;{' '}
                {preview.duplicate_rows} matching an existing holiday &middot;{' '}
                {preview.error_rows} row{preview.error_rows !== 1 ? 's' : ''} rejected
                {preview.error_rows > 0 ? ' (won\u2019t be imported)' : ''}.
              </p>
              {preview.error_rows > 0 && (
                <button className="btn-link" onClick={downloadErrorReport} disabled={downloadingErrors}>
                  {downloadingErrors ? 'Preparing report...' : 'Download Error Report'}
                </button>
              )}
            </div>
          </Card>

          <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th></th><th>Date</th><th>Name</th><th>Type</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r) => {
                const willOverwrite = !!overwriteRows[r.row_number];
                const status = rowStatus(r, willOverwrite);
                const canExclude = r.errors.length === 0;
                return (
                  <tr key={r.row_number} style={{ opacity: excludedRows[r.row_number] ? 0.5 : 1 }}>
                    <td>
                      {canExclude && (
                        <input
                          type="checkbox" checked={!excludedRows[r.row_number]}
                          onChange={(e) => setExcludedRows((prev) => ({ ...prev, [r.row_number]: !e.target.checked }))}
                        />
                      )}
                    </td>
                    <td>{r.date || '-'}</td>
                    <td>{r.name || '-'}</td>
                    <td>{r.is_working ? 'Special Working Day' : 'Holiday'}</td>
                    <td>
                      <span className={`status-badge ${status.className}`}>{status.label}</span>
                      {r.is_duplicate && !excludedRows[r.row_number] && (
                        <label style={{ display: 'block', fontSize: '0.85rem', marginTop: 4 }}>
                          <input
                            type="checkbox" checked={willOverwrite}
                            onChange={(e) => setOverwriteRows((prev) => ({ ...prev, [r.row_number]: e.target.checked }))}
                          />{' '}Update the existing holiday with this row's values
                        </label>
                      )}
                      {r.errors.length > 0 && (
                        <div className="import-row-error">{r.errors.join('; ')}</div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>

          <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="btn-primary" onClick={handleImport} disabled={stage === 'importing' || importableCount === 0}>
              {stage === 'importing' ? 'Importing...' : `Confirm Import (${importableCount} row${importableCount !== 1 ? 's' : ''})`}
            </button>
            <button className="btn-secondary" onClick={resetFile} disabled={stage === 'importing'}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}

// --- AttendanceLeaveHub.jsx ---
// Woodful navigation/module-structure consolidation: Attendance,
// Leave, and Company Holidays used to be three separate primary
// Sidebar destinations. They are now one "Attendance & Leave"
// workspace reached from a single nav item (/attendance-leave). This
// is a thin tab switcher over the exact same three page components
// above - same components, same API calls, same data-loading, same
// role checks. Nothing here is a second implementation of any of
// them, and only the selected tab is mounted at a time, so switching
// tabs never fetches more than one tab's data at once (no new/
// duplicate network traffic versus visiting each page directly).
// /attendance, /leaves, and /company-holidays keep working exactly as
// before - this hub does not replace or redirect them.
//
// Known trade-off (disclosed, not hidden): each of the three pages
// still renders its own full page header ("Attendance & Overtime" /
// "Leave Requests" / "Company Holidays") below this hub's tab bar,
// since none of their internals were changed to avoid regressing
// already-complex, working components. This means a little more
// vertical space than a from-scratch single-header design would use,
// but preserves every existing visual element and behavior untouched.
const ATTENDANCE_LEAVE_TABS = ['Attendance', 'Leave', 'Holiday Calendar'];

function AttendanceLeaveHub() {
  const [tab, setTab] = useState('Attendance');
  return (
    <div className="page attendance-leave-hub">
      <div className="page-header">
        <div>
          <h1>Attendance &amp; Leave</h1>
          <p className="page-summary">Attendance, leave requests, and the company holiday calendar in one place.</p>
        </div>
      </div>
      <div className="tab-bar">
        {ATTENDANCE_LEAVE_TABS.map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)} type="button">{t}</button>
        ))}
      </div>
      {tab === 'Attendance' && <AttendancePage />}
      {tab === 'Leave' && <LeavesPage />}
      {tab === 'Holiday Calendar' && <CompanyHolidaysPage />}
    </div>
  );
}

export { EmployeesPage, EmployeeDetailPage, AttendancePage, LeavesPage, CompanyHolidaysPage, HolidayImportPage, AttendanceLeaveHub };
