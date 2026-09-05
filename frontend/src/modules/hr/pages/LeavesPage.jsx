import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { leavesAPI, employeesAPI, reportsAPI } from '../../../utils/api';
import Table from '../../../components/common/Table';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import { statusClass } from '../../../utils/format';

function LeavesPage() {
  const { user } = useSelector((state) => state.auth);
  const [leaves, setLeaves] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = (status) => {
    setPageLoading(true);
    setLoadError(false);
    leavesAPI.list(status ? { status } : undefined).then((res) => setLeaves(res.data)).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
    employeesAPI.list().then((res) => setEmployees(res.data));
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
    try {
      await leavesAPI.update(leave.id, { status, approved_by: user?.full_name || user?.username });
      load(statusFilter);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update leave request');
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
            <button className="btn-link" onClick={() => handleDecision(row, 'Approved')}>Approve</button>
            <button className="btn-link" style={{ color: 'var(--danger)' }} onClick={() => handleDecision(row, 'Rejected')}>Reject</button>
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

export default LeavesPage;
