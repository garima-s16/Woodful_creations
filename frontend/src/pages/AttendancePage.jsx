import React, { useEffect, useState } from 'react';
import { attendanceAPI, employeesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function AttendancePage() {
  const [records, setRecords] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => {
    attendanceAPI.list().then((res) => setRecords(res.data));
    employeesAPI.list().then((res) => setEmployees(res.data));
  };
  useEffect(load, []);

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

  return (
    <div className="page">
      <div className="page-header">
        <h1>Attendance</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Mark Attendance</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={records} emptyMessage="No attendance recorded yet. Record today's attendance to get started." />
      <Modal isOpen={showAdd} title="Mark Attendance" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Mark Attendance" />
      </Modal>
    </div>
  );
}

export default AttendancePage;
