import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { salaryAdvancesAPI, employeesAPI } from '../../../utils/api';
import Table from '../../../components/common/Table';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import { formatCurrency, statusClass } from '../../../utils/format';

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

  const load = () => {
    setPageLoading(true);
    salaryAdvancesAPI.list().then((res) => setAdvances(res.data)).catch(() => setError('Unable to load salary advances.')).finally(() => setPageLoading(false));
    if (isPrivileged) employeesAPI.list().then((res) => setEmployees(res.data));
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
      load();
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
      load();
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
      load();
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
      load();
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

export default SalaryAdvancesPage;
