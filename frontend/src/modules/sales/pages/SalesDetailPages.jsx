// Sales detail pages: estimate detail and order detail. Combines
// the former EstimateDetailPage.jsx and OrderDetailPage.jsx.
import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { clientsAPI, communicationAPI, dailyTasksAPI, documentsAPI, employeesAPI, estimatesAPI, issuesAPI, materialsAPI, ordersAPI, paymentsAPI, productionJobsAPI, projectExpensesAPI, reportsAPI } from '../../../utils/api';
import { Alert, Card, ConfirmDialog, Form, Modal, OrderLifecycle, SendEmailModal, Table } from '../../../components/common/UI';
import { classifyLoadError, formatCurrency, statusClass, today } from '../../../utils/utils';
import { DocumentsPanel } from '../../../components/Assistant';

// --- EstimateDetailPage.jsx ---
function EstimateDetailPage() {
  const { estimateId } = useParams();
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [estimate, setEstimate] = useState(null);
  const [client, setClient] = useState(null);
  const [order, setOrder] = useState(null);
  const [versions, setVersions] = useState([]);
  const [revising, setRevising] = useState(false);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState(null);
  const [versionsError, setVersionsError] = useState(false);
  const [showConvert, setShowConvert] = useState(false);
  const [showSendEmail, setShowSendEmail] = useState(false);
  const [sentMessage, setSentMessage] = useState('');
  const [converting, setConverting] = useState(false);
  const [convertError, setConvertError] = useState('');
  // Family 137, feature 9 - Cost-Drift Alert.
  const [costDrift, setCostDrift] = useState(null);

  const load = useCallback(() => {
    setLoadError(null);
    estimatesAPI.get(estimateId).then((res) => {
      setEstimate(res.data);
      if (res.data.client_id) clientsAPI.get(res.data.client_id).then((r) => setClient(r.data)).catch(() => setClient('error'));
      if (res.data.order_id) ordersAPI.get(res.data.order_id).then((r) => setOrder(r.data)).catch(() => setOrder('error'));
    }).catch((err) => setLoadError(classifyLoadError(err, 'estimate')));
    setVersionsError(false);
    estimatesAPI.versions(estimateId).then((res) => setVersions(res.data)).catch(() => { setVersions([]); setVersionsError(true); });
    // Cost/margin figures are master-only (see _serialize_estimates) -
    // the cost-drift endpoint itself requires the master role, so this
    // is only ever fetched for a privileged user. A failure here (e.g.
    // no line items have a recorded cost basis yet) is left as null and
    // simply shown as "nothing to report" rather than an error - this is
    // a supplementary insight, not core estimate data.
    if (isPrivileged) {
      estimatesAPI.costDrift(estimateId).then((res) => setCostDrift(res.data)).catch(() => setCostDrift(null));
    }
  }, [estimateId, isPrivileged]);

  useEffect(() => {
    // Defect repair (F138 P4.2): estimateId changing (notably via
    // handleRevise below, which navigates from this same page to the
    // freshly-created next version's own /estimates/:id) means this is
    // a different estimate now, not a background refresh of the one
    // already on screen - reset per-estimate state so the previous
    // version's data can't flash under the new estimate's URL while the
    // new estimate is still loading. load() itself (called again for
    // the SAME estimateId elsewhere) must keep doing the opposite and
    // never clear already-good data.
    setEstimate(null);
    setClient(null);
    setOrder(null);
    setVersions([]);
    setCostDrift(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estimateId]);

  useEffect(load, [load]);

  const handleRevise = async () => {
    setRevising(true);
    setError('');
    try {
      const res = await estimatesAPI.revise(estimateId);
      navigate(`/estimates/${res.data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create a new version');
    } finally {
      setRevising(false);
    }
  };

  const handleConvertToOrder = async (formData) => {
    setConverting(true);
    setConvertError('');
    try {
      const res = await ordersAPI.create({
        client_id: estimate.client_id,
        project_type: estimate.description ? estimate.description.slice(0, 100) : undefined,
        order_date: new Date(formData.order_date).toISOString(),
        advance: formData.advance || '0',
        from_estimate_id: estimate.id,
      });
      navigate(`/orders/${res.data.id}`);
    } catch (err) {
      setConvertError(err.response?.data?.detail || 'Failed to convert this estimate into an order');
    } finally {
      setConverting(false);
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
  if (!estimate) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/estimates" className="btn-link">&larr; Back to Estimates</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{estimate.estimate_code}</h1>
          <div className="detail-subtitle">
            {client?.name || 'Client'} &middot; Version {estimate.version}
            {' '}<span className={`status-badge ${statusClass(estimate.status)}`}>{estimate.status}</span>
            {estimate.business_id && <span className="business-id-badge">{estimate.business_id}</span>}
          </div>
        </div>
        <div className="page-actions">
          {isPrivileged && (
            <button className="btn-secondary" onClick={handleRevise} disabled={revising}>
              {revising ? 'Creating...' : 'Create New Version'}
            </button>
          )}
          {isPrivileged && !estimate.order_id && estimate.status === 'approved' && (
            <button className="btn-primary" onClick={() => setShowConvert(true)}>Convert to Order</button>
          )}
          {isPrivileged && (
            <button className="btn-secondary" onClick={() => setShowSendEmail(true)}>Send to Client</button>
          )}
          <a className="btn-secondary" href={reportsAPI.downloadUrl(`estimates/${estimate.id}/quote.pdf`)} target="_blank" rel="noreferrer">
            Download Quote PDF
          </a>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {sentMessage && <Alert type="success" message={sentMessage} onClose={() => setSentMessage('')} />}

      <div className="kpi-row">
        {isPrivileged && (
          <>
            <Card><div className="card-body"><div className="detail-meta-label">Subtotal</div><h3>{formatCurrency(estimate.subtotal)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Discount</div><h3>{formatCurrency(estimate.discount)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Tax ({Number(estimate.tax_percent)}%)</div><h3>{formatCurrency(estimate.tax_amount)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Total Estimate</div><h3>{formatCurrency(estimate.total_cost)}</h3></div></Card>
          </>
        )}
      </div>

      {/* Family 137, feature 9 - Cost-Drift Alert. FACT: the cost
          comparison below is directly computed from recorded cost
          snapshots vs current cost - never a decision. Nothing here
          changes the estimate; the human reviews and acts through the
          normal edit/revise actions above. */}
      {isPrivileged && costDrift && costDrift.drifted_line_items > 0 && (
        <Card title="Cost-Drift Alert">
          <div className="card-body">
            <Alert
              type="warning"
              onClose={() => {}}
              message={
                `Costs have moved since this estimate was quoted ${costDrift.quote_age_days} day(s) ago. `
                + `Cost: ${formatCurrency(costDrift.original_cost_total)} \u2192 ${formatCurrency(costDrift.current_cost_total)} `
                + `(${costDrift.cost_delta_total >= 0 ? '+' : ''}${formatCurrency(costDrift.cost_delta_total)}). `
                + (costDrift.original_margin_percent != null && costDrift.current_margin_percent != null
                  ? `Projected margin: ${costDrift.original_margin_percent}% \u2192 ${costDrift.current_margin_percent}% if the quoted price is unchanged.`
                  : '')
              }
            />
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr><th>Line Item</th><th>Original Cost</th><th>Current Cost</th><th>Delta</th><th>Margin (was &rarr; now)</th></tr>
                </thead>
                <tbody>
                  {costDrift.items.filter((i) => Number(i.cost_delta) !== 0).map((i) => (
                    <tr key={i.line_item_id}>
                      <td>{i.description}</td>
                      <td>{formatCurrency(i.original_cost)}</td>
                      <td>{formatCurrency(i.current_cost)}</td>
                      <td>{Number(i.cost_delta) >= 0 ? '+' : ''}{formatCurrency(i.cost_delta)}</td>
                      <td>{i.original_margin_percent != null ? `${i.original_margin_percent}% \u2192 ${i.current_margin_percent}%` : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {costDrift.skipped_line_items > 0 && (
              <p className="detail-meta-label" style={{ marginTop: 12 }}>
                {costDrift.skipped_line_items} line item(s) could not be checked (no linked product or no recorded cost basis).
              </p>
            )}
          </div>
        </Card>
      )}

      {estimate.line_items?.length > 0 && (
        <Card title="Line Items">
          <Table
            columns={[
              { key: 'description', label: 'Description', render: (v, row) => (
                <>
                  {v}
                  {row.product_name && (
                    <div className="order-item-product-link">{row.product_code} &middot; {row.product_name}</div>
                  )}
                </>
              ) },
              { key: 'category', label: 'Category', render: (v) => v || '-' },
              { key: 'quantity', label: 'Qty', render: (v) => Number(v), align: 'right' },
              { key: 'unit', label: 'Unit', render: (v) => v || '-' },
              ...(isPrivileged ? [
                { key: 'rate', label: 'Rate', render: formatCurrency, align: 'right' },
                { key: 'amount', label: 'Amount', render: formatCurrency, align: 'right' },
              ] : []),
            ]}
            data={estimate.line_items}
          />
        </Card>
      )}

      <Card title="Estimate Details">
        <div className="card-body">
          <div className="detail-meta">
            <div className="detail-meta-item"><span className="detail-meta-label">Client</span><span className="detail-meta-value">{client === 'error' ? 'Unavailable' : client ? <Link to={`/clients/${client.id}`}>{client.name}</Link> : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Related Order</span><span className="detail-meta-value">{order === 'error' ? 'Unavailable' : order ? <Link to={`/orders/${order.id}`}>{order.order_code}</Link> : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Valid Until</span><span className="detail-meta-value">{estimate.valid_until ? new Date(estimate.valid_until).toLocaleDateString() : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Created</span><span className="detail-meta-value">{new Date(estimate.created_at).toLocaleDateString()}</span></div>
          </div>
          {estimate.description && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Scope</span>
              <p>{estimate.description}</p>
            </div>
          )}
          {estimate.remarks && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Remarks</span>
              <p>{estimate.remarks}</p>
            </div>
          )}
        </div>
      </Card>

      {(versions.length > 1 || versionsError) && (
        <Card title="Version History">
          <Table
            columns={[
              { key: 'version', label: 'Version' }, { key: 'estimate_code', label: 'Estimate Code' },
              { key: 'total_cost', label: 'Total', render: formatCurrency, align: 'right' },
              { key: 'status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
              { key: 'created_at', label: 'Created', render: (v) => new Date(v).toLocaleDateString() },
            ]}
            data={versions}
            error={versionsError}
            onRetry={load}
            onRowClick={(row) => navigate(`/estimates/${row.id}`)}
          />
        </Card>
      )}

      <Modal isOpen={showConvert} title="Convert to Order" onClose={() => { setShowConvert(false); setConvertError(''); }}>
        {convertError && <Alert type="error" message={convertError} onClose={() => setConvertError('')} />}
        <p style={{ marginBottom: 16, color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
          This creates a new order for {client?.name || 'this client'} using this estimate's line items and total
          ({formatCurrency(estimate.total_cost)}). The estimate will be linked to the new order.
        </p>
        <Form
          fields={[
            { name: 'order_date', label: 'Order Date', type: 'date', required: true },
            { name: 'advance', label: 'Advance Received', type: 'number' },
          ]}
          onSubmit={handleConvertToOrder} loading={converting} submitText="Create Order"
          initialValues={{ order_date: today() }}
        />
      </Modal>
      <SendEmailModal
        isOpen={showSendEmail}
        title={`Send Estimate ${estimate.estimate_code}`}
        previewFn={() => estimatesAPI.emailPreview(estimateId)}
        sendFn={(data) => estimatesAPI.sendEmail(estimateId, data)}
        onClose={() => setShowSendEmail(false)}
        onSent={(message) => setSentMessage(message)}
      />
    </div>
  );
}

// --- OrderDetailPage.jsx ---
const TABS = ['Overview', 'Communication', 'Payments', 'Expenses', 'Materials', 'Tasks', 'Production', 'Profitability'];

function OrderDetailPage() {
  const { orderId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const canViewFinancials = user?.role === 'master';
  const [order, setOrder] = useState(null);
  const [client, setClient] = useState(null);
  const [materials, setMaterials] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [payments, setPayments] = useState(null);
  const [expenses, setExpenses] = useState(null);
  const [issues, setIssues] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [aiReports, setAiReports] = useState([]);
  const [productionJobs, setProductionJobs] = useState([]);
  const [profitability, setProfitability] = useState(null);
  const [materialRequirements, setMaterialRequirements] = useState(null);
  const [materialRiskDismissed, setMaterialRiskDismissed] = useState(false);
  const [orderHealth, setOrderHealth] = useState(null);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState(null);
  const [sendEmailKind, setSendEmailKind] = useState(null); // 'order' | 'invoice' | null
  const [sentMessage, setSentMessage] = useState('');
  const [tab, setTab] = useState('Overview');
  // Project communication (comments) + activity timeline, plus the AI
  // summarize/draft helpers (rule-based, never sends anything - see
  // communication_ai_service.py).
  const [comments, setComments] = useState([]);
  const [commentsError, setCommentsError] = useState(false);
  const [activityFeed, setActivityFeed] = useState([]);
  const [newComment, setNewComment] = useState('');
  const [commentError, setCommentError] = useState('');
  const [insights, setInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [draftPurpose, setDraftPurpose] = useState('follow_up');
  const [draftResult, setDraftResult] = useState(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftError, setDraftError] = useState('');
  const [activeAction, setActiveAction] = useState(null); // 'payment' | 'expense' | 'issue' | 'task' | 'production'
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState('');
  const [pendingDeletePayment, setPendingDeletePayment] = useState(null);
  const [deletingPayment, setDeletingPayment] = useState(false);
  const [sendReceiptPaymentId, setSendReceiptPaymentId] = useState(null);
  // Family 137, feature 8 - Approved Specification / Sample Lock.
  const [approvedSpecs, setApprovedSpecs] = useState([]);
  const [approvedSpecsError, setApprovedSpecsError] = useState(false);
  const [showApproveSpecForm, setShowApproveSpecForm] = useState(false);
  const [approvingSpec, setApprovingSpec] = useState(false);
  const [approveSpecError, setApproveSpecError] = useState('');
  // Family 137, feature 2 - Visual Build Timeline.
  const [buildTimeline, setBuildTimeline] = useState(null);
  // Family 137, feature 12 - Capacity-Aware Delivery Promise. The
  // evaluation is a PREDICTION + RECOMMENDATION only, requested
  // on-demand rather than loaded automatically - recording the final
  // date is the one explicit human decision.
  const [promiseRequestedDate, setPromiseRequestedDate] = useState('');
  const [promiseEvaluation, setPromiseEvaluation] = useState(null);
  const [evaluatingPromise, setEvaluatingPromise] = useState(false);
  const [promiseError, setPromiseError] = useState('');
  const [promiseReason, setPromiseReason] = useState('');
  const [recordingPromise, setRecordingPromise] = useState(false);

  const closeAction = () => { setActiveAction(null); setActionError(''); };

  const handleApproveSpecification = async (formData) => {
    setApprovingSpec(true);
    setApproveSpecError('');
    try {
      await ordersAPI.approveSpecification(orderId, {
        material: formData.material || null,
        finish: formData.finish || null,
        veneer: formData.veneer || null,
        laminate: formData.laminate || null,
        colour: formData.colour || null,
        hardware: formData.hardware || null,
        batch_reference: formData.batch_reference || null,
        sample_photo_path: formData.sample_photo_path || null,
        notes: formData.notes || null,
        approved_by: formData.approved_by || null,
      });
      setShowApproveSpecForm(false);
      load();
    } catch (err) {
      setApproveSpecError(err.response?.data?.detail || 'Failed to record the approved specification.');
    } finally {
      setApprovingSpec(false);
    }
  };

  // Family 137, feature 12 - Capacity-Aware Delivery Promise.
  const handleEvaluateDeliveryPromise = async () => {
    if (!promiseRequestedDate) { setPromiseError('Pick a requested delivery date first.'); return; }
    setEvaluatingPromise(true); setPromiseError(''); setPromiseEvaluation(null);
    try {
      const res = await ordersAPI.evaluateDeliveryPromise(orderId, new Date(promiseRequestedDate).toISOString());
      setPromiseEvaluation(res.data);
    } catch (err) {
      setPromiseError(err.response?.data?.detail || 'Failed to evaluate this delivery date.');
    } finally {
      setEvaluatingPromise(false);
    }
  };

  const handleRecordDeliveryPromise = async (dateIso) => {
    setRecordingPromise(true); setPromiseError('');
    try {
      await ordersAPI.recordDeliveryPromise(orderId, {
        promised_date: new Date(dateIso).toISOString(),
        reason: promiseReason || null,
      });
      setPromiseEvaluation(null);
      setPromiseRequestedDate('');
      setPromiseReason('');
      load();
    } catch (err) {
      setPromiseError(err.response?.data?.detail || 'Failed to record the promised delivery date.');
    } finally {
      setRecordingPromise(false);
    }
  };

  const handleQuickPayment = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await paymentsAPI.create({ ...formData, order_id: Number(orderId), date: new Date(formData.date).toISOString() });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to record payment'); }
    finally { setActionLoading(false); }
  };

  const confirmDeletePayment = async () => {
    setActionError('');
    setDeletingPayment(true);
    try {
      await paymentsAPI.remove(pendingDeletePayment.id);
      setPendingDeletePayment(null);
      load();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to delete payment');
      setPendingDeletePayment(null);
    } finally {
      setDeletingPayment(false);
    }
  };

  const handleQuickExpense = async (formData) => {    setActionLoading(true); setActionError('');
    try {
      await projectExpensesAPI.create({ ...formData, order_id: Number(orderId), date: new Date(formData.date).toISOString() });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to add expense'); }
    finally { setActionLoading(false); }
  };

  const handleQuickIssue = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await issuesAPI.create({ ...formData, order_id: Number(orderId), material_id: Number(formData.material_id), date: new Date(formData.date).toISOString() });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to issue material'); }
    finally { setActionLoading(false); }
  };

  const handleQuickTask = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await dailyTasksAPI.create({ ...formData, order_id: Number(orderId), employee_id: Number(formData.employee_id), date: new Date(formData.date).toISOString() });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to assign task'); }
    finally { setActionLoading(false); }
  };

  const handleQuickProduction = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await productionJobsAPI.create({
        ...formData, order_id: Number(orderId),
        employee_id: formData.employee_id ? Number(formData.employee_id) : null,
        material_id: formData.material_id ? Number(formData.material_id) : null,
        date: new Date(formData.date).toISOString(),
        planned_qty: Number(formData.planned_qty || 0),
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to create production job'); }
    finally { setActionLoading(false); }
  };

  const load = useCallback(() => {
    setLoadError(null);
    ordersAPI.get(orderId).then((res) => {
      setOrder(res.data);
      clientsAPI.get(res.data.client_id).then((r) => setClient(r.data)).catch(() => setClient('error'));
    }).catch((err) => setLoadError(classifyLoadError(err, 'order')));

    issuesAPI.list({ order_id: orderId }).then((res) => setIssues(res.data)).catch((err) => setIssues(err.response?.status === 403 ? 'forbidden' : 'error'));
    dailyTasksAPI.list({ order_id: orderId }).then((res) => setTasks(res.data)).catch((err) => setTasks(err.response?.status === 403 ? 'forbidden' : 'error'));
    ordersAPI.aiReports(orderId).then((res) => setAiReports(res.data)).catch(() => setAiReports([]));
    productionJobsAPI.list({ order_id: orderId }).then((res) => setProductionJobs(res.data)).catch((err) => setProductionJobs(err.response?.status === 403 ? 'forbidden' : 'error'));

    paymentsAPI.list({ order_id: orderId }).then((res) => setPayments(res.data)).catch((err) => setPayments(err.response?.status === 403 ? 'forbidden' : 'error'));
    projectExpensesAPI.list({ order_id: orderId }).then((res) => setExpenses(res.data)).catch((err) => setExpenses(err.response?.status === 403 ? 'forbidden' : 'error'));
    ordersAPI.profitability(orderId).then((res) => setProfitability(res.data)).catch((err) => setProfitability(err.response?.status === 403 ? 'forbidden' : 'error'));
    ordersAPI.materialRequirements(orderId).then((res) => setMaterialRequirements(res.data.materials)).catch(() => setMaterialRequirements('error'));
    // Deterministic Order Health/Risk (Family 130 P0.1) - same
    // authoritative computation the chatbot's "what is blocking this
    // order" query uses. Drives the header's Next Action/risk line
    // below instead of the page re-deriving it from raw tasks.
    ordersAPI.health(orderId).then((res) => setOrderHealth(res.data)).catch(() => setOrderHealth(null));

    setCommentsError(false);
    ordersAPI.listComments(orderId).then((res) => setComments(res.data)).catch(() => { setComments([]); setCommentsError(true); });
    ordersAPI.activity(orderId).then((res) => setActivityFeed(res.data)).catch(() => setActivityFeed([]));

    setApprovedSpecsError(false);
    ordersAPI.listApprovedSpecifications(orderId).then((res) => setApprovedSpecs(res.data)).catch(() => { setApprovedSpecs([]); setApprovedSpecsError(true); });

    // Family 137, feature 2 - Visual Build Timeline (Milestone +
    // ProductionJob status, reusing the same order-health computation).
    ordersAPI.buildTimeline(orderId).then((res) => setBuildTimeline(res.data)).catch(() => setBuildTimeline(null));
  }, [orderId]);

  useEffect(load, [load]);

  // Materials/employees are company-wide reference data for the
  // add-task/add-issue forms on this page, not order-specific - they
  // do not change when an order is mutated, so fetching them again on
  // every load() call (every payment/task/issue/expense/job created)
  // was pure waste. Fetched once per page visit instead.
  useEffect(() => {
    materialsAPI.list().then((res) => setMaterials(res.data)).catch(() => setMaterials([]));
    employeesAPI.list().then((res) => setEmployees(res.data)).catch(() => setEmployees([]));
  }, []);

  const handleAddComment = async (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    setCommentError('');
    try {
      await ordersAPI.addComment(orderId, { text: newComment.trim() });
      setNewComment('');
      load();
    } catch (err) {
      setCommentError(err.response?.data?.detail || 'Failed to add comment');
    }
  };

  const handleGetInsights = async () => {
    setInsightsLoading(true); setInsights(null);
    try {
      const res = await communicationAPI.insights('order', orderId);
      setInsights(res.data);
    } catch (err) {
      setInsights({ error: err.response?.data?.detail || 'Unable to generate insights.' });
    } finally {
      setInsightsLoading(false);
    }
  };

  const handleGetDraft = async () => {
    setDraftLoading(true); setDraftResult(null); setDraftError('');
    try {
      const res = await communicationAPI.draft('order', orderId, draftPurpose);
      setDraftResult(res.data);
    } catch (err) {
      setDraftError(err.response?.data?.detail || 'Unable to generate a draft.');
    } finally {
      setDraftLoading(false);
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
  if (!order) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      {sentMessage && <Alert type="success" message={sentMessage} onClose={() => setSentMessage('')} />}
      <div className="detail-header">
        <div>
          <Link to="/orders" className="btn-link">&larr; Back to Orders</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{order.order_code}</h1>
          <div className="detail-subtitle">
            {client?.name || 'Client'} &middot; {order.project_type || 'Project'}
            {order.business_id && <span className="business-id-badge">{order.business_id}</span>}
          </div>
          {order.source_estimate_id && (
            <div className="detail-subtitle" style={{ marginTop: 4 }}>
              Converted from{' '}
              <Link to={`/estimates/${order.source_estimate_id}`}>{order.source_estimate_code}</Link>
            </div>
          )}
          <OrderLifecycle order={order} />
          <div className="detail-meta">
            {orderHealth?.next_action && (
              // Sourced from OrderService.compute_order_health's priority-ordered
              // next_action (blocked task > material shortage > production
              // blocker > overdue task > delivery risk > earliest open task) -
              // not re-derived from raw tasks here, so a generic open task can
              // never hide a stronger business blocker (Family 130 P0.1 s.5).
              <div className="detail-meta-item">
                <span className="detail-meta-label">Next Action</span>
                <span className="detail-meta-value">
                  {orderHealth.next_action.description}
                  {orderHealth.next_action.detail ? ` — ${orderHealth.next_action.detail}` : ''}
                </span>
              </div>
            )}
            {orderHealth && orderHealth.risk_level !== 'ON_TRACK' && (
              <div className="detail-meta-item">
                <span className="detail-meta-label">Needs Attention</span>
                <span className="detail-meta-value">
                  <span className={`status-badge ${
                    orderHealth.risk_level === 'CRITICAL' ? 'status-danger'
                      : orderHealth.risk_level === 'AT_RISK' ? 'status-danger' : 'status-warning'
                  }`}>
                    {orderHealth.risk_level === 'CRITICAL' ? 'Critical'
                      : orderHealth.risk_level === 'AT_RISK' ? 'At Risk' : 'Watch'}
                  </span>{' '}
                  {orderHealth.reasons[0]}
                </span>
              </div>
            )}
            {orderHealth?.readiness && (
              // Structured, non-fabricated readiness (Family 130 P0.1 s.6) -
              // "unavailable" means no real data exists for that dimension
              // yet, never a hidden pass. No percentage is invented.
              <div className="detail-meta-item">
                <span className="detail-meta-label">Readiness</span>
                <span className="detail-meta-value" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {Object.entries(orderHealth.readiness).map(([dim, state]) => {
                    const cls = ['blocked', 'at_risk', 'overdue'].includes(state) ? 'status-danger'
                      : ['ready', 'on_track', 'delivered'].includes(state) ? 'status-ok'
                      : state === 'in_progress' ? 'status-warning' : 'status-muted';
                    return (
                      <span key={dim} className={`status-badge ${cls}`} title={`${dim}: ${state}`}>
                        {dim}: {state.replace('_', ' ')}
                      </span>
                    );
                  })}
                </span>
              </div>
            )}
          </div>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl(`orders/${order.id}/estimate.pdf`)} target="_blank" rel="noreferrer">
            Download Estimate PDF
          </a>
          {canViewFinancials && (
            <button className="btn-secondary" onClick={() => setSendEmailKind('order')}>Send Order</button>
          )}
          {canViewFinancials && (
            <a className="btn-secondary" href={reportsAPI.downloadUrl(`orders/${order.id}/invoice.pdf`)} target="_blank" rel="noreferrer">
              Download Invoice
            </a>
          )}
          {canViewFinancials && (
            <button className="btn-secondary" onClick={() => setSendEmailKind('invoice')}>Send Invoice</button>
          )}
        </div>
      </div>

      <div className="kpi-row">
        {canViewFinancials && (
          <>
            <Card><div className="card-body"><div className="detail-meta-label">Order Value</div><h3>{formatCurrency(order.order_value)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Amount Received</div><h3>{formatCurrency(order.total_received)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Outstanding Balance</div><h3>{formatCurrency(order.balance)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Payment Status</div><h3><span className={`status-badge ${statusClass(order.payment_status)}`}>{order.payment_status}</span></h3></div></Card>
          </>
        )}
        <Card><div className="card-body"><div className="detail-meta-label">Progress</div><h3>{order.progress_percent}%</h3></div></Card>
      </div>

      {!materialRiskDismissed && Array.isArray(materialRequirements) && materialRequirements.some((m) => Number(m.shortage) > 0) && (() => {
        const shortages = materialRequirements.filter((m) => Number(m.shortage) > 0);
        const top = shortages[0];
        const topSupplier = top.supplier_options?.[0];
        return (
          <Alert
            type="error"
            onClose={() => setMaterialRiskDismissed(true)}
            message={
              <>
                <strong>Order at material risk.</strong> Short {top.shortage} {top.unit} of {top.material_name}
                {shortages.length > 1 ? ` (+${shortages.length - 1} other material(s))` : ''}.
                {topSupplier
                  ? ` ${topSupplier.supplier_name} can supply this${topSupplier.lead_time_days != null ? ` (${topSupplier.lead_time_days}d lead time)` : ''} - recommend reviewing procurement.`
                  : ' No supplier option is on file for this material yet - recommend reviewing procurement.'}
              </>
            }
          />
        );
      })()}

      <div className="page-actions" style={{ marginBottom: 'var(--space-5)' }}>
        {canViewFinancials && <button className="btn-secondary" onClick={() => setActiveAction('payment')}>Record Payment</button>}
        {canViewFinancials && <button className="btn-secondary" onClick={() => setActiveAction('expense')}>Add Expense</button>}
        <button className="btn-secondary" onClick={() => setActiveAction('issue')}>Issue Material</button>
        <button className="btn-secondary" onClick={() => setActiveAction('task')}>Assign Task</button>
        <button className="btn-secondary" onClick={() => setActiveAction('production')}>Create Production Job</button>
      </div>

      <div className="tab-bar">
        {TABS.map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && (
        <Card title="Project Overview">
          <div className="card-body">
            <div className="detail-meta">
              <div className="detail-meta-item"><span className="detail-meta-label">Client Phone</span><span className="detail-meta-value">{client?.phone ? <a href={`tel:${client.phone}`}>{client.phone}</a> : '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Client Email</span><span className="detail-meta-value">{client?.email ? <a href={`mailto:${client.email}`}>{client.email}</a> : '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Order Date</span><span className="detail-meta-value">{new Date(order.order_date).toLocaleDateString()}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Delivery Date</span><span className="detail-meta-value">{order.delivery_date ? new Date(order.delivery_date).toLocaleDateString() : '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Supervisor</span><span className="detail-meta-value">{order.supervisor || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Priority</span><span className="detail-meta-value">{order.priority || '-'}</span></div>
            </div>
            {order.site_address && (
              <div style={{ marginTop: 16 }}>
                <span className="detail-meta-label">Site Address</span>
                <p>{order.site_address}</p>
              </div>
            )}
            {order.remarks && (
              <div style={{ marginTop: 16 }}>
                <span className="detail-meta-label">Remarks</span>
                <p>{order.remarks}</p>
              </div>
            )}
          </div>
        </Card>
      )}

      {tab === 'Overview' && order.items?.length > 0 && (
        <Card title="Order Scope">
          <div className="table-container">
          <table className="data-table">
            <thead>
              <tr><th>Description</th><th>Category</th><th>Qty</th><th>Unit</th>{canViewFinancials && <><th>Rate</th><th>Amount</th></>}</tr>
            </thead>
            <tbody>
              {order.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    {item.description}
                    {item.product_name && (
                      <div className="order-item-product-link">{item.product_code} &middot; {item.product_name}</div>
                    )}
                  </td>
                  <td>{item.category || '-'}</td>
                  <td>{Number(item.quantity)}</td><td>{item.unit || '-'}</td>
                  {canViewFinancials && <><td>{formatCurrency(item.rate)}</td><td>{formatCurrency(item.amount)}</td></>}
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </Card>
      )}

      {tab === 'Overview' && (
        <Card
          title="Approved Specification"
          actions={canViewFinancials && (
            <button className="btn-secondary" onClick={() => setShowApproveSpecForm(true)}>Record New Approval</button>
          )}
        >
          <div className="card-body">
            {approvedSpecsError && <p className="detail-meta-value">Could not load approved specifications.</p>}
            {!approvedSpecsError && approvedSpecs.length === 0 && (
              <p className="detail-meta-value">No specification has been approved for this order yet.</p>
            )}
            {approvedSpecs.length > 0 && (() => {
              const current = approvedSpecs.find((s) => s.status === 'approved') || approvedSpecs[0];
              const history = approvedSpecs.filter((s) => s.id !== current.id);
              return (
                <>
                  <div className="detail-meta">
                    {current.material && <div className="detail-meta-item"><span className="detail-meta-label">Material</span><span className="detail-meta-value">{current.material}</span></div>}
                    {current.finish && <div className="detail-meta-item"><span className="detail-meta-label">Finish</span><span className="detail-meta-value">{current.finish}</span></div>}
                    {current.veneer && <div className="detail-meta-item"><span className="detail-meta-label">Veneer</span><span className="detail-meta-value">{current.veneer}</span></div>}
                    {current.laminate && <div className="detail-meta-item"><span className="detail-meta-label">Laminate</span><span className="detail-meta-value">{current.laminate}</span></div>}
                    {current.colour && <div className="detail-meta-item"><span className="detail-meta-label">Colour</span><span className="detail-meta-value">{current.colour}</span></div>}
                    {current.hardware && <div className="detail-meta-item"><span className="detail-meta-label">Hardware</span><span className="detail-meta-value">{current.hardware}</span></div>}
                    {current.batch_reference && <div className="detail-meta-item"><span className="detail-meta-label">Batch/Reference</span><span className="detail-meta-value">{current.batch_reference}</span></div>}
                    <div className="detail-meta-item"><span className="detail-meta-label">Approved By</span><span className="detail-meta-value">{current.approved_by || '-'}</span></div>
                    <div className="detail-meta-item"><span className="detail-meta-label">Approved On</span><span className="detail-meta-value">{new Date(current.approved_at).toLocaleString()}</span></div>
                    <div className="detail-meta-item"><span className="detail-meta-label">Version</span><span className="detail-meta-value">v{current.version}</span></div>
                  </div>
                  {current.notes && (
                    <div style={{ marginTop: 16 }}>
                      <span className="detail-meta-label">Notes</span>
                      <p>{current.notes}</p>
                    </div>
                  )}
                  {history.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <span className="detail-meta-label">Prior Versions</span>
                      <div className="table-container">
                        <table className="data-table">
                          <thead>
                            <tr><th>Version</th><th>Material</th><th>Finish</th><th>Colour</th><th>Batch/Reference</th><th>Approved By</th><th>Approved On</th><th>Status</th></tr>
                          </thead>
                          <tbody>
                            {history.map((s) => (
                              <tr key={s.id}>
                                <td>v{s.version}</td><td>{s.material || '-'}</td><td>{s.finish || '-'}</td>
                                <td>{s.colour || '-'}</td><td>{s.batch_reference || '-'}</td>
                                <td>{s.approved_by || '-'}</td><td>{new Date(s.approved_at).toLocaleDateString()}</td>
                                <td><span className={`status-badge ${statusClass(s.status)}`}>{s.status}</span></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        </Card>
      )}

      {tab === 'Overview' && buildTimeline && (
        <Card title="Build Timeline">
          <div className="card-body">
            {buildTimeline.milestones.length === 0 && (
              <p className="detail-meta-value">No milestones have been added to this order yet.</p>
            )}
            {buildTimeline.milestones.length > 0 && (
              <div className="table-container">
                <table className="data-table">
                  <thead><tr><th>Milestone</th><th>Target Date</th><th>Completed</th><th>Status</th></tr></thead>
                  <tbody>
                    {buildTimeline.milestones.map((m) => (
                      <tr key={m.id}>
                        <td>{m.name}</td>
                        <td>{m.target_date ? new Date(m.target_date).toLocaleDateString() : '-'}</td>
                        <td>{m.completed_date ? new Date(m.completed_date).toLocaleDateString() : '-'}</td>
                        <td>
                          <span className={`status-badge ${
                            m.status === 'completed' ? 'status-ok'
                              : m.status === 'delayed' || m.status === 'at_risk' ? 'status-danger'
                              : m.status === 'current' ? 'status-warning' : 'status-neutral'
                          }`}>
                            {m.status === 'at_risk' ? 'At Risk' : m.status.charAt(0).toUpperCase() + m.status.slice(1)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {buildTimeline.production_summary?.has_production_jobs && (
              <div className="detail-meta" style={{ marginTop: 16 }}>
                <div className="detail-meta-item"><span className="detail-meta-label">Production Jobs</span>
                  <span className="detail-meta-value">{buildTimeline.production_summary.total_jobs}</span></div>
                <div className="detail-meta-item"><span className="detail-meta-label">Completed</span>
                  <span className="detail-meta-value">{buildTimeline.production_summary.completed_jobs}</span></div>
                <div className="detail-meta-item"><span className="detail-meta-label">Pending</span>
                  <span className="detail-meta-value">{buildTimeline.production_summary.pending_jobs}</span></div>
                <div className="detail-meta-item"><span className="detail-meta-label">Blocked</span>
                  <span className="detail-meta-value">{buildTimeline.production_summary.blocked_jobs}</span></div>
              </div>
            )}
          </div>
        </Card>
      )}

      {tab === 'Overview' && canViewFinancials && (
        <Card title="Delivery Promise">
          <div className="card-body">
            <p className="detail-meta-value">
              Current promised delivery date: {order.delivery_date ? new Date(order.delivery_date).toLocaleDateString() : 'Not set'}.
              Evaluating a date is a recommendation only - nothing is saved until you record it below.
            </p>
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <input type="date" value={promiseRequestedDate} onChange={(e) => setPromiseRequestedDate(e.target.value)} />
              <button className="btn-secondary" disabled={evaluatingPromise} onClick={handleEvaluateDeliveryPromise}>
                {evaluatingPromise ? 'Evaluating...' : 'Evaluate This Date'}
              </button>
            </div>
            {promiseError && <Alert type="error" message={promiseError} onClose={() => setPromiseError('')} />}
            {promiseEvaluation && (
              <div style={{ marginTop: 12 }}>
                <span className={`status-badge ${
                  promiseEvaluation.feasibility === 'FEASIBLE' ? 'status-ok'
                    : promiseEvaluation.feasibility === 'AT_RISK' ? 'status-warning' : 'status-danger'
                }`}>
                  {promiseEvaluation.feasibility} (confidence: {promiseEvaluation.confidence})
                </span>
                <ul>
                  {promiseEvaluation.reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
                {promiseEvaluation.alternative_dates.length > 0 && (
                  <p className="detail-meta-value">
                    Suggested alternatives: {promiseEvaluation.alternative_dates.map((d) => new Date(d).toLocaleDateString()).join(', ')}
                  </p>
                )}
                <p className="detail-meta-value">{promiseEvaluation.historical_context}</p>
                <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                  <input type="text" placeholder="Reason for the final decision (optional)" value={promiseReason}
                         onChange={(e) => setPromiseReason(e.target.value)} />
                  <button className="btn-primary" disabled={recordingPromise}
                          onClick={() => handleRecordDeliveryPromise(promiseEvaluation.requested_date)}>
                    {recordingPromise ? 'Recording...' : 'Record This as the Promised Date'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {tab === 'Overview' && aiReports.length > 0 && (
        <Card title="AI Insights">
          <div className="card-body">
            {aiReports.slice(0, 3).map((r) => (
              <div key={r.id} className="detail-meta-item" style={{ marginBottom: 12 }}>
                <span className={`status-badge ${
                  r.risk_level === 'CRITICAL' || r.risk_level === 'AT_RISK' ? 'status-danger'
                    : r.risk_level === 'WATCH' ? 'status-warning' : 'status-ok'
                }`}>
                  {r.risk_level === 'CRITICAL' ? 'Critical'
                    : r.risk_level === 'AT_RISK' ? 'At Risk'
                    : r.risk_level === 'WATCH' ? 'Watch' : 'On Track'}
                </span>
                <span className="detail-meta-label">{new Date(r.created_at).toLocaleString()}</span>
                {r.findings.blocked_tasks?.length > 0 && (
                  <span className="detail-meta-value">
                    Blocked: {r.findings.blocked_tasks.map((t) => t.description).join(', ')}
                  </span>
                )}
                {r.findings.delivery_at_risk && (
                  <span className="detail-meta-value">Delivery date is close with work still open.</span>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {tab === 'Overview' && (
        <DocumentsPanel title="Documents" api={{
          list: () => documentsAPI.list('order', orderId),
          upload: (file, description) => documentsAPI.upload('order', orderId, file, description),
          downloadUrl: (documentId) => documentsAPI.downloadUrl('order', orderId, documentId),
          remove: (documentId) => documentsAPI.remove('order', orderId, documentId),
        }} canUpload={canViewFinancials} />
      )}

      {tab === 'Communication' && (
        <>
          <Card title="Project Comments">
            <div className="card-body">
              {commentError && <Alert type="error" message={commentError} onClose={() => setCommentError('')} />}
              {commentsError && (
                <p className="page-summary">
                  Unable to load comments.{' '}
                  <button type="button" className="btn-link" onClick={load}>Retry</button>
                </p>
              )}
              {!commentsError && comments.length === 0 && <p className="page-summary">No comments yet.</p>}
              {comments.map((c) => (
                <div key={c.id} className="detail-meta-item" style={{ marginBottom: 12 }}>
                  <span className="detail-meta-label">{c.author} &middot; {new Date(c.date).toLocaleString()}</span>
                  <span className="detail-meta-value">{c.text}</span>
                </div>
              ))}
              <form onSubmit={handleAddComment} style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <input
                  className="form-input" style={{ flex: 1 }} placeholder="Add a comment - use @username to mention someone"
                  value={newComment} onChange={(e) => setNewComment(e.target.value)}
                />
                <button type="submit" className="btn-secondary">Post</button>
              </form>
            </div>
          </Card>

          <Card title="Activity Timeline">
            <div className="card-body">
              {activityFeed.length === 0 && <p className="page-summary">No activity recorded for this project yet.</p>}
              {activityFeed.map((a, idx) => (
                <div key={idx} className="detail-meta-item" style={{ marginBottom: 12 }}>
                  <span className="detail-meta-label">
                    {a.type?.replace('_', ' ')} &middot; {a.author ? `${a.author} &middot; ` : ''}{a.date ? new Date(a.date).toLocaleString() : ''}
                  </span>
                  <span className="detail-meta-value">{a.text || a.title}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card title="AI Summary (rule-based, not a live language model)">
            <div className="card-body">
              <p className="page-summary">
                Summarizes the comments actually recorded on this project - extracts action items and
                flags anything left unanswered. This never contacts an external AI service and nothing
                is invented beyond what was written above.
              </p>
              <button className="btn-secondary" onClick={handleGetInsights} disabled={insightsLoading}>
                {insightsLoading ? 'Summarizing...' : 'Summarize Communication'}
              </button>
              {insights && insights.error && <Alert type="error" message={insights.error} />}
              {insights && !insights.error && (
                <div style={{ marginTop: 16 }}>
                  <div className="detail-meta-item">
                    <span className="detail-meta-label">Summary ({insights.entry_count} entries)</span>
                    <span className="detail-meta-value">{insights.summary}</span>
                  </div>
                  {insights.action_items?.length > 0 && (
                    <div className="detail-meta-item">
                      <span className="detail-meta-label">Action Items</span>
                      <ul>{insights.action_items.map((it, i) => <li key={i}>{it}</li>)}</ul>
                    </div>
                  )}
                  {insights.unanswered_items?.length > 0 && (
                    <div className="detail-meta-item">
                      <span className="detail-meta-label">Unanswered</span>
                      <ul>{insights.unanswered_items.map((it, i) => <li key={i}>{it}</li>)}</ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>

          <Card title="Draft a Message">
            <div className="card-body">
              <p className="page-summary">
                A template-filled draft for you to review and send yourself through your usual channel.
                Nothing is ever sent automatically from here.
              </p>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <select className="form-input" value={draftPurpose} onChange={(e) => setDraftPurpose(e.target.value)}>
                  <option value="follow_up">Follow-up</option>
                  <option value="status_update">Status Update</option>
                  {canViewFinancials && <option value="payment_reminder">Payment Reminder</option>}
                </select>
                <button className="btn-secondary" onClick={handleGetDraft} disabled={draftLoading}>
                  {draftLoading ? 'Drafting...' : 'Generate Draft'}
                </button>
              </div>
              {draftError && <Alert type="error" message={draftError} onClose={() => setDraftError('')} />}
              {draftResult && (
                <div style={{ marginTop: 16 }}>
                  <textarea className="form-input" style={{ width: '100%', minHeight: 140 }} readOnly value={draftResult.draft} />
                  <p className="page-summary">{draftResult.note}</p>
                </div>
              )}
            </div>
          </Card>
        </>
      )}

      {tab === 'Payments' && (
        payments === 'forbidden'
          ? <Alert type="info" message="You do not have permission to view payments for this order." />
          : (
            <Table
              columns={[
                { key: 'receipt_code', label: 'Receipt' },
                { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
                { key: 'payment_type', label: 'Type' }, { key: 'payment_mode', label: 'Mode' },
                { key: 'amount', label: 'Amount', render: formatCurrency, align: 'right' },
                { key: 'received_by', label: 'Received By' },
                {
                  key: 'send_receipt_action', label: '', render: (v, row) => (
                    canViewFinancials ? (
                      <button className="btn-link" onClick={(e) => { e.stopPropagation(); setSendReceiptPaymentId(row.id); }}>Send Receipt</button>
                    ) : null
                  ),
                },
                {
                  key: 'delete_action', label: '', render: (v, row) => (
                    canViewFinancials ? (
                      <button className="btn-link" onClick={(e) => { e.stopPropagation(); setPendingDeletePayment(row); }}>Delete</button>
                    ) : null
                  ),
                },
              ]}
              data={payments === 'error' ? [] : (payments || [])}
              error={payments === 'error'}
              onRetry={load}
              emptyMessage="No payments recorded for this order yet."
            />
          )
      )}

      {tab === 'Expenses' && (
        expenses === 'forbidden'
          ? <Alert type="info" message="You do not have permission to view expenses for this order." />
          : (
            <Table
              columns={[
                { key: 'expense_code', label: 'Expense' },
                { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
                { key: 'category', label: 'Category' }, { key: 'description', label: 'Description' },
                { key: 'amount', label: 'Amount', render: formatCurrency, align: 'right' },
              ]}
              data={expenses === 'error' ? [] : (expenses || [])}
              error={expenses === 'error'}
              onRetry={load}
              emptyMessage="No project expenses recorded yet."
            />
          )
      )}

      {tab === 'Materials' && (
        issues === 'forbidden'
          ? <Alert type="info" message="You do not have permission to view materials issued for this order." />
          : (
            <>
              {materialRequirements === 'error' ? null : materialRequirements && materialRequirements.length > 0 && (
                <Card title="Material Requirement + Shortage" style={{ marginBottom: 'var(--space-4)' }}>
                  <div className="card-body">
                    <Table
                      columns={[
                        { key: 'material_name', label: 'Material' },
                        { key: 'required', label: 'Required', render: (v, row) => `${v} ${row.unit}` },
                        { key: 'available', label: 'Available' },
                        { key: 'reserved_by_other_orders', label: 'Reserved (Other Orders)' },
                        { key: 'pending_purchase_quantity', label: 'Pending Purchase' },
                        {
                          key: 'shortage', label: 'Shortage',
                          render: (v) => Number(v) > 0
                            ? <span style={{ color: 'var(--danger)', fontWeight: 600 }}>{v}</span>
                            : <span style={{ color: 'var(--success)' }}>None</span>,
                        },
                        {
                          key: 'supplier_options', label: 'Recommended Supplier',
                          render: (v, row) => {
                            if (Number(row.shortage) <= 0) return '-';
                            const top = v?.[0];
                            if (!top) return <span style={{ color: 'var(--text-secondary)' }}>No supplier on file</span>;
                            return `${top.supplier_name}${top.lead_time_days != null ? ` (${top.lead_time_days}d)` : ''}`;
                          },
                        },
                      ]}
                      data={materialRequirements}
                      emptyMessage="No products with a bill of materials on this order."
                    />
                  </div>
                </Card>
              )}
              <Table
                columns={[
                  { key: 'issue_code', label: 'Issue' },
                  { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
                  { key: 'material_id', label: 'Material', render: (v) => materials.find((m) => m.id === v)?.name || v },
                  { key: 'quantity_issued', label: 'Quantity' }, { key: 'issued_to', label: 'Issued To' },
                ]}
                data={issues === 'error' ? [] : (issues || [])}
                error={issues === 'error'}
                onRetry={load}
                emptyMessage="No materials issued to this project yet."
              />
            </>
          )
      )}

      {tab === 'Tasks' && (
        tasks === 'forbidden'
          ? <Alert type="info" message="You do not have permission to view tasks for this order." />
          : (
            <Table
              columns={[
                { key: 'task_code', label: 'Task' }, { key: 'task_description', label: 'Description' },
                { key: 'priority', label: 'Priority' },
                { key: 'status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
                { key: 'completion_percent', label: 'Completion %' },
              ]}
              data={tasks === 'error' ? [] : (tasks || [])}
              error={tasks === 'error'}
              onRetry={load}
              emptyMessage="No tasks assigned to this project yet."
            />
          )
      )}

      {tab === 'Production' && (
        productionJobs === 'forbidden'
          ? <Alert type="info" message="You do not have permission to view production jobs for this order." />
          : (
            <Table
              columns={[
                { key: 'job_code', label: 'Job' }, { key: 'machine', label: 'Machine' },
                { key: 'operation', label: 'Operation' },
                { key: 'planned_qty', label: 'Planned' }, { key: 'completed_qty', label: 'Completed' },
                { key: 'status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
              ]}
              data={productionJobs === 'error' ? [] : (productionJobs || [])}
              error={productionJobs === 'error'}
              onRetry={load}
              emptyMessage="No production jobs recorded for this project yet."
            />
          )
      )}

      {tab === 'Profitability' && (
        profitability === 'forbidden'
          ? <Alert type="info" message="You do not have permission to view profitability for this order." />
          : profitability === 'error'
          ? (
            <Card>
              <div className="card-body" style={{ textAlign: 'center' }}>
                <p style={{ margin: 0 }}>Unable to load profitability. Please try again.</p>
                <button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button>
              </div>
            </Card>
          )
          : profitability && (
            <Card title="Order Profitability">
              <div className="card-body">
                <div className="detail-meta">
                  <div className="detail-meta-item"><span className="detail-meta-label">Order Value</span><span className="detail-meta-value">{formatCurrency(profitability.order_value)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Total Received</span><span className="detail-meta-value">{formatCurrency(profitability.total_received)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Pending Payment</span><span className="detail-meta-value">{formatCurrency(profitability.pending_payment)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Project Expenses</span><span className="detail-meta-value">{formatCurrency(profitability.project_expenses)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Material Cost (Issued)</span><span className="detail-meta-value">{formatCurrency(profitability.material_cost)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Estimated Gross Profit</span><span className="detail-meta-value">{formatCurrency(profitability.estimated_gross_profit)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Gross Margin</span><span className="detail-meta-value">{(profitability.gross_margin_ratio * 100).toFixed(1)}%</span></div>
                </div>
              </div>
            </Card>
          )
      )}

      <Modal isOpen={activeAction === 'payment'} title="Record Payment" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'payment_type', label: 'Payment Type', type: 'select', required: true, options: [
              { value: 'Advance', label: 'Advance' }, { value: 'Progress Payment', label: 'Progress Payment' }, { value: 'Internal', label: 'Internal' },
            ] },
            { name: 'payment_mode', label: 'Payment Mode', type: 'select', required: true, options: [
              { value: 'Cash', label: 'Cash' }, { value: 'UPI', label: 'UPI' }, { value: 'Bank', label: 'Bank' }, { value: 'Credit Card', label: 'Credit Card' },
            ] },
            { name: 'amount', label: 'Amount', type: 'number', required: true },
            { name: 'reference_number', label: 'Reference No.' },
            { name: 'received_by', label: 'Received By' },
          ]}
          onSubmit={handleQuickPayment} loading={actionLoading} submitText="Record Payment"
          initialValues={{ date: today(), received_by: user?.full_name || user?.username || '' }}
        />
      </Modal>

      <Modal isOpen={activeAction === 'expense'} title="Add Project Expense" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'category', label: 'Category', required: true },
            { name: 'description', label: 'Description' },
            { name: 'paid_to', label: 'Paid To' },
            { name: 'amount', label: 'Amount', type: 'number', required: true },
            { name: 'approved_by', label: 'Approved By' },
          ]}
          onSubmit={handleQuickExpense} loading={actionLoading} submitText="Add Expense"
          initialValues={{ date: today(), approved_by: user?.full_name || user?.username || '' }}
        />
      </Modal>

      <Modal isOpen={activeAction === 'issue'} title="Issue Material" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'material_id', label: 'Material', type: 'select', required: true, options: materials.map((m) => ({ value: m.id, label: `${m.name} (${m.current_stock} in stock)` })) },
            { name: 'quantity_issued', label: 'Quantity Issued', type: 'number', required: true },
            { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets' },
            { name: 'issued_to', label: 'Issued To' },
            { name: 'department', label: 'Department' },
            { name: 'purpose', label: 'Purpose' },
            { name: 'approved_by', label: 'Approved By' },
          ]}
          onSubmit={handleQuickIssue} loading={actionLoading} submitText="Issue Material"
          initialValues={{ date: today(), approved_by: user?.full_name || user?.username || '' }}
        />
      </Modal>

      <Modal isOpen={activeAction === 'task'} title="Assign Task" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'employee_id', label: 'Employee', type: 'select', required: true, options: employees.map((e) => ({ value: e.id, label: e.name })) },
            { name: 'task_description', label: 'Task Description', required: true, type: 'textarea' },
            { name: 'priority', label: 'Priority', type: 'select', options: [
              { value: 'Low', label: 'Low' }, { value: 'Medium', label: 'Medium' },
              { value: 'High', label: 'High' }, { value: 'Urgent', label: 'Urgent' },
            ] },
            { name: 'checked_by', label: 'Checked By' },
          ]}
          onSubmit={handleQuickTask} loading={actionLoading} submitText="Assign Task"
          initialValues={{ date: today(), checked_by: user?.full_name || user?.username || '' }}
        />
      </Modal>

      <Modal isOpen={activeAction === 'production'} title="Create Production Job" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'machine', label: 'Machine' },
            { name: 'operation', label: 'Operation' },
            { name: 'employee_id', label: 'Operator', type: 'select', options: employees.map((e) => ({ value: e.id, label: e.name })) },
            { name: 'material_id', label: 'Material', type: 'select', options: materials.map((m) => ({ value: m.id, label: m.name })) },
            { name: 'planned_qty', label: 'Planned Quantity', type: 'number', required: true },
          ]}
          onSubmit={handleQuickProduction} loading={actionLoading} submitText="Create Production Job"
          initialValues={{ date: today() }}
        />
      </Modal>

      {/* Family 137, feature 8 - Approved Specification / Sample Lock.
          Never edits an existing approval - each submit creates a new
          version and supersedes the previous one, preserving full
          history (see create_approved_specification). */}
      <Modal isOpen={showApproveSpecForm} title="Record New Approval" onClose={() => { setShowApproveSpecForm(false); setApproveSpecError(''); }}>
        {approveSpecError && <Alert type="error" message={approveSpecError} onClose={() => setApproveSpecError('')} />}
        <Form
          fields={[
            { name: 'material', label: 'Material' },
            { name: 'finish', label: 'Finish' },
            { name: 'veneer', label: 'Veneer' },
            { name: 'laminate', label: 'Laminate' },
            { name: 'colour', label: 'Colour' },
            { name: 'hardware', label: 'Hardware' },
            { name: 'batch_reference', label: 'Batch/Reference' },
            { name: 'approved_by', label: 'Approved By (client/contact name)' },
            { name: 'notes', label: 'Notes', type: 'textarea' },
          ]}
          onSubmit={handleApproveSpecification}
          loading={approvingSpec}
          submitText="Record Approval"
          initialValues={{
            material: '', finish: '', veneer: '', laminate: '', colour: '',
            hardware: '', batch_reference: '', approved_by: '', notes: '',
          }}
        />
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDeletePayment}
        message={pendingDeletePayment ? `Delete payment ${pendingDeletePayment.receipt_code} (${formatCurrency(pendingDeletePayment.amount)})? This cannot be undone.` : ''}
        onConfirm={confirmDeletePayment}
        onCancel={() => setPendingDeletePayment(null)}
        loading={deletingPayment}
      />

      <SendEmailModal
        isOpen={!!sendEmailKind}
        title={sendEmailKind === 'invoice' ? `Send Invoice - ${order.order_code}` : `Send Order - ${order.order_code}`}
        previewFn={() => ordersAPI.emailPreview(orderId, sendEmailKind)}
        sendFn={(data) => ordersAPI.sendEmail(orderId, sendEmailKind, data)}
        onClose={() => setSendEmailKind(null)}
        onSent={(message) => setSentMessage(message)}
      />

      <SendEmailModal
        isOpen={!!sendReceiptPaymentId}
        title="Send Payment Receipt"
        previewFn={() => paymentsAPI.emailPreview(sendReceiptPaymentId)}
        sendFn={(data) => paymentsAPI.sendEmail(sendReceiptPaymentId, data)}
        onClose={() => setSendReceiptPaymentId(null)}
        onSent={(message) => setSentMessage(message)}
      />
    </div>
  );
}

export { EstimateDetailPage, OrderDetailPage };
