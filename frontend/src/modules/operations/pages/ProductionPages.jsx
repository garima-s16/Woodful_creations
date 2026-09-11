// Production pages: jobs list and job detail. Combines the
// former ProductionJobsPage.jsx and ProductionJobDetailPage.jsx.
import React, { useCallback, useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { cuttingRequirementsAPI, employeesAPI, materialsAPI, ordersAPI, productionJobsAPI, productionOperationsAPI, reportsAPI, settingsAPI } from '../../../utils/api';
import { Alert, Card, Form, Modal, Table } from '../../../components/common/UI';
import { classifyLoadError, statusClass, today } from '../../../utils/utils';

// --- ProductionJobsPage.jsx ---
function ProductionJobsPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isMaster = user?.role === 'master';
  const [jobs, setJobs] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [orders, setOrders] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [stages, setStages] = useState([]);
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingJob, setEditingJob] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    productionJobsAPI.list().then((res) => setJobs(res.data)).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
    employeesAPI.list().then((res) => setEmployees(res.data));
    ordersAPI.list().then((res) => setOrders(res.data));
    materialsAPI.list().then((res) => setMaterials(res.data));
    settingsAPI.list('production-stages').then((res) => setStages(res.data)).catch(() => setStages([]));
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
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'machine', label: 'Machine' },
    { name: 'planned_qty', label: 'Planned Quantity', type: 'number', required: true },
    { name: 'operation', label: 'Operation', advanced: true },
    { name: 'stage', label: 'Stage', type: 'select', advanced: true,
      options: stages.map((s) => ({ value: s.name, label: s.name })) },
    { name: 'employee_id', label: 'Operator', type: 'select', advanced: true, options: employees.map((e) => ({ value: e.id, label: e.name })) },
    { name: 'order_id', label: 'Project (Order)', type: 'select', advanced: true, options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'material_id', label: 'Material', type: 'select', advanced: true, options: materials.map((m) => ({ value: m.id, label: m.name })) },
    { name: 'completed_qty', label: 'Completed Quantity', type: 'number', advanced: true },
  ];

  const editFields = [
    { name: 'completed_qty', label: 'Completed Quantity', type: 'number', required: true },
    { name: 'stage', label: 'Stage', type: 'select', options: stages.map((s) => ({ value: s.name, label: s.name })) },
    { name: 'status', label: 'Status', type: 'select', required: true, options: [
      { value: 'Not Started', label: 'Not Started' }, { value: 'In Progress', label: 'In Progress' },
      { value: 'Completed', label: 'Completed' },
    ] },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Production Jobs</h1>
          <p className="page-summary">Track work through cutting, assembly, and finishing on the shop floor.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('production.xlsx')} target="_blank" rel="noreferrer">
            Export Production
          </a>
          {isMaster && <button className="btn-primary" onClick={() => setShowAdd(true)}>Create Production Job</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={jobs} loading={pageLoading} error={loadError} onRetry={load} onRowClick={(row) => navigate(`/production-jobs/${row.id}`)} emptyMessage="No production jobs recorded yet." />

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

// --- ProductionJobDetailPage.jsx ---
function ProductionJobDetailPage() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [employee, setEmployee] = useState(null);
  const [order, setOrder] = useState(null);
  const [material, setMaterial] = useState(null);
  const [materials, setMaterials] = useState([]);
  const [readiness, setReadiness] = useState(null);
  const [variance, setVariance] = useState(null);
  const [risks, setRisks] = useState(null);
  const [operations, setOperations] = useState([]);
  const [operationError, setOperationError] = useState('');
  const [showAddOperation, setShowAddOperation] = useState(false);
  const [addOperationLoading, setAddOperationLoading] = useState(false);
  const [cuttingRequirements, setCuttingRequirements] = useState([]);
  const [cuttingError, setCuttingError] = useState('');
  const [showAddCutting, setShowAddCutting] = useState(false);
  const [addCuttingLoading, setAddCuttingLoading] = useState(false);
  const [nestingResult, setNestingResult] = useState(null);
  const [nestingLoading, setNestingLoading] = useState(false);
  const [nestingError, setNestingError] = useState('');
  const [sheetLength, setSheetLength] = useState(2440);
  const [sheetWidth, setSheetWidth] = useState(1220);
  const [kerf, setKerf] = useState(3);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoadError(null);
    productionJobsAPI.get(jobId).then((res) => {
      setJob(res.data);
      if (res.data.employee_id) employeesAPI.get(res.data.employee_id).then((r) => setEmployee(r.data)).catch(() => setEmployee('error'));
      if (res.data.order_id) ordersAPI.get(res.data.order_id).then((r) => setOrder(r.data)).catch(() => setOrder('error'));
      if (res.data.material_id) materialsAPI.get(res.data.material_id).then((r) => setMaterial(r.data)).catch(() => setMaterial('error'));
    }).catch((err) => setLoadError(classifyLoadError(err, 'production job')));
    productionJobsAPI.readiness(jobId).then((res) => setReadiness(res.data)).catch(() => setReadiness(null));
    productionJobsAPI.variance(jobId).then((res) => setVariance(res.data)).catch(() => setVariance(null));
    productionJobsAPI.risks(jobId).then((res) => setRisks(res.data.risks)).catch(() => setRisks(null));
    productionOperationsAPI.list({ production_job_id: jobId }).then((res) => setOperations(res.data)).catch(() => setOperations([]));
    cuttingRequirementsAPI.list({ production_job_id: jobId }).then((res) => setCuttingRequirements(res.data)).catch(() => setCuttingRequirements([]));
    materialsAPI.list().then((res) => setMaterials(res.data)).catch(() => setMaterials([]));
  }, [jobId]);

  useEffect(load, [load]);

  const handleOperationStatusChange = async (operationId, status) => {
    setOperationError('');
    try {
      await productionOperationsAPI.update(operationId, { status });
      load();
    } catch (err) {
      setOperationError(err.response?.data?.detail || 'Failed to update this operation');
    }
  };

  const handleAddOperation = async (formData) => {
    setAddOperationLoading(true);
    setOperationError('');
    try {
      await productionOperationsAPI.create({
        production_job_id: Number(jobId), sequence: Number(formData.sequence || operations.length + 1),
        operation_name: formData.operation_name, resource: formData.resource || undefined,
        estimated_duration_minutes: formData.estimated_duration_minutes ? Number(formData.estimated_duration_minutes) : undefined,
        depends_on_operation_id: formData.depends_on_operation_id ? Number(formData.depends_on_operation_id) : undefined,
      });
      setShowAddOperation(false);
      load();
    } catch (err) {
      setOperationError(err.response?.data?.detail || 'Failed to add this operation');
    } finally {
      setAddOperationLoading(false);
    }
  };

  const handleAddCutting = async (formData) => {
    setAddCuttingLoading(true);
    setCuttingError('');
    try {
      await cuttingRequirementsAPI.create({
        production_job_id: Number(jobId), material_id: Number(formData.material_id),
        part_name: formData.part_name, quantity: Number(formData.quantity || 1),
        length_mm: formData.length_mm, width_mm: formData.width_mm,
        thickness_mm: formData.thickness_mm || undefined,
        grain_direction: formData.grain_direction || undefined,
        rotation_allowed: formData.rotation_allowed !== 'false',
        kerf_mm: formData.kerf_mm || undefined,
      });
      setShowAddCutting(false);
      load();
    } catch (err) {
      setCuttingError(err.response?.data?.detail || 'Failed to add this cutting requirement');
    } finally {
      setAddCuttingLoading(false);
    }
  };

  const handleDeleteCutting = async (requirementId) => {
    setCuttingError('');
    try {
      await cuttingRequirementsAPI.remove(requirementId);
      load();
    } catch (err) {
      setCuttingError(err.response?.data?.detail || 'Failed to delete this cutting requirement');
    }
  };

  const handleCalculateNesting = async () => {
    setNestingLoading(true);
    setNestingError('');
    try {
      const res = await productionJobsAPI.nesting(jobId, {
        sheet_length_mm: sheetLength, sheet_width_mm: sheetWidth, kerf_mm: kerf,
      });
      setNestingResult(res.data);
    } catch (err) {
      setNestingError(err.response?.data?.detail || 'Failed to calculate nesting');
    } finally {
      setNestingLoading(false);
    }
  };

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

  if (loadError) return (
    <div className="page">
      <Alert type="error" message={loadError.message} />
      {!loadError.isNotFound && (
        <button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button>
      )}
    </div>
  );
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
            {job.operation || 'Production Job'} &middot; {order === 'error' ? 'Order unavailable' : (order?.order_code || 'No order linked')}
            {job.business_id && <span className="business-id-badge">{job.business_id}</span>}
          </div>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {readiness && (
        <div className={`readiness-banner readiness-${readiness.readiness.toLowerCase()}`}>
          <span className={`status-badge ${
            readiness.readiness === 'READY' ? 'status-ok'
              : readiness.readiness === 'PARTIALLY_READY' ? 'status-warning' : 'status-danger'
          }`}>
            {readiness.readiness === 'READY' ? 'Ready for Production'
              : readiness.readiness === 'PARTIALLY_READY' ? 'Partially Ready' : 'Blocked'}
          </span>
          <span className="readiness-reason">{readiness.reason}</span>
        </div>
      )}

      {risks && risks.filter((r) => r.type !== 'material_shortage').length > 0 && (
        <Card title="Production Risks">
          {risks.filter((r) => r.type !== 'material_shortage').map((risk, i) => (
            <div key={i} className="detail-meta-item" style={{ marginBottom: 'var(--space-3)' }}>
              <span className={`status-badge ${risk.severity === 'high' ? 'status-danger' : 'status-warning'}`}>
                {risk.type.replace(/_/g, ' ')}
              </span>
              <div><strong>{risk.what}</strong></div>
              <div>{risk.why}</div>
              <div className="detail-meta-label">Impact: {risk.impact}</div>
            </div>
          ))}
        </Card>
      )}

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
          <span className="detail-meta-value">{employee === 'error' ? 'Unavailable' : (employee?.name || '-')}</span>
        </div>
        <div className="detail-meta-item">
          <span className="detail-meta-label">Machine</span>
          <span className="detail-meta-value">{job.machine || '-'}</span>
        </div>
        <div className="detail-meta-item">
          <span className="detail-meta-label">Material</span>
          <span className="detail-meta-value">{material === 'error' ? 'Unavailable' : (material?.name || '-')}</span>
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

      <Card title="Operations">
        {operationError && <Alert type="error" message={operationError} onClose={() => setOperationError('')} />}
        <div className="page-actions" style={{ marginBottom: 'var(--space-4)' }}>
          <button type="button" className="btn-secondary" onClick={() => setShowAddOperation((v) => !v)}>
            {showAddOperation ? 'Cancel' : 'Add Operation'}
          </button>
        </div>
        {showAddOperation && (
          <Form
            fields={[
              { name: 'operation_name', label: 'Operation Name', required: true },
              { name: 'sequence', label: 'Sequence', type: 'number' },
              { name: 'resource', label: 'Resource / Machine' },
              { name: 'estimated_duration_minutes', label: 'Estimated Duration (minutes)', type: 'number' },
              { name: 'depends_on_operation_id', label: 'Depends On', type: 'select', options: [
                { value: '', label: 'None' },
                ...operations.map((op) => ({ value: String(op.id), label: `${op.sequence}. ${op.operation_name}` })),
              ] },
            ]}
            onSubmit={handleAddOperation} loading={addOperationLoading} submitText="Add Operation"
          />
        )}
        <Table
          columns={[
            { key: 'sequence', label: '#' },
            { key: 'operation_name', label: 'Operation' },
            { key: 'resource', label: 'Resource', render: (v) => v || '-' },
            { key: 'status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
            {
              key: 'is_blocked_by_dependency', label: 'Dependency',
              render: (v) => v
                ? <span className="status-badge status-danger">Waiting on predecessor</span>
                : <span className="status-badge status-ok">Clear</span>,
            },
            {
              key: 'actions', label: '',
              render: (v, row) => row.status !== 'Completed' && (
                <>
                  {row.status === 'Not Started' && (
                    <button type="button" className="btn-link" onClick={() => handleOperationStatusChange(row.id, 'In Progress')} disabled={row.is_blocked_by_dependency}>
                      Start
                    </button>
                  )}
                  {row.status === 'In Progress' && (
                    <button type="button" className="btn-link" onClick={() => handleOperationStatusChange(row.id, 'Completed')}>
                      Complete
                    </button>
                  )}
                </>
              ),
            },
          ]}
          data={operations}
          emptyMessage="No operations recorded for this job yet."
        />
      </Card>

      <Card title="Cutting Requirements">
        {cuttingError && <Alert type="error" message={cuttingError} onClose={() => setCuttingError('')} />}
        <div className="page-actions" style={{ marginBottom: 'var(--space-4)' }}>
          <button type="button" className="btn-secondary" onClick={() => setShowAddCutting((v) => !v)}>
            {showAddCutting ? 'Cancel' : 'Add Part'}
          </button>
        </div>
        {showAddCutting && (
          <Form
            fields={[
              { name: 'part_name', label: 'Part Name', required: true },
              { name: 'material_id', label: 'Material', type: 'select', required: true, options: materials.map((m) => ({ value: m.id, label: m.name })) },
              { name: 'quantity', label: 'Quantity', type: 'number', placeholder: '1' },
              { name: 'length_mm', label: 'Length (mm)', type: 'number', required: true },
              { name: 'width_mm', label: 'Width (mm)', type: 'number', required: true },
              { name: 'thickness_mm', label: 'Thickness (mm)', type: 'number' },
              { name: 'grain_direction', label: 'Grain Direction', type: 'select', options: [
                { value: '', label: 'None' }, { value: 'Length', label: 'Length' }, { value: 'Width', label: 'Width' },
              ] },
              { name: 'rotation_allowed', label: 'Rotation Allowed', type: 'select', options: [
                { value: 'true', label: 'Yes' }, { value: 'false', label: 'No - grain must stay aligned' },
              ] },
              { name: 'kerf_mm', label: 'Kerf (mm)', type: 'number' },
            ]}
            onSubmit={handleAddCutting} loading={addCuttingLoading} submitText="Add Part"
          />
        )}
        <Table
          columns={[
            { key: 'part_name', label: 'Part' },
            { key: 'material_name', label: 'Material' },
            { key: 'quantity', label: 'Qty' },
            { key: 'length_mm', label: 'Length (mm)' },
            { key: 'width_mm', label: 'Width (mm)' },
            { key: 'grain_direction', label: 'Grain', render: (v) => v || '-' },
            { key: 'rotation_allowed', label: 'Rotation', render: (v) => v ? 'Allowed' : 'Fixed' },
            {
              key: 'actions', label: '',
              render: (v, row) => <button type="button" className="btn-link" onClick={() => handleDeleteCutting(row.id)}>Delete</button>,
            },
          ]}
          data={cuttingRequirements}
          emptyMessage="No cutting requirements recorded for this job yet."
        />
      </Card>

      {cuttingRequirements.length > 0 && (
        <Card title="Nesting">
          {nestingError && <Alert type="error" message={nestingError} onClose={() => setNestingError('')} />}
          <p className="page-summary" style={{ marginBottom: 'var(--space-4)' }}>
            Estimated sheet layout for this job's parts - a real, deterministic calculation
            (not an "optimized" guess), grouped separately per material since different materials
            can't share a physical sheet.
          </p>
          <div className="bulk-purchase-shared-fields" style={{ marginBottom: 'var(--space-4)' }}>
            <label>
              Sheet Length (mm)
              <input type="number" value={sheetLength} onChange={(e) => setSheetLength(e.target.value)} />
            </label>
            <label>
              Sheet Width (mm)
              <input type="number" value={sheetWidth} onChange={(e) => setSheetWidth(e.target.value)} />
            </label>
            <label>
              Kerf (mm)
              <input type="number" value={kerf} onChange={(e) => setKerf(e.target.value)} />
            </label>
          </div>
          <button type="button" className="btn-primary" onClick={handleCalculateNesting} disabled={nestingLoading}>
            {nestingLoading ? 'Calculating...' : 'Calculate Nesting'}
          </button>

          {nestingResult && (
            <div style={{ marginTop: 'var(--space-5)' }}>
              {nestingResult.material_results.map((r) => (
                <div key={r.material_id} className="detail-meta" style={{ marginBottom: 'var(--space-4)', paddingBottom: 'var(--space-4)', borderBottom: '1px solid var(--border-color)' }}>
                  <div className="detail-meta-item" style={{ gridColumn: '1 / -1' }}>
                    <span className="detail-meta-label">Material</span>
                    <span className="detail-meta-value">{r.material_name}</span>
                  </div>
                  {r.error ? (
                    <div className="detail-meta-item" style={{ gridColumn: '1 / -1' }}>
                      <span className="detail-meta-label">Result</span>
                      <span className="detail-meta-value" style={{ color: 'var(--danger)' }}>
                        {r.unfit_parts.length} part{r.unfit_parts.length !== 1 ? 's' : ''} too large for a
                        {' '}{r.sheet_length_mm}x{r.sheet_width_mm}mm sheet, even with rotation.
                      </span>
                    </div>
                  ) : (
                    <>
                      <div className="detail-meta-item">
                        <span className="detail-meta-label">Sheets Required</span>
                        <span className="detail-meta-value">{r.sheets_required}</span>
                      </div>
                      <div className="detail-meta-item">
                        <span className="detail-meta-label">Parts Placed</span>
                        <span className="detail-meta-value">{r.parts_placed}</span>
                      </div>
                      <div className="detail-meta-item">
                        <span className="detail-meta-label">Estimated Utilization</span>
                        <span className="detail-meta-value">{r.estimated_utilization_percent}%</span>
                      </div>
                      <div className="detail-meta-item">
                        <span className="detail-meta-label">Estimated Waste</span>
                        <span className="detail-meta-value">{r.estimated_waste_percent}%</span>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {variance && (
        <Card title="Planned vs Actual">
          <div className="detail-meta">
            <div className="detail-meta-item">
              <span className="detail-meta-label">Quantity</span>
              <span className="detail-meta-value">
                {variance.quantity_completed} / {variance.quantity_planned}
                {variance.quantity_variance_percent != null && ` (${variance.quantity_variance_percent > 0 ? '+' : ''}${variance.quantity_variance_percent}%)`}
              </span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Estimated Duration</span>
              <span className="detail-meta-value">{variance.duration_planned_minutes} min</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Actual Duration</span>
              <span className="detail-meta-value">
                {variance.duration_actual_minutes != null ? `${variance.duration_actual_minutes} min` : 'Not yet recorded'}
              </span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Duration Variance</span>
              <span className="detail-meta-value">
                {variance.duration_variance_minutes != null
                  ? `${variance.duration_variance_minutes > 0 ? '+' : ''}${variance.duration_variance_minutes} min`
                  : '-'}
                {!variance.duration_complete && variance.operations_with_actual_duration > 0 && ' (partial - not every operation has an actual yet)'}
              </span>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

export { ProductionJobsPage, ProductionJobDetailPage };
