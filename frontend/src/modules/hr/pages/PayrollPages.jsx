// HR payroll pages: salary slips and salary advances. Combines
// the former SalarySlipsPage.jsx and SalaryAdvancesPage.jsx.
import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { employeesAPI, reportsAPI, salaryAdvancesAPI, salarySlipsAPI } from '../../../utils/api';
import { Alert, Form, Modal, Table } from '../../../components/common/UI';
import { formatCurrency, statusClass } from '../../../utils/utils';

// --- SalarySlipsPage.jsx ---
function SalarySlipsPage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [slips, setSlips] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = () => {
    setPageLoading(true);
    salarySlipsAPI.list().then((res) => setSlips(res.data)).catch(() => setError('Unable to load salary slips.')).finally(() => setPageLoading(false));
    employeesAPI.list().then((res) => setEmployees(res.data));
  };
  useEffect(load, []);

  const [updatingStatusId, setUpdatingStatusId] = useState(null);
  const handleStatusChange = async (slip, newStatus) => {
    setUpdatingStatusId(slip.id);
    setError('');
    try {
      await salarySlipsAPI.update(slip.id, { status: newStatus });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update this slip\'s status.');
    } finally {
      setUpdatingStatusId(null);
    }
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await salarySlipsAPI.create({
        ...formData,
        employee_id: Number(formData.employee_id),
        working_days: formData.working_days || '26', paid_days: formData.paid_days || '26',
        basic: formData.basic || '0', da: formData.da || '0', hra: formData.hra || '0',
        overtime_amount: formData.overtime_amount || '0',
        pf_deduction: formData.pf_deduction || '0', tds_deduction: formData.tds_deduction || '0',
        other_deductions: formData.other_deductions || '0',
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create salary slip');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'business_id', label: 'Slip ID', render: (v) => v || '-' },
    { key: 'employee_id', label: 'Employee', render: (v) => employees.find((e) => e.id === v)?.name || v },
    { key: 'month', label: 'Month' }, { key: 'year', label: 'Year' },
    { key: 'working_days', label: 'Working Days' }, { key: 'paid_days', label: 'Paid Days' },
    { key: 'net_salary', label: 'Net Salary', render: (v) => formatCurrency(v) },
    { key: 'status', label: 'Status', render: (v) => <span className={statusClass(v)}>{v}</span> },
    {
      key: 'id', label: 'Payslip', render: (v) => (
        <a href={reportsAPI.downloadUrl(`salary-slips/${v}.pdf`)} target="_blank" rel="noreferrer">Download PDF</a>
      ),
    },
    {
      // The natural draft -> finalized -> paid progression (matching
      // the backend's own SALARY_SLIP_STATUSES) - a "paid" slip is a
      // terminal state with no further action shown, and there is no
      // way to move a slip backwards from here (matching the
      // established master-only, forward-only pattern used for
      // Purchases' "Mark Received").
      key: 'status_action', label: '', render: (v, row) => {
        if (!isPrivileged || row.status === 'paid') return null;
        const nextStatus = row.status === 'draft' ? 'finalized' : 'paid';
        const label = row.status === 'draft' ? 'Finalize' : 'Mark Paid';
        return (
          <button
            type="button" className="btn-link"
            disabled={updatingStatusId === row.id}
            onClick={() => handleStatusChange(row, nextStatus)}
          >
            {updatingStatusId === row.id ? 'Updating...' : label}
          </button>
        );
      },
    },
  ];

  const fields = [
    { name: 'employee_id', label: 'Employee', type: 'select', required: true, section: 'Pay Period', options: employees.map((e) => ({ value: e.id, label: e.name })) },
    { name: 'month', label: 'Month', required: true, placeholder: 'August', section: 'Pay Period' },
    { name: 'year', label: 'Year', required: true, placeholder: '2026', section: 'Pay Period' },
    { name: 'working_days', label: 'Working Days', type: 'number', required: true, placeholder: '26', section: 'Pay Period' },
    { name: 'paid_days', label: 'Paid Days', type: 'number', required: true, placeholder: '26', hint: 'Cannot exceed Working Days', section: 'Pay Period' },
    { name: 'basic', label: 'Basic', type: 'number', required: true, section: 'Earnings' },
    { name: 'da', label: 'DA (Dearness Allowance)', type: 'number', section: 'Earnings' },
    { name: 'hra', label: 'HRA (House Rent Allowance)', type: 'number', section: 'Earnings' },
    { name: 'overtime_amount', label: 'Overtime Amount', type: 'number', section: 'Earnings' },
    { name: 'pf_deduction', label: 'PF Deduction', type: 'number', section: 'Deductions' },
    { name: 'tds_deduction', label: 'TDS Deduction', type: 'number', section: 'Deductions' },
    { name: 'other_deductions', label: 'Other Deductions', type: 'number', section: 'Deductions' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Salary Slips</h1>
          <p className="page-summary">Generate and review monthly salary slips for employees.</p>
        </div>
        {isPrivileged && (
          <div className="page-actions">
            <a className="btn-secondary" href={reportsAPI.downloadUrl('payroll.xlsx')} target="_blank" rel="noreferrer">
              Export Payroll
            </a>
            <button className="btn-primary" onClick={() => setShowAdd(true)}>Generate Salary Slip</button>
          </div>
        )}
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <p style={{ marginBottom: 16, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
        PF/TDS figures are entered manually and are not auto-calculated against statutory slabs -
        confirm with your accountant before finalizing payroll.
      </p>
      <Table columns={columns} data={slips} loading={pageLoading} emptyMessage="No salary slips generated yet." />
      <Modal isOpen={showAdd} title="Generate Salary Slip" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Generate"
          initialValues={{ working_days: '26', paid_days: '26' }} />
      </Modal>
    </div>
  );
}

// --- SalaryAdvancesPage.jsx ---
function SalaryAdvancesPage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [advances, setAdvances] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [actioning, setActioning] = useState(null); // { advance, type: 'approve'|'reject'|'recover' }
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = (refreshEmployees = true) => {
    setPageLoading(true);
    salaryAdvancesAPI.list().then((res) => setAdvances(res.data)).catch(() => setError('Unable to load salary advances.')).finally(() => setPageLoading(false));
    if (isPrivileged && refreshEmployees) employeesAPI.list().then((res) => setEmployees(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await salaryAdvancesAPI.create({
        employee_id: isPrivileged ? Number(formData.employee_id) : user.employee_id,
        requested_amount: formData.requested_amount, request_date: new Date().toISOString(),
        reason: formData.reason,
      });
      setShowAdd(false);
      load(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit the salary advance request.');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await salaryAdvancesAPI.approve(actioning.advance.id, {
        approved_amount: formData.approved_amount || undefined,
        recovery_month: formData.recovery_month, recovery_year: formData.recovery_year,
      });
      setActioning(null);
      load(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to approve this request.');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await salaryAdvancesAPI.reject(actioning.advance.id, { rejection_reason: formData.rejection_reason });
      setActioning(null);
      load(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reject this request.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecover = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await salaryAdvancesAPI.recover(actioning.advance.id, {
        amount: formData.amount, month: formData.month, year: formData.year,
      });
      setActioning(null);
      load(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record recovery - check a salary slip exists for that employee/month.');
    } finally {
      setLoading(false);
    }
  };

  const requestFields = isPrivileged
    ? [
      { name: 'employee_id', label: 'Employee', type: 'select', required: true, options: employees.map((e) => ({ value: e.id, label: e.name })) },
      { name: 'requested_amount', label: 'Amount', type: 'number', required: true },
      { name: 'reason', label: 'Reason', type: 'textarea' },
    ]
    : [
      { name: 'requested_amount', label: 'Amount', type: 'number', required: true },
      { name: 'reason', label: 'Reason', type: 'textarea' },
    ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Salary Advances</h1>
        <button className="btn btn-primary" onClick={() => setShowAdd(true)}>
          {isPrivileged ? 'Create Advance' : 'Request Advance'}
        </button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <Table
        loading={pageLoading}
        columns={[
          ...(isPrivileged ? [{ key: 'employee_name', label: 'Employee' }] : []),
          { key: 'requested_amount', label: 'Requested', render: (v) => formatCurrency(v) },
          { key: 'approved_amount', label: 'Approved', render: (v) => (v != null ? formatCurrency(v) : '-') },
          { key: 'outstanding_amount', label: 'Outstanding', render: (v) => formatCurrency(v) },
          { key: 'status', label: 'Status', render: (v) => <span className={statusClass(v)}>{v}</span> },
          {
            key: 'actions', label: '',
            render: (v, row) => isPrivileged && (
              <>
                {row.status === 'Pending' && (
                  <>
                    <button type="button" className="btn-link" onClick={() => setActioning({ advance: row, type: 'approve' })}>Approve</button>
                    <button type="button" className="btn-link" onClick={() => setActioning({ advance: row, type: 'reject' })}>Reject</button>
                  </>
                )}
                {row.status === 'Approved' && Number(row.outstanding_amount) > 0 && (
                  <button type="button" className="btn-link" onClick={() => setActioning({ advance: row, type: 'recover' })}>Record Recovery</button>
                )}
              </>
            ),
          },
        ]}
        data={advances}
        emptyMessage={isPrivileged ? 'No salary advance requests yet.' : "You haven't requested a salary advance."}
      />

      <Modal isOpen={showAdd} title={isPrivileged ? 'Create Advance' : 'Request Advance'} onClose={() => setShowAdd(false)}>
        <Form fields={requestFields} onSubmit={handleCreate} loading={loading} submitText="Submit" />
      </Modal>

      <Modal isOpen={actioning?.type === 'approve'} title="Approve Advance" onClose={() => setActioning(null)}>
        <Form
          fields={[
            { name: 'approved_amount', label: 'Approved Amount', type: 'number', placeholder: actioning ? `Default: ${actioning.advance.requested_amount}` : '' },
            { name: 'recovery_month', label: 'Recovery Month', required: true, placeholder: 'e.g. September' },
            { name: 'recovery_year', label: 'Recovery Year', required: true, placeholder: 'e.g. 2026' },
          ]}
          onSubmit={handleApprove} loading={loading} submitText="Approve"
        />
      </Modal>

      <Modal isOpen={actioning?.type === 'reject'} title="Reject Advance" onClose={() => setActioning(null)}>
        <Form
          fields={[{ name: 'rejection_reason', label: 'Reason', type: 'textarea' }]}
          onSubmit={handleReject} loading={loading} submitText="Reject"
        />
      </Modal>

      <Modal isOpen={actioning?.type === 'recover'} title="Record Recovery" onClose={() => setActioning(null)}>
        <Form
          fields={[
            { name: 'amount', label: 'Amount', type: 'number', required: true, hint: actioning ? `Outstanding: ${actioning.advance.outstanding_amount}` : '' },
            { name: 'month', label: 'Salary Slip Month', required: true, placeholder: 'e.g. September' },
            { name: 'year', label: 'Salary Slip Year', required: true, placeholder: 'e.g. 2026' },
          ]}
          onSubmit={handleRecover} loading={loading} submitText="Record Recovery"
        />
      </Modal>
    </div>
  );
}

export { SalarySlipsPage, SalaryAdvancesPage };
