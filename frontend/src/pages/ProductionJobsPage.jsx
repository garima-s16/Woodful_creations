import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { productionJobsAPI, employeesAPI, ordersAPI, materialsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { today } from '../utils/dates';

function ProductionJobsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [orders, setOrders] = useState([]);
  const [materials, setMaterials] = useState([]);
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingJob, setEditingJob] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = () => {
    setPageLoading(true);
    productionJobsAPI.list().then((res) => setJobs(res.data)).finally(() => setPageLoading(false));
    employeesAPI.list().then((res) => setEmployees(res.data));
    ordersAPI.list().then((res) => setOrders(res.data));
    materialsAPI.list().then((res) => setMaterials(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await productionJobsAPI.create({
        ...formData,
        employee_id: formData.employee_id ? Number(formData.employee_id) : null,
        order_id: formData.order_id ? Number(formData.order_id) : null,
        material_id: formData.material_id ? Number(formData.material_id) : null,
        date: new Date(formData.date).toISOString(),
        planned_qty: Number(formData.planned_qty || 0),
        completed_qty: Number(formData.completed_qty || 0),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create production job');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await productionJobsAPI.update(editingJob.id, {
        completed_qty: Number(formData.completed_qty || 0),
        status: formData.status,
        remarks: formData.remarks,
      });
      setEditingJob(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update production job');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'job_code', label: 'Job ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'machine', label: 'Machine' },
    { key: 'operation', label: 'Operation' },
    { key: 'employee_id', label: 'Operator', render: (v) => employees.find((e) => e.id === v)?.name || '-' },
    { key: 'order_id', label: 'Project', render: (v) => orders.find((o) => o.id === v)?.order_code || '-' },
    { key: 'planned_qty', label: 'Planned' }, { key: 'completed_qty', label: 'Completed' },
    { key: 'status', label: 'Status' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingJob(row); }}>Update Progress</button>
      ),
    },
  ];

  const createFields = [
    { name: 'date', label: 'Date', type: 'date', required: true, section: 'Job & Machine' },
    { name: 'machine', label: 'Machine', section: 'Job & Machine' },
    { name: 'operation', label: 'Operation', section: 'Job & Machine' },
    { name: 'employee_id', label: 'Operator', type: 'select', section: 'Assignment', options: employees.map((e) => ({ value: e.id, label: e.name })) },
    { name: 'order_id', label: 'Project (Order)', type: 'select', section: 'Assignment', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'material_id', label: 'Material', type: 'select', section: 'Assignment', options: materials.map((m) => ({ value: m.id, label: m.name })) },
    { name: 'planned_qty', label: 'Planned Quantity', type: 'number', required: true, section: 'Quantity' },
    { name: 'completed_qty', label: 'Completed Quantity', type: 'number', section: 'Quantity' },
  ];

  const editFields = [
    { name: 'completed_qty', label: 'Completed Quantity', type: 'number', required: true },
    { name: 'status', label: 'Status', type: 'select', required: true, options: [
      { value: 'Not Started', label: 'Not Started' }, { value: 'In Progress', label: 'In Progress' },
      { value: 'Completed', label: 'Completed' },
    ] },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Production Jobs</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Create Production Job</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={jobs} loading={pageLoading} onRowClick={(row) => navigate(`/production-jobs/${row.id}`)} emptyMessage="No production jobs recorded yet." />

      <Modal isOpen={showAdd} title="Create Production Job" onClose={() => setShowAdd(false)}>
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Create Job"
          initialValues={{ date: today() }} />
      </Modal>

      <Modal isOpen={!!editingJob} title={`Update Progress - ${editingJob?.job_code || ''}`} onClose={() => setEditingJob(null)}>
        {editingJob && (
          <Form
            fields={editFields}
            onSubmit={handleUpdate}
            loading={loading}
            submitText="Update"
            initialValues={{ completed_qty: editingJob.completed_qty, status: editingJob.status, remarks: editingJob.remarks || '' }}
          />
        )}
      </Modal>
    </div>
  );
}

export default ProductionJobsPage;
