import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { salarySlipsAPI, employeesAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { formatCurrency } from '../utils/currency';

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
    employeesAPI.list().then((res) => setEmployees(res.data)).catch(() => {});
  };
  useEffect(load, []);

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
    { key: 'status', label: 'Status' },
    {
      key: 'id', label: 'Payslip', render: (v) => (
        <a href={reportsAPI.downloadUrl(`salary-slips/${v}.pdf`)} target="_blank" rel="noreferrer">Download PDF</a>
      ),
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

export default SalarySlipsPage;
