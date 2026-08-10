import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { employeesAPI, attendanceAPI, dailyTasksAPI, productionJobsAPI, leavesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Card from '../components/common/Card';

function money(v) { return `Rs ${Number(v || 0).toLocaleString()}`; }

const TABS = ['Overview', 'Attendance', 'Leave', 'Tasks', 'Production'];

function EmployeeDetailPage() {
  const { employeeId } = useParams();
  const [employee, setEmployee] = useState(null);
  const [attendance, setAttendance] = useState([]);
  const [leaves, setLeaves] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [productionJobs, setProductionJobs] = useState([]);
  const [tab, setTab] = useState('Overview');

  const load = useCallback(() => {
    employeesAPI.get(employeeId).then((res) => setEmployee(res.data)).catch(() => setEmployee(null));
    attendanceAPI.list({ employee_id: employeeId }).then((res) => setAttendance(res.data));
    leavesAPI.list({ employee_id: employeeId }).then((res) => setLeaves(res.data));
    dailyTasksAPI.list({ employee_id: employeeId }).then((res) => setTasks(res.data));
    // production_jobs doesn't support an employee_id filter server-side yet;
    // filter client-side here rather than fetch nothing.
    productionJobsAPI.list().then((res) => setProductionJobs(res.data.filter((j) => String(j.employee_id) === String(employeeId))));
  }, [employeeId]);

  useEffect(load, [load]);

  if (!employee) return <div className="page">Loading...</div>;

  const totalHours = attendance.reduce((sum, a) => sum + (a.working_hours || 0), 0);
  const totalOvertime = attendance.reduce((sum, a) => sum + (a.overtime_hours || 0), 0);
  const completedTasks = tasks.filter((t) => t.status === 'Completed').length;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/employees" className="btn-link">&larr; Back to Employees</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{employee.name}</h1>
          <div className="detail-subtitle">{employee.employee_code} &middot; {employee.department || 'No department'}</div>
        </div>
      </div>

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Total Hours</div><h3>{totalHours.toFixed(1)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Overtime Hours</div><h3>{totalOvertime.toFixed(1)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Tasks Completed</div><h3>{completedTasks}/{tasks.length}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Status</div><h3 style={{ fontSize: '1.1rem' }}>{employee.status}</h3></div></Card>
      </div>

      <div className="tab-bar">
        {TABS.map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && (
        <Card title="Employee Details">
          <div className="card-body">
            <div className="detail-meta">
              <div className="detail-meta-item"><span className="detail-meta-label">Phone</span><span className="detail-meta-value">{employee.phone || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Joining Date</span><span className="detail-meta-value">{employee.joining_date ? new Date(employee.joining_date).toLocaleDateString() : '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Monthly Salary</span><span className="detail-meta-value">{money(employee.monthly_salary)}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Daily Wage</span><span className="detail-meta-value">{money(employee.daily_wage)}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Emergency Contact</span><span className="detail-meta-value">{employee.emergency_contact || '-'}</span></div>
            </div>
          </div>
        </Card>
      )}

      {tab === 'Attendance' && (
        <Table
          columns={[
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'working_hours', label: 'Working Hours' }, { key: 'overtime_hours', label: 'Overtime' },
            { key: 'attendance_status', label: 'Status' },
          ]}
          data={attendance}
          emptyMessage="No attendance records for this employee yet."
        />
      )}

      {tab === 'Leave' && (
        <Table
          columns={[
            { key: 'leave_type', label: 'Type' },
            { key: 'start_date', label: 'From', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'end_date', label: 'To', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'days', label: 'Days' }, { key: 'reason', label: 'Reason' },
            { key: 'status', label: 'Status' },
          ]}
          data={leaves}
          emptyMessage="No leave requests for this employee yet."
        />
      )}

      {tab === 'Tasks' && (
        <Table
          columns={[
            { key: 'task_code', label: 'Task' }, { key: 'task_description', label: 'Description' },
            { key: 'status', label: 'Status' }, { key: 'completion_percent', label: 'Completion %' },
          ]}
          data={tasks}
          emptyMessage="No tasks assigned to this employee yet."
        />
      )}

      {tab === 'Production' && (
        <Table
          columns={[
            { key: 'job_code', label: 'Job' }, { key: 'machine', label: 'Machine' },
            { key: 'operation', label: 'Operation' }, { key: 'status', label: 'Status' },
          ]}
          data={productionJobs}
          emptyMessage="No production jobs for this employee yet."
        />
      )}
    </div>
  );
}

export default EmployeeDetailPage;
