import React, { useEffect, useState, useMemo } from 'react';
import { attendanceAPI, employeesAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Card from '../components/common/Card';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { today } from '../utils/dates';

function monthKey(dateStr) {
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function monthLabel(key) {
  const [year, month] = key.split('-');
  return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

function monthNameOnly(key) {
  const [year, month] = key.split('-');
  return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString('en-US', { month: 'long' });
}

function AttendancePage() {
  const [records, setRecords] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [monthFilter, setMonthFilter] = useState('');
  const [employeeFilter, setEmployeeFilter] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = () => {
    setPageLoading(true);
    attendanceAPI.list().then((res) => setRecords(res.data)).finally(() => setPageLoading(false));
    employeesAPI.list().then((res) => setEmployees(res.data));
  };
  useEffect(() => {
    load();
  }, []);

  // Backend only supports filtering by a single exact date, not a month
  // range, so the monthly view groups/filters the already-fetched records
  // on the client - still real data, just reorganized for this view.
  const availableMonths = useMemo(() => {
    const keys = new Set(records.map((r) => monthKey(r.date)));
    return Array.from(keys).sort().reverse();
  }, [records]);

  const filteredRecords = records.filter((r) => {
    if (monthFilter && monthKey(r.date) !== monthFilter) return false;
    if (employeeFilter && String(r.employee_id) !== employeeFilter) return false;
    return true;
  });

  const monthlySummary = useMemo(() => {
    if (!monthFilter) return [];
    const byEmployee = {};
    records.filter((r) => monthKey(r.date) === monthFilter).forEach((r) => {
      const emp = employees.find((e) => e.id === r.employee_id);
      const name = emp?.name || `Employee ${r.employee_id}`;
      if (!byEmployee[name]) byEmployee[name] = { name, days: 0, hours: 0, overtime: 0 };
      byEmployee[name].days += 1;
      byEmployee[name].hours += r.working_hours || 0;
      byEmployee[name].overtime += r.overtime_hours || 0;
    });
    return Object.values(byEmployee);
  }, [records, employees, monthFilter]);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await attendanceAPI.create({
        ...formData,
        employee_id: Number(formData.employee_id),
        date: new Date(formData.date).toISOString(),
        in_time: formData.in_time ? new Date(`${formData.date}T${formData.in_time}`).toISOString() : null,
        out_time: formData.out_time ? new Date(`${formData.date}T${formData.out_time}`).toISOString() : null,
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to mark attendance');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'employee_id', label: 'Employee', render: (v) => employees.find((e) => e.id === v)?.name || v },
    { key: 'working_hours', label: 'Working Hours' }, { key: 'overtime_hours', label: 'Overtime' },
    { key: 'attendance_status', label: 'Status' },
  ];

  const fields = [
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'employee_id', label: 'Employee', type: 'select', required: true, options: employees.map((e) => ({ value: e.id, label: e.name })) },
    { name: 'in_time', label: 'In Time', type: 'time' },
    { name: 'out_time', label: 'Out Time', type: 'time' },
    { name: 'attendance_status', label: 'Status', type: 'select', options: [
      { value: 'Present', label: 'Present' }, { value: 'Absent', label: 'Absent' },
      { value: 'Half Day', label: 'Half Day' }, { value: 'Leave', label: 'Leave' },
    ] },
    { name: 'remarks', label: 'Remarks' },
  ];

  const attendanceExportUrl = (overtimeOnly = false) => {
    const params = new URLSearchParams();
    if (employeeFilter) params.set('employee_id', employeeFilter);
    if (monthFilter) {
      const [year] = monthFilter.split('-');
      params.set('month', monthNameOnly(monthFilter));
      params.set('year', year);
    }
    if (overtimeOnly) params.set('overtime_only', 'true');
    const qs = params.toString();
    return reportsAPI.downloadUrl(`attendance.xlsx${qs ? `?${qs}` : ''}`);
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Attendance</h1>
          <p className="page-summary">Log daily attendance and track Half Day/Absent records for payroll.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={attendanceExportUrl()} target="_blank" rel="noreferrer">
            {employeeFilter || monthFilter ? 'Export Filtered' : 'Export All'}
          </a>
          <a className="btn-secondary" href={attendanceExportUrl(true)} target="_blank" rel="noreferrer">
            Export Overtime
          </a>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>Mark Attendance</button>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <form className="page-search" onSubmit={(e) => e.preventDefault()}>
        <select className="form-input" value={monthFilter} onChange={(e) => setMonthFilter(e.target.value)}>
          <option value="">All Months</option>
          {availableMonths.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
        </select>
        <select className="form-input" value={employeeFilter} onChange={(e) => setEmployeeFilter(e.target.value)}>
          <option value="">All Employees</option>
          {employees.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </form>

      {monthFilter && monthlySummary.length > 0 && (
        <Card title={`${monthLabel(monthFilter)} Summary`}>
          <Table
            columns={[
              { key: 'name', label: 'Employee' }, { key: 'days', label: 'Days Recorded' },
              { key: 'hours', label: 'Total Working Hours', render: (v) => v.toFixed(1) },
              { key: 'overtime', label: 'Total Overtime', render: (v) => v.toFixed(1) },
            ]}
            data={monthlySummary}
          />
        </Card>
      )}

      <Table columns={columns} data={filteredRecords} loading={pageLoading} emptyMessage="No attendance recorded yet. Record today's attendance to get started." />
      <Modal isOpen={showAdd} title="Mark Attendance" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Mark Attendance"
          initialValues={{ date: today() }} />
      </Modal>
    </div>
  );
}

export default AttendancePage;
