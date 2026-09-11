import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { clientsAPI, ordersAPI, estimatesAPI, paymentsAPI, clientActivitiesAPI, communicationAPI, reportsAPI, clientProductRateAPI, productsAPI, clientDocumentsAPI } from '../../../utils/api';
import { Table } from '../../../components/common/UI';
import { Card } from '../../../components/common/UI';
import { DocumentsPanel } from '../../../components/Assistant';
import { Modal } from '../../../components/common/UI';
import { Form } from '../../../components/common/UI';
import { Alert } from '../../../components/common/UI';
import { ConfirmDialog } from '../../../components/common/UI';
import { formatCurrency, today } from '../../../utils/utils';


function ClientDetailPage() {
  const { clientId } = useParams();
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isStrictlyMaster = user?.role === 'master';
  const canViewFinancials = user?.role === 'master';
  const TABS = canViewFinancials
    ? ['Overview', 'Orders', 'Estimates', 'Payments', 'Pricing', 'Activity', 'Timeline']
    : ['Overview', 'Orders', 'Estimates', 'Activity', 'Timeline'];
  const [client, setClient] = useState(null);
  const [orders, setOrders] = useState([]);
  const [estimates, setEstimates] = useState([]);
  const [payments, setPayments] = useState([]);
  const [activities, setActivities] = useState([]);
  const [tab, setTab] = useState('Overview');
  const [activeAction, setActiveAction] = useState(null); // 'order' | 'estimate' | 'payment' | 'activity'
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState('');
  // AI summary of this client's communication history
  // (rule-based extractive summary, never a real LLM call - see
  // communication_ai_service.py).
  const [insights, setInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [editingActivity, setEditingActivity] = useState(null);
  const [pendingDeleteActivity, setPendingDeleteActivity] = useState(null);
  const [deletingActivity, setDeletingActivity] = useState(false);
  const [pendingDeletePayment, setPendingDeletePayment] = useState(null);
  const [deletingPayment, setDeletingPayment] = useState(false);
  const [productRates, setProductRates] = useState([]);
  const [products, setProducts] = useState([]);
  const [showAddRate, setShowAddRate] = useState(false);
  const [pendingDeleteRate, setPendingDeleteRate] = useState(null);
  const [deletingRate, setDeletingRate] = useState(false);
  const [rateError, setRateError] = useState('');
  const [loadError, setLoadError] = useState('');
  // Family 137, feature 5 - Unified Client Relationship Timeline.
  // Fetched only when the Timeline tab is actually opened, not on
  // every page load - this is a broader, heavier aggregation than the
  // Activity tab's own manual log.
  const [relationshipTimeline, setRelationshipTimeline] = useState(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState('');

  const load = useCallback(() => {
    setLoadError('');
    clientsAPI.get(clientId).then((res) => setClient(res.data)).catch(() => setLoadError('Unable to load this client.'));
    ordersAPI.list({ client_id: clientId }).then((res) => setOrders(res.data));
    if (canViewFinancials) {
      paymentsAPI.list({ client_id: clientId }).then((res) => setPayments(res.data)).catch(() => setPayments('error'));
    }
    estimatesAPI.list({ client_id: clientId }).then((res) => setEstimates(res.data));
    clientActivitiesAPI.list({ client_id: clientId }).then((res) => setActivities(res.data));
    if (canViewFinancials) {
      clientProductRateAPI.list({ client_id: clientId }).then((res) => setProductRates(res.data)).catch(() => setProductRates('error'));
    }
  }, [clientId, canViewFinancials]);

  useEffect(load, [load]);

  // Products is company-wide reference data for the add-product-rate
  // form, not client-specific - refetching it on every load() call
  // (every payment/activity/rate mutation on this page) was waste.
  useEffect(() => {
    if (canViewFinancials) {
      productsAPI.list({ is_active: true }).then((res) => setProducts(res.data)).catch(() => setProducts([]));
    }
  }, [canViewFinancials]);

  useEffect(() => {
    if (tab === 'Timeline' && !relationshipTimeline && !timelineLoading) {
      setTimelineLoading(true);
      setTimelineError('');
      clientsAPI.relationshipTimeline(clientId)
        .then((res) => setRelationshipTimeline(res.data))
        .catch(() => setTimelineError('Unable to load the relationship timeline.'))
        .finally(() => setTimelineLoading(false));
    }
  }, [tab, clientId, relationshipTimeline, timelineLoading]);

  const closeAction = () => { setActiveAction(null); setActionError(''); };

  const handleCreateOrder = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await ordersAPI.create({
        ...formData, client_id: Number(clientId),
        order_date: new Date(formData.order_date).toISOString(),
        order_value: formData.order_value || '0', advance: formData.advance || '0',
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to create order'); }
    finally { setActionLoading(false); }
  };

  const handleCreateEstimate = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await estimatesAPI.create({
        ...formData, client_id: Number(clientId),
        material_cost: formData.material_cost || '0', labor_cost: formData.labor_cost || '0',
        tax_percent: formData.tax_percent || '18',
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to create estimate'); }
    finally { setActionLoading(false); }
  };

  const handleRecordPayment = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await paymentsAPI.create({
        ...formData, order_id: Number(formData.order_id), date: new Date(formData.date).toISOString(),
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to record payment'); }
    finally { setActionLoading(false); }
  };

  const handleLogActivity = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await clientActivitiesAPI.create({
        ...formData, client_id: Number(clientId), date: new Date(formData.date).toISOString(),
        follow_up_date: formData.follow_up_date ? new Date(formData.follow_up_date).toISOString() : null,
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to log activity'); }
    finally { setActionLoading(false); }
  };

  const handleUpdateActivity = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await clientActivitiesAPI.update(editingActivity.id, {
        ...formData, date: new Date(formData.date).toISOString(),
        follow_up_date: formData.follow_up_date ? new Date(formData.follow_up_date).toISOString() : null,
      });
      setEditingActivity(null); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to update activity'); }
    finally { setActionLoading(false); }
  };

  const confirmDeleteActivity = async () => {
    setDeletingActivity(true);
    try {
      await clientActivitiesAPI.remove(pendingDeleteActivity.id);
      setPendingDeleteActivity(null); load();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to delete activity');
      setPendingDeleteActivity(null);
    } finally {
      setDeletingActivity(false);
    }
  };

  const confirmDeletePayment = async () => {
    setDeletingPayment(true);
    try {
      await paymentsAPI.remove(pendingDeletePayment.id);
      setPendingDeletePayment(null); load();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to delete payment');
      setPendingDeletePayment(null);
    } finally {
      setDeletingPayment(false);
    }
  };

  if (loadError) return <div className="page"><Alert type="error" message={loadError} /><button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button></div>;
  if (!client) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/clients" className="btn-link">&larr; Back to Clients</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{client.name}</h1>
          <div className="detail-subtitle">
            {client.client_code} &middot; {client.lead_source || 'Lead source not recorded'}
            {client.business_id && <span className="business-id-badge">{client.business_id}</span>}
          </div>
        </div>
        <div className="page-actions">
          {canViewFinancials && <button className="btn-secondary" onClick={() => setActiveAction('order')}>Create Order</button>}
          {canViewFinancials && <button className="btn-secondary" onClick={() => setActiveAction('estimate')}>Create Estimate</button>}
          {canViewFinancials && orders.length > 0 && (
            <button className="btn-secondary" onClick={() => setActiveAction('payment')}>Record Payment</button>
          )}
          <button className="btn-secondary" onClick={() => setActiveAction('activity')}>Log Activity</button>
          <a className="btn-secondary" href={reportsAPI.downloadUrl(`clients/${client.id}/profile.pdf`)} target="_blank" rel="noreferrer">Export PDF</a>
          <a className="btn-secondary" href={reportsAPI.downloadUrl(`clients.xlsx?search=${encodeURIComponent(client.client_code)}`)} target="_blank" rel="noreferrer">Export Excel</a>
        </div>
      </div>

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Total Orders</div><h3>{client.total_orders}</h3></div></Card>
        {canViewFinancials && (
          <Card><div className="card-body"><div className="detail-meta-label">Total Sales</div><h3>{formatCurrency(client.total_sales)}</h3></div></Card>
        )}
        {canViewFinancials && (
          <Card><div className="card-body"><div className="detail-meta-label">Outstanding Balance</div><h3>{formatCurrency(orders.reduce((sum, o) => sum + Number(o.balance || 0), 0))}</h3></div></Card>
        )}
        <Card><div className="card-body"><div className="detail-meta-label">Phone</div><h3 style={{ fontSize: '1.1rem' }}>{client.phone ? <a href={`tel:${client.phone}`}>{client.phone}</a> : '-'}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Email</div><h3 style={{ fontSize: '1.1rem' }}>{client.email ? <a href={`mailto:${client.email}`}>{client.email}</a> : '-'}</h3></div></Card>
      </div>

      <div className="tab-bar">
        {TABS.map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && (
        <>
        <Card title="Client Details">
          <div className="card-body">
            <div className="detail-meta">
              {client.contact_person && (
                <div className="detail-meta-item"><span className="detail-meta-label">Contact Person</span><span className="detail-meta-value">{client.contact_person}</span></div>
              )}
              {client.alternate_phone && (
                <div className="detail-meta-item"><span className="detail-meta-label">Alternate Phone</span><span className="detail-meta-value"><a href={`tel:${client.alternate_phone}`}>{client.alternate_phone}</a></span></div>
              )}
              <div className="detail-meta-item"><span className="detail-meta-label">Address</span><span className="detail-meta-value">{client.address || '-'}</span></div>
              {client.site_address && (
                <div className="detail-meta-item"><span className="detail-meta-label">Site Address</span><span className="detail-meta-value">{client.site_address}</span></div>
              )}
              {client.gstin && (
                <div className="detail-meta-item"><span className="detail-meta-label">GSTIN</span><span className="detail-meta-value">{client.gstin}</span></div>
              )}
              <div className="detail-meta-item"><span className="detail-meta-label">First Contact</span><span className="detail-meta-value">{client.first_contact_date ? new Date(client.first_contact_date).toLocaleDateString() : '-'}</span></div>
            </div>
            {client.remarks && (
              <div style={{ marginTop: 16 }}>
                <span className="detail-meta-label">Remarks</span>
                <p>{client.remarks}</p>
              </div>
            )}
          </div>
        </Card>
        <DocumentsPanel title="Documents" api={{
          list: () => clientDocumentsAPI.list(clientId),
          upload: (file, description) => clientDocumentsAPI.upload(clientId, file, description),
          downloadUrl: (documentId) => clientDocumentsAPI.downloadUrl(clientId, documentId),
          remove: (documentId) => clientDocumentsAPI.remove(clientId, documentId),
        }} canUpload={isStrictlyMaster} />
        </>
      )}

      {tab === 'Orders' && (
        <Table
          columns={[
            { key: 'order_code', label: 'Order' }, { key: 'project_type', label: 'Project Type' },
            { key: 'order_value', label: 'Order Value', render: formatCurrency, align: 'right' },
            { key: 'total_received', label: 'Received', render: formatCurrency, align: 'right' },
            { key: 'balance', label: 'Balance', render: formatCurrency, align: 'right' },
            { key: 'project_status', label: 'Status' },
          ]}
          data={orders}
          onRowClick={(row) => navigate(`/orders/${row.id}`)}
          emptyMessage="No orders for this client yet."
        />
      )}

      {tab === 'Estimates' && (
        <Table
          columns={[
            { key: 'estimate_code', label: 'Estimate' }, { key: 'description', label: 'Description' },
            { key: 'total_cost', label: 'Total', render: formatCurrency, align: 'right' }, { key: 'status', label: 'Status' },
          ]}
          data={estimates}
          emptyMessage="No estimates for this client yet."
        />
      )}

      {tab === 'Payments' && (
        <Table
          columns={[
            { key: 'receipt_code', label: 'Receipt' },
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'order_id', label: 'Order', render: (v) => orders.find((o) => o.id === v)?.order_code || v },
            { key: 'payment_type', label: 'Type' }, { key: 'payment_mode', label: 'Mode' },
            { key: 'amount', label: 'Amount', render: formatCurrency, align: 'right' },
            {
              key: 'delete_action', label: '', render: (v, row) => (
                <button className="btn-link" onClick={(e) => { e.stopPropagation(); setPendingDeletePayment(row); }}>Delete</button>
              ),
            },
          ]}
          data={payments === 'error' ? [] : payments}
          error={payments === 'error'}
          onRetry={load}
          emptyMessage="No payments recorded for this client yet."
        />
      )}

      {tab === 'Pricing' && (
        <>
          {rateError && <Alert type="error" message={rateError} onClose={() => setRateError('')} />}
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Customer-specific pricing for {client.name} - a negotiated margin or a directly agreed price for a
            specific product. This never changes the global Product Master price; other clients are unaffected.
          </p>
          <div className="page-actions" style={{ marginBottom: 12 }}>
            <button className="btn-primary" onClick={() => setShowAddRate(true)}>+ Add Customer Rate</button>
          </div>
          <Table
            columns={[
              { key: 'product_id', label: 'Product', render: (v) => products.find((p) => p.id === v)?.name || v },
              { key: 'margin_percent', label: 'Margin Override', render: (v) => v != null ? `${v}%` : '\u2014' },
              { key: 'fixed_selling_price', label: 'Fixed Price', render: (v) => v != null ? formatCurrency(v) : '\u2014' },
              { key: 'notes', label: 'Notes' },
              {
                key: 'delete_action', label: '', render: (v, row) => (
                  <button className="btn-link" onClick={(e) => { e.stopPropagation(); setPendingDeleteRate(row); }}>Remove</button>
                ),
              },
            ]}
            data={productRates === 'error' ? [] : productRates}
            error={productRates === 'error'}
            onRetry={load}
            emptyMessage="No customer-specific pricing for this client yet - the default Product/Rate Master pricing applies."
          />
        </>
      )}

      <Modal isOpen={showAddRate} title={`Add Customer Rate - ${client.name}`} onClose={() => setShowAddRate(false)}>
        <Form
          fields={[
            { name: 'product_id', label: 'Product', type: 'select', required: true,
              options: products.map((p) => ({ value: p.id, label: `${p.product_code} - ${p.name}` })) },
            { name: 'margin_percent', label: 'Margin % Override', type: 'number',
              hint: 'Set either this OR a fixed price below, not both.' },
            { name: 'fixed_selling_price', label: 'Fixed Selling Price', type: 'number' },
            { name: 'notes', label: 'Notes', type: 'textarea', advanced: true },
          ]}
          onSubmit={async (formData) => {
            setRateError('');
            try {
              await clientProductRateAPI.create({
                client_id: Number(clientId), product_id: Number(formData.product_id),
                margin_percent: formData.margin_percent || null,
                fixed_selling_price: formData.fixed_selling_price || null,
                notes: formData.notes || null,
              });
              setShowAddRate(false);
              load();
            } catch (err) {
              setRateError(err.response?.data?.detail || 'Failed to add customer rate');
            }
          }}
          submitText="Add Customer Rate"
        />
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDeleteRate}
        message={pendingDeleteRate ? `Remove this customer-specific rate? ${client.name} will go back to the default pricing for this product.` : ''}
        onConfirm={async () => {
          setDeletingRate(true);
          try {
            await clientProductRateAPI.remove(pendingDeleteRate.id);
            setPendingDeleteRate(null);
            load();
          } catch (err) {
            setRateError(err.response?.data?.detail || 'Failed to remove customer rate');
            setPendingDeleteRate(null);
          } finally {
            setDeletingRate(false);
          }
        }}
        onCancel={() => setPendingDeleteRate(null)}
        loading={deletingRate}
      />

      {tab === 'Activity' && (
        <Table
          columns={[
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleString() },
            { key: 'activity_type', label: 'Type' }, { key: 'summary', label: 'Summary' },
            { key: 'logged_by', label: 'Logged By' },
            {
              key: 'follow_up_date', label: 'Follow-up',
              render: (v, row) => {
                if (!v) return '-';
                if (row.follow_up_done) return <span style={{ color: 'var(--text-secondary)' }}>Done \u2713</span>;
                const overdue = new Date(v) < new Date();
                return (
                  <span>
                    <span className={overdue ? 'follow-up-overdue' : ''}>{new Date(v).toLocaleDateString()}</span>
                    {' '}
                    <button
                      className="btn-link"
                      onClick={async (e) => {
                        e.stopPropagation();
                        await clientActivitiesAPI.completeFollowUp(row.id);
                        load();
                      }}
                    >
                      Mark Done
                    </button>
                  </span>
                );
              },
            },
            {
              key: 'edit_action', label: '', render: (v, row) => (
                <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingActivity(row); }}>Edit</button>
              ),
            },
            {
              key: 'delete_action', label: '', render: (v, row) => (
                isStrictlyMaster ? (
                  <button className="btn-link" onClick={(e) => { e.stopPropagation(); setPendingDeleteActivity(row); }}>Delete</button>
                ) : null
              ),
            },
          ]}
          data={activities}
          emptyMessage="No activity logged for this client yet. Log calls, meetings, and site visits here."
        />
      )}

      {tab === 'Timeline' && (
        <Card title="Relationship Timeline">
          <div className="card-body">
            {timelineLoading && <p className="detail-meta-value">Loading timeline...</p>}
            {timelineError && <Alert type="error" message={timelineError} onClose={() => setTimelineError('')} />}
            {relationshipTimeline && relationshipTimeline.entries.length === 0 && (
              <p className="detail-meta-value">Nothing recorded yet for this client.</p>
            )}
            {relationshipTimeline && relationshipTimeline.entries.length > 0 && (
              <div className="table-container">
                <table className="data-table">
                  <thead><tr><th>Date</th><th>Type</th><th>Details</th></tr></thead>
                  <tbody>
                    {relationshipTimeline.entries.map((e, i) => (
                      <tr key={i}>
                        <td>{e.date ? new Date(e.date).toLocaleString() : '-'}</td>
                        <td><span className="status-badge status-neutral">{e.type.replace('_', ' ')}</span></td>
                        <td>
                          {e.path ? <Link to={e.path}>{e.text}</Link> : e.text}
                          {e.author ? <span className="detail-meta-label"> - {e.author}</span> : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </Card>
      )}

      {tab === 'Activity' && (
        <Card title="AI Summary (rule-based, not a live language model)">
          <div className="card-body">
            <p className="page-summary">
              Summarizes this client's communication history exactly as logged above - no external AI
              service is contacted and nothing is invented beyond what was actually recorded.
            </p>
            <button
              className="btn-secondary"
              onClick={async () => {
                setInsightsLoading(true); setInsights(null);
                try {
                  const res = await communicationAPI.insights('client', clientId);
                  setInsights(res.data);
                } catch (err) {
                  setInsights({ error: err.response?.data?.detail || 'Unable to generate insights.' });
                } finally {
                  setInsightsLoading(false);
                }
              }}
              disabled={insightsLoading}
            >
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
      )}

      <Modal isOpen={activeAction === 'order'} title="Create Order" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'project_type', label: 'Project Type' },
            { name: 'order_value', label: 'Order Value', type: 'number', required: true },
            { name: 'advance', label: 'Advance', type: 'number' },
            { name: 'order_date', label: 'Order Date', type: 'date', required: true },
          ]}
          onSubmit={handleCreateOrder} loading={actionLoading} submitText="Create Order"
          initialValues={{ order_date: today() }}
        />
      </Modal>

      <Modal isOpen={activeAction === 'estimate'} title="Create Estimate" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'description', label: 'Scope / Description', type: 'textarea' },
            { name: 'material_cost', label: 'Material Cost', type: 'number', required: true },
            { name: 'labor_cost', label: 'Labor Cost', type: 'number', required: true },
            { name: 'tax_percent', label: 'Tax %', type: 'number', placeholder: '18' },
          ]}
          onSubmit={handleCreateEstimate} loading={actionLoading} submitText="Create Estimate"
        />
      </Modal>

      <Modal isOpen={activeAction === 'payment'} title="Record Payment" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'order_id', label: 'Order', type: 'select', required: true, options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'payment_type', label: 'Payment Type', type: 'select', required: true, options: [
              { value: 'Advance', label: 'Advance' }, { value: 'Progress Payment', label: 'Progress Payment' }, { value: 'Internal', label: 'Internal' },
            ] },
            { name: 'payment_mode', label: 'Payment Mode', type: 'select', required: true, options: [
              { value: 'Cash', label: 'Cash' }, { value: 'UPI', label: 'UPI' }, { value: 'Bank', label: 'Bank' }, { value: 'Credit Card', label: 'Credit Card' },
            ] },
            { name: 'amount', label: 'Amount', type: 'number', required: true },
            { name: 'received_by', label: 'Received By' },
          ]}
          onSubmit={handleRecordPayment} loading={actionLoading} submitText="Record Payment"
          initialValues={{ date: today(), received_by: user?.full_name || user?.username || '' }}
        />
      </Modal>

      <Modal isOpen={activeAction === 'activity'} title="Log Activity" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'activity_type', label: 'Activity Type', type: 'select', required: true, options: [
              { value: 'Call', label: 'Call' }, { value: 'Meeting', label: 'Meeting' },
              { value: 'Email', label: 'Email' }, { value: 'Site Visit', label: 'Site Visit' }, { value: 'Note', label: 'Note' },
            ] },
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'summary', label: 'Summary', type: 'textarea', required: true },
            { name: 'logged_by', label: 'Logged By' },
            { name: 'follow_up_date', label: 'Follow-up Date (optional)', type: 'date', advanced: true },
          ]}
          onSubmit={handleLogActivity} loading={actionLoading} submitText="Log Activity"
          initialValues={{ date: today(), logged_by: user?.full_name || user?.username || '' }}
        />
      </Modal>

      <Modal isOpen={!!editingActivity} title="Edit Activity" onClose={() => { setEditingActivity(null); setActionError(''); }}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        {editingActivity && (
          <Form
            fields={[
              { name: 'activity_type', label: 'Activity Type', type: 'select', required: true, options: [
                { value: 'Call', label: 'Call' }, { value: 'Meeting', label: 'Meeting' },
                { value: 'Email', label: 'Email' }, { value: 'Site Visit', label: 'Site Visit' }, { value: 'Note', label: 'Note' },
              ] },
              { name: 'date', label: 'Date', type: 'date', required: true },
              { name: 'summary', label: 'Summary', type: 'textarea', required: true },
              { name: 'logged_by', label: 'Logged By' },
              { name: 'follow_up_date', label: 'Follow-up Date (optional)', type: 'date', advanced: true },
            ]}
            onSubmit={handleUpdateActivity} loading={actionLoading} submitText="Save Changes"
            initialValues={{
              ...editingActivity,
              date: editingActivity.date ? editingActivity.date.slice(0, 10) : '',
              follow_up_date: editingActivity.follow_up_date ? editingActivity.follow_up_date.slice(0, 10) : '',
            }}
          />
        )}
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDeleteActivity}
        message={pendingDeleteActivity ? `Delete this ${pendingDeleteActivity.activity_type?.toLowerCase() || 'activity'} entry? This cannot be undone.` : ''}
        onConfirm={confirmDeleteActivity}
        onCancel={() => setPendingDeleteActivity(null)}
        loading={deletingActivity}
      />

      <ConfirmDialog
        isOpen={!!pendingDeletePayment}
        message={pendingDeletePayment ? `Delete payment ${pendingDeletePayment.receipt_code} (${formatCurrency(pendingDeletePayment.amount)})? This cannot be undone.` : ''}
        onConfirm={confirmDeletePayment}
        onCancel={() => setPendingDeletePayment(null)}
        loading={deletingPayment}
      />
    </div>
  );
}

export default ClientDetailPage;
