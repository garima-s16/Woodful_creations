import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { productionJobsAPI, employeesAPI, ordersAPI, materialsAPI } from '../utils/api';
import Card from '../components/common/Card';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { statusClass } from '../utils/statusColors';

function ProductionJobDetailPage() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [employee, setEmployee] = useState(null);
  const [order, setOrder] = useState(null);
  const [material, setMaterial] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    productionJobsAPI.get(jobId).then((res) => {
      setJob(res.data);
      if (res.data.employee_id) employeesAPI.get(res.data.employee_id).then((r) => setEmployee(r.data)).catch(() => {});
      if (res.data.order_id) ordersAPI.get(res.data.order_id).then((r) => setOrder(r.data)).catch(() => {});
      if (res.data.material_id) materialsAPI.get(res.data.material_id).then((r) => setMaterial(r.data)).catch(() => {});
    }).catch(() => setError('Unable to load this production job.'));
  }, [jobId]);

  useEffect(load, [load]);

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await productionJobsAPI.update(job.id, {
        status: formData.status, completed_qty: Number(formData.completed_qty || 0), remarks: formData.remarks,
      });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update production job');
    } finally {
      setLoading(false);
    }
  };

  if (error) return <div className="page"><Alert type="error" message={error} /></div>;
  if (!job) return <div className="page">Loading...</div>;

  const updateFields = [
    { name: 'status', label: 'Status', type: 'select', options: [
      { value: 'Not Started', label: 'Not Started' }, { value: 'In Progress', label: 'In Progress' },
      { value: 'Completed', label: 'Completed' },
    ] },
    { name: 'completed_qty', label: 'Completed Quantity', type: 'number' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{job.job_code}</h1>
          <div className="detail-subtitle">
            {job.operation || 'Production Job'} &middot; {order?.order_code || 'No order linked'}
            {job.business_id && <span className="business-id-badge">{job.business_id}</span>}
          </div>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="detail-meta">
        <div className="detail-meta-item">
          <span className="detail-meta-label">Status</span>
          <span className={`status-badge ${statusClass(job.status)}`}>{job.status}</span>
        </div>
        <div className="detail-meta-item">
          <span className="detail-meta-label">Date</span>
          <span className="detail-meta-value">{new Date(job.date).toLocaleDateString()}</span>
        </div>
        <div className="detail-meta-item">
          <span className="detail-meta-label">Operator</span>
          <span className="detail-meta-value">{employee?.name || '-'}</span>
        </div>
        <div className="detail-meta-item">
          <span className="detail-meta-label">Machine</span>
          <span className="detail-meta-value">{job.machine || '-'}</span>
        </div>
        <div className="detail-meta-item">
          <span className="detail-meta-label">Material</span>
          <span className="detail-meta-value">{material?.name || '-'}</span>
        </div>
        <div className="detail-meta-item">
          <span className="detail-meta-label">Progress</span>
          <span className="detail-meta-value">{job.completed_qty} / {job.planned_qty}</span>
        </div>
      </div>

      <Card title="Update Job">
        <Form
          fields={updateFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
          initialValues={{ status: job.status, completed_qty: job.completed_qty, remarks: job.remarks || '' }}
        />
      </Card>
    </div>
  );
}

export default ProductionJobDetailPage;
