// Sales list pages: estimates and orders. Combines the former
// EstimatesPage.jsx and OrdersPage.jsx.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { LineItemEditor, emptyRow, quantityViolatesWholeUnitRule } from './SalesSupportPages';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { clientsAPI, estimatesAPI, ordersAPI, reportsAPI } from '../../../utils/api';
import { Alert, Card, Form, Modal, Pagination, SendEmailModal, KpiStrip } from '../../../components/common/UI';
import { formatCurrency, statusClass, today } from '../../../utils/utils';
import { OrderIcon, MaterialIcon, TruckIcon, PaymentIcon, EmployeeIcon, EstimateIcon, ChatIcon, ArrowUpRightIcon, AlertTriangleIcon, PrinterIcon } from '../../../components/icons';

// --- EstimatesPage.jsx ---
const ESTIMATE_STATUS_TABS = [
  { value: '', label: 'All' }, { value: 'draft', label: 'Draft' }, { value: 'sent', label: 'Sent' },
  { value: 'approved', label: 'Approved' }, { value: 'changes_requested', label: 'Changes Requested' },
  { value: 'rejected', label: 'Rejected' }, { value: 'expired', label: 'Expired' }, { value: 'cancelled', label: 'Cancelled' },
];

function EstimatesPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  // workspace holds the one bounded GET /api/estimates/workspace response:
  // { summary, estimates: {items,total_count,limit,offset}, selected_estimate }.
  // Nothing here is fetched/derived a second time client-side - mirrors
  // OrdersPage/ClientsPage's own workspace state exactly.
  const [workspace, setWorkspace] = useState(null);
  const [selectedEstimateId, setSelectedEstimateId] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  // clients/orders are only needed for the New Estimate modal's pickers,
  // so (like Orders' own New Order modal) they're fetched lazily when
  // that modal actually opens, not on every page load/filter change.
  const [clients, setClients] = useState([]);
  const [clientsLoading, setClientsLoading] = useState(false);
  const [linkableOrders, setLinkableOrders] = useState([]);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [lineItems, setLineItems] = useState([emptyRow()]);
  const [selectedClientId, setSelectedClientId] = useState('');
  const [editingEstimate, setEditingEstimate] = useState(null);
  const [showConvert, setShowConvert] = useState(false);
  const [converting, setConverting] = useState(false);
  const [convertError, setConvertError] = useState('');
  const [showSendEmail, setShowSendEmail] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const activeFilters = () => {
    const params = {};
    if (statusFilter) params.status = statusFilter;
    if (search) params.search = search;
    return params;
  };

  // Same ref treatment OrdersPage/ClientsPage use: the mount effect must
  // read the *current* filters/selection without re-running whenever
  // they change (every change already triggers its own explicit load()).
  const activeFiltersRef = useRef(activeFilters);
  activeFiltersRef.current = activeFilters;
  const selectedEstimateIdRef = useRef(selectedEstimateId);
  selectedEstimateIdRef.current = selectedEstimateId;

  const load = useCallback((filterParams, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    setPageLoading(true);
    setLoadError(false);
    estimatesAPI.workspace({
      ...filterParams, limit: PAGE_SIZE, offset,
      selected_estimate_id: selectedEstimateIdRef.current || undefined,
    }).then((res) => {
      setWorkspace(res.data);
      if (res.data.selected_estimate) setSelectedEstimateId(res.data.selected_estimate.id);
    }).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
  }, []);

  useEffect(() => {
    load(activeFiltersRef.current());
  }, [load]);

  // Default the detail panel to the first row when nothing is selected
  // yet but the list isn't empty - a real estimate's data, never a mock.
  useEffect(() => {
    if (!pageLoading && workspace && !selectedEstimateId && workspace.estimates?.items?.length) {
      handleSelectEstimate(workspace.estimates.items[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageLoading, workspace]);

  const handleSelectEstimate = (estimateId) => {
    if (estimateId === selectedEstimateId && workspace?.selected_estimate) return;
    setSelectedEstimateId(estimateId);
    setDetailLoading(true);
    estimatesAPI.workspace({ selected_estimate_id: estimateId, detail_only: true }).then((res) => {
      setWorkspace((prev) => (prev ? { ...prev, selected_estimate: res.data.selected_estimate } : prev));
    }).catch(() => {}).finally(() => setDetailLoading(false));
  };

  const openNewEstimateModal = () => {
    setShowAdd(true);
    if (!clients.length) {
      setClientsLoading(true);
      clientsAPI.list().then((res) => setClients(res.data)).catch(() => {}).finally(() => setClientsLoading(false));
    }
    if (!linkableOrders.length) {
      ordersAPI.list().then((res) => setLinkableOrders(res.data)).catch(() => {});
    }
  };

  const applyFilters = (nextStatus, nextSearch) => {
    const params = {};
    if (nextStatus) params.status = nextStatus;
    if (nextSearch) params.search = nextSearch;
    setPage(1);
    load(params, 1);
  };

  const handleStatusTab = (value) => {
    setStatusFilter(value);
    applyFilters(value, search);
  };

  const handleSearch = (e) => {
    e.preventDefault();
    applyFilters(statusFilter, search);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(activeFilters(), pageNum);
  };

  // Mirrors the Clients page's own exportUrl() exactly - "Export
  // Estimates" previously always downloaded every estimate regardless
  // of the current status tab/search, unlike Export Clients (which
  // already respected its filters). Now the export matches what's on
  // screen here too.
  const exportUrl = () => {
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);
    if (search) params.set('search', search);
    const qs = params.toString();
    return reportsAPI.downloadUrl(`estimates.xlsx${qs ? `?${qs}` : ''}`);
  };

  const handleCreate = async (formData) => {
    if (!selectedClientId) {
      setError('Please select a client first.');
      return;
    }
    const invalidRow = lineItems.find((row) => row.description.trim() && quantityViolatesWholeUnitRule(row.quantity, row.unit));
    if (invalidRow) {
      setError(`"${invalidRow.description}" - ${invalidRow.unit} must be a whole number, not a fractional quantity.`);
      return;
    }
    setLoading(true);
    setError('');
    const validItems = lineItems
      .filter((row) => row.description.trim())
      .map((row) => ({
        description: row.description, category: row.category || null,
        quantity: row.quantity || '1', unit: row.unit || null, rate: row.rate || '0',
        product_id: row.product_id ? Number(row.product_id) : null,
      }));
    try {
      await estimatesAPI.create({
        ...formData,
        client_id: Number(selectedClientId),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        material_cost: formData.material_cost || '0',
        labor_cost: formData.labor_cost || '0',
        discount: formData.discount || '0',
        tax_percent: formData.tax_percent || '18',
        valid_until: formData.valid_until ? new Date(formData.valid_until).toISOString() : null,
        line_items: validItems,
      });
      setShowAdd(false);
      setLineItems([emptyRow()]);
      setSelectedClientId('');
      setSuccess('Estimate created.');
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create estimate');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await estimatesAPI.update(editingEstimate.id, {
        material_cost: formData.material_cost, labor_cost: formData.labor_cost,
        tax_percent: formData.tax_percent, status: formData.status,
        valid_until: formData.valid_until ? new Date(formData.valid_until).toISOString() : null,
        remarks: formData.remarks,
      });
      setEditingEstimate(null);
      setSuccess('Estimate updated.');
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update estimate');
    } finally {
      setLoading(false);
    }
  };

  const handleConvertToOrder = async (formData) => {
    setConverting(true);
    setConvertError('');
    try {
      const res = await ordersAPI.create({
        client_id: selected.client?.id,
        project_type: selected.description ? selected.description.slice(0, 100) : undefined,
        order_date: new Date(formData.order_date).toISOString(),
        advance: formData.advance || '0',
        from_estimate_id: selected.id,
      });
      navigate(`/orders/${res.data.id}`);
    } catch (err) {
      setConvertError(err.response?.data?.detail || 'Failed to convert this estimate into an order');
    } finally {
      setConverting(false);
    }
  };

  const createFields = [
    { name: 'order_id', label: 'Related Order (optional)', type: 'select', options: linkableOrders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'description', label: 'Scope / Description', type: 'textarea' },
    { name: 'discount', label: 'Discount', type: 'number', placeholder: '0', advanced: true },
    { name: 'tax_percent', label: 'Tax % (GST)', type: 'number', placeholder: '18', advanced: true },
    { name: 'valid_until', label: 'Valid Until', type: 'date', advanced: true },
    { name: 'remarks', label: 'Remarks', type: 'textarea', advanced: true },
  ];

  const editFields = [
    { name: 'material_cost', label: 'Material Cost', type: 'number', required: true },
    { name: 'labor_cost', label: 'Labor Cost', type: 'number', required: true },
    { name: 'tax_percent', label: 'Tax %', type: 'number' },
    { name: 'status', label: 'Status', type: 'select', options: [
      { value: 'draft', label: 'Draft' }, { value: 'sent', label: 'Sent' },
      { value: 'approved', label: 'Approved' }, { value: 'rejected', label: 'Rejected' },
      { value: 'expired', label: 'Expired' }, { value: 'cancelled', label: 'Cancelled' },
    ] },
    { name: 'valid_until', label: 'Valid Until', type: 'date' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  const summary = workspace?.summary || null;
  const estimateRows = workspace?.estimates?.items || [];
  const totalCount = workspace?.estimates?.total_count || 0;
  const offsetStart = workspace?.estimates?.offset ?? (page - 1) * PAGE_SIZE;
  const selected = workspace?.selected_estimate || null;

  const topStatuses = summary?.pipeline?.status_breakdown
    ? [...summary.pipeline.status_breakdown].filter((s) => s.count > 0).sort((a, b) => b.count - a.count).slice(0, 3)
    : [];

  // All 5 KPI chips come straight from workspace.summary - nothing
  // invented client-side. Estimate Value is a financial aggregate, so
  // (like Orders' Payment Due and Clients' Payment Due) it's simply
  // absent for a non-master viewer - and, to match those two pages'
  // layout exactly, it sits in the same second-to-last slot they use
  // for their own privileged-only pill, rather than the 2nd slot. That
  // way a non-master viewer sees the same "4 pills, gated one omitted
  // from the end" shape on every page, and the trailing pills never
  // shift position depending on role.
  const kpiItems = summary ? [
    { label: 'Total Estimates', value: summary.total_estimates, icon: EstimateIcon },
    { label: 'Pending Client Response', value: summary.pending_client_response, icon: ChatIcon, tone: summary.pending_client_response > 0 ? 'warning' : 'default' },
    { label: 'Conversion Pipeline', value: `${summary.conversion_pipeline.converted_count}${summary.conversion_pipeline.conversion_percent != null ? ` (${summary.conversion_pipeline.conversion_percent}%)` : ''}`, icon: ArrowUpRightIcon },
    ...(summary.estimate_value != null ? [{ label: 'Estimate Value', value: formatCurrency(summary.estimate_value.open_total_value), icon: PaymentIcon }] : []),
    { label: 'Expiring / Follow-up', value: summary.expiring_follow_up, icon: AlertTriangleIcon, tone: summary.expiring_follow_up > 0 ? 'warning' : 'default' },
  ] : [];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>
            Estimates &amp; Quotations
            {summary && <span className="home-card-chip" style={{ marginLeft: 10, verticalAlign: 'middle' }}>{summary.open_estimates} Active Estimates</span>}
          </h1>
          <p className="page-summary">Prepare and track client quotations before they convert to orders.</p>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {summary && <KpiStrip items={kpiItems} />}

      <div className="orders-workspace-toolbar">
        {isPrivileged && <button className="btn-primary" onClick={openNewEstimateModal}>+ New Estimate</button>}
        {/* estimates.xlsx is master-gated on the backend (see
            export_estimates in app/modules/sales/api.py) because every
            exported column is financial - gated here too, so the
            button never 403s for a non-master viewer. */}
        {isPrivileged && <a className="btn-secondary" href={exportUrl()} target="_blank" rel="noreferrer">Export Estimates</a>}
        {isPrivileged && <button className="btn-secondary" onClick={() => navigate('/estimates/import')}>Import Estimates</button>}
      </div>

      <div className="orders-summary-cards">
        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Estimate Pipeline</span>
            {summary && <span className="home-card-chip">{summary.open_estimates} Open</span>}
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.open_estimates}</span>
                <span className="orders-card-hero-caption">Open</span>
                {topStatuses.length > 0 && (
                  <span className="orders-card-hero-side">{topStatuses.map((s) => `${s.count} ${s.status}`).join(' • ')}</span>
                )}
              </div>
              {topStatuses[0] ? (
                <div className="orders-card-footer-row">
                  <span>{topStatuses[0].status}</span>
                  <strong>{topStatuses[0].count}</strong>
                </div>
              ) : (
                <div className="orders-card-footer-row"><span>No estimates yet.</span></div>
              )}
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Client Response</span>
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.client_response.pending}</span>
                <span className="orders-card-hero-caption">Awaiting Response</span>
              </div>
              {isPrivileged && summary.client_response.value != null && (
                <div className="orders-card-footer-row">
                  <span>Value</span>
                  <strong>{formatCurrency(summary.client_response.value)}</strong>
                </div>
              )}
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Conversion Overview</span>
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.conversion_pipeline.converted_count}</span>
                <span className="orders-card-hero-caption">Converted</span>
                {summary.conversion_pipeline.conversion_percent != null && (
                  <span className="orders-card-hero-side">{summary.conversion_pipeline.conversion_percent}% Conversion Rate</span>
                )}
              </div>
              {isPrivileged && summary.conversion_pipeline.converted_value != null && (
                <div className="orders-card-footer-row">
                  <span>Converted Value</span>
                  <strong>{formatCurrency(summary.conversion_pipeline.converted_value)}</strong>
                </div>
              )}
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Estimate Value</span>
          </div>
          {isPrivileged ? (
            summary?.estimate_value ? (
              <div className="orders-card-body">
                <div className="orders-card-hero">
                  <span className="orders-card-hero-number">{formatCurrency(summary.estimate_value.open_total_value)}</span>
                  <span className="orders-card-hero-caption">Open Total</span>
                </div>
                {summary.estimate_value.average_value != null && (
                  <div className="orders-card-footer-row">
                    <span>Average</span>
                    <strong>{formatCurrency(summary.estimate_value.average_value)}</strong>
                  </div>
                )}
              </div>
            ) : <div className="simple-chart-empty">Loading...</div>
          ) : (
            <div className="simple-chart-empty">Restricted to Master accounts.</div>
          )}
        </Card>
      </div>

      <div className="orders-workspace-grid">
        {/* All Estimates - 68%, compact 6-column table, sticky header,
            internal scroll, row click selects (never navigates). Status
            tabs + search live inside this panel, under its title row. */}
        <div className="card orders-workspace-panel">
          <div className="orders-panel-header">
            <div className="orders-panel-title">
              <h3>All Estimates</h3>
              <div className="orders-panel-tabs">
                {ESTIMATE_STATUS_TABS.map((t) => (
                  <button
                    key={t.label} type="button"
                    className={`orders-panel-tab ${statusFilter === t.value ? 'active' : ''}`}
                    onClick={() => handleStatusTab(t.value)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
            <span className="home-card-caption">{totalCount} total</span>
          </div>
          <form
            className="page-search"
            onSubmit={handleSearch}
            style={{ maxWidth: 'none', flexWrap: 'wrap', padding: 'var(--space-3) var(--space-4)', margin: 0, borderBottom: '1px solid var(--border-subtle)' }}
          >
            <input
              type="text" placeholder="Search by Estimate ID or client name..." value={search}
              onChange={(e) => setSearch(e.target.value)} className="form-input"
            />
            <button type="submit" className="btn-secondary">Search</button>
          </form>
          <div className="orders-table-scroll">
            {loadError ? (
              <div className="simple-chart-empty">
                Failed to load estimates. <button className="btn-link" onClick={() => load(activeFilters(), page)}>Retry</button>
              </div>
            ) : pageLoading ? (
              <div className="simple-chart-empty">Loading estimates...</div>
            ) : estimateRows.length === 0 ? (
              <div className="simple-chart-empty">
                No estimates yet.
                {isPrivileged && <><br /><button className="btn-link" onClick={openNewEstimateModal}>Create your first estimate</button></>}
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Estimate ID</th><th>Client</th><th>Estimate Date</th>
                    <th>Valid Until</th><th>Value</th><th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {estimateRows.map((row) => (
                    <tr
                      key={row.id}
                      className={`clickable ${row.id === selectedEstimateId ? 'orders-row-selected' : ''}`}
                      tabIndex={0}
                      role="button"
                      onClick={() => handleSelectEstimate(row.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelectEstimate(row.id); } }}
                    >
                      <td>{row.estimate_code}</td>
                      <td>{row.client?.name || '-'}</td>
                      <td>{new Date(row.created_at).toLocaleDateString()}</td>
                      <td>{row.valid_until ? new Date(row.valid_until).toLocaleDateString() : '-'}</td>
                      <td>{row.total_cost != null ? formatCurrency(row.total_cost) : 'Restricted'}</td>
                      <td><span className={`status-badge ${statusClass(row.status)}`}>{row.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="orders-panel-footer">
            <span>{estimateRows.length ? `Showing ${offsetStart + 1}-${offsetStart + estimateRows.length} of ${totalCount}` : `${totalCount} estimates`}</span>
            {totalCount > PAGE_SIZE && (
              <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />
            )}
          </div>
        </div>

        {/* Estimate Details - 32%, three fixed/scroll/fixed zones. */}
        <div className="card orders-workspace-panel">
          <div className="orders-panel-header">
            <div className="orders-panel-title"><h3>Estimate Details</h3></div>
            {selected && <button className="btn-link" onClick={() => navigate(`/estimates/${selected.id}`)}>Full Detail</button>}
          </div>
          {!selected ? (
            <div className="order-detail-empty">
              {detailLoading ? 'Loading...' : 'Select an estimate from the list to see its details.'}
            </div>
          ) : (
            <>
              <div className="order-detail-top">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <h3 style={{ margin: 0 }}>{selected.estimate_code}</h3>
                  <button type="button" className="order-detail-icon-btn" title="Print" onClick={() => window.print()}>
                    <PrinterIcon />
                  </button>
                </div>
                <div className="order-detail-top-meta" style={{ marginTop: 6 }}>
                  <span className={`status-badge status-badge-dot ${statusClass(selected.status)}`}>{selected.status}</span>
                  {selected.business_id && <span className="business-id-badge">{selected.business_id}</span>}
                  {isPrivileged && (
                    <button className="btn-link" onClick={() => setEditingEstimate(selected)}>Edit</button>
                  )}
                </div>
                {selected.client && (
                  <div className="order-detail-client">
                    {selected.client.name}{selected.client.phone ? ` - ${selected.client.phone}` : ''}
                  </div>
                )}
              </div>

              <div className="order-detail-scroll">
                <div>
                  <div className="order-detail-section-label">Client</div>
                  {selected.client ? (
                    <>
                      <div className="order-detail-row"><span>Name</span><button type="button" className="btn-link" onClick={() => navigate(`/clients/${selected.client.id}`)}>{selected.client.name}</button></div>
                      {selected.client.contact_person && <div className="order-detail-row"><span>Contact Person</span><strong>{selected.client.contact_person}</strong></div>}
                      {selected.client.phone && <div className="order-detail-row"><span>Phone</span><strong>{selected.client.phone}</strong></div>}
                      {selected.client.email && <div className="order-detail-row"><span>Email</span><strong>{selected.client.email}</strong></div>}
                    </>
                  ) : <div className="order-detail-row"><span>No client on file.</span></div>}
                </div>

                <div>
                  <div className="order-detail-section-label">Pricing &amp; Tax</div>
                  {isPrivileged && selected.summary.subtotal != null && (
                    <div className="order-detail-row"><span>Subtotal</span><strong>{formatCurrency(selected.summary.subtotal)}</strong></div>
                  )}
                  {isPrivileged && selected.summary.discount != null && (
                    <div className="order-detail-row"><span>Discount</span><strong>{formatCurrency(selected.summary.discount)}</strong></div>
                  )}
                  {selected.summary.tax_percent != null && (
                    <div className="order-detail-row"><span>Tax</span><strong>{selected.summary.tax_percent}%{isPrivileged && selected.summary.tax_amount != null ? ` (${formatCurrency(selected.summary.tax_amount)})` : ''}</strong></div>
                  )}
                  {isPrivileged && selected.summary.total_cost != null && (
                    <div className="order-detail-row"><span>Total</span><strong>{formatCurrency(selected.summary.total_cost)}</strong></div>
                  )}
                </div>

                {selected.line_items?.length > 0 && (
                  <div>
                    <div className="order-detail-section-label">Line Items ({selected.line_items.length})</div>
                    {selected.line_items.map((item) => (
                      <div className="order-detail-item-row" key={item.id}>
                        <span>{item.description}</span>
                        <span>{item.quantity} {item.unit || ''}{isPrivileged && item.amount != null ? ` - ${formatCurrency(item.amount)}` : ''}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div>
                  <div className="order-detail-section-label">Terms &amp; Validity</div>
                  <div className="order-detail-row"><span>Valid Until</span><strong>{selected.valid_until ? new Date(selected.valid_until).toLocaleDateString() : 'Not set'}</strong></div>
                  {selected.description && <div className="order-detail-row"><span>{selected.description}</span></div>}
                </div>

                <div>
                  <div className="order-detail-section-label">Conversion Status</div>
                  {selected.conversion?.order_id ? (
                    <div className="order-detail-item-row" onClick={() => navigate(`/orders/${selected.conversion.order_id}`)} style={{ cursor: 'pointer' }}>
                      <span>Converted to Order</span>
                      <span>{selected.conversion.order_code}</span>
                    </div>
                  ) : (
                    <div className="order-detail-row"><span>Not yet converted ({selected.status})</span></div>
                  )}
                </div>

                <div>
                  <div className="order-detail-section-label">Documents / PDF</div>
                  <div className="order-detail-row">
                    <a href={reportsAPI.downloadUrl(`estimates/${selected.id}/quote.pdf`)} target="_blank" rel="noreferrer">View / Download Quote PDF</a>
                  </div>
                </div>

                {selected.activity?.length > 0 && (
                  <div>
                    <div className="order-detail-section-label">Activity</div>
                    {selected.activity.map((a, i) => (
                      <div className="order-detail-comment" key={i}>
                        <strong>{a.type}</strong> - {a.text}
                      </div>
                    ))}
                  </div>
                )}

                {selected.remarks && (
                  <div>
                    <div className="order-detail-section-label">Notes</div>
                    <div className="order-detail-row"><span>{selected.remarks}</span></div>
                  </div>
                )}
              </div>

              <div className="order-detail-bottom">
                {isPrivileged && <button className="btn-secondary" style={{ flex: 1 }} onClick={() => setEditingEstimate(selected)}>Edit Estimate</button>}
                <a className="btn-secondary" style={{ flex: 1, textAlign: 'center' }} href={reportsAPI.downloadUrl(`estimates/${selected.id}/quote.pdf`)} target="_blank" rel="noreferrer">View / Download PDF</a>
                {selected.conversion?.can_convert && (
                  <button className="btn-primary" style={{ flex: 1 }} onClick={() => setShowConvert(true)}>Convert to Order</button>
                )}
                {isPrivileged && !selected.conversion?.order_id && (
                  <button className="btn-primary" style={{ flex: 1 }} onClick={() => setShowSendEmail(true)}>Send to Client</button>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      <Modal isOpen={showAdd} title="New Estimate" size="wide" onClose={() => { setShowAdd(false); setSelectedClientId(''); setLineItems([emptyRow()]); }}>
        <div className="form-group">
          <label className="form-label">Client *</label>
          <select className="form-input" value={selectedClientId} onChange={(e) => setSelectedClientId(e.target.value)}>
            <option value="">{clientsLoading ? 'Loading clients...' : 'Select a client...'}</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <h4 style={{ marginBottom: 8 }}>Line Items</h4>
        <LineItemEditor items={lineItems} onChange={setLineItems} clientId={selectedClientId} />
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Create Estimate" />
      </Modal>

      <Modal isOpen={!!editingEstimate} title={`Edit ${editingEstimate?.estimate_code || ''}`} onClose={() => setEditingEstimate(null)}>
        {editingEstimate && (
          <Form
            fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
            initialValues={{
              material_cost: editingEstimate.summary?.material_cost, labor_cost: editingEstimate.summary?.labor_cost,
              tax_percent: editingEstimate.summary?.tax_percent, status: editingEstimate.status,
              valid_until: editingEstimate.valid_until ? editingEstimate.valid_until.slice(0, 10) : '',
              remarks: editingEstimate.remarks || '',
            }}
          />
        )}
      </Modal>

      <Modal isOpen={showConvert} title="Convert to Order" onClose={() => { setShowConvert(false); setConvertError(''); }}>
        {convertError && <Alert type="error" message={convertError} onClose={() => setConvertError('')} />}
        {selected && (
          <>
            <p style={{ marginBottom: 16, color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
              This creates a new order for {selected.client?.name || 'this client'} using this estimate's line items
              {isPrivileged && selected.summary.total_cost != null ? ` and total (${formatCurrency(selected.summary.total_cost)})` : ''}. The estimate will be linked to the new order.
            </p>
            <Form
              fields={[
                { name: 'order_date', label: 'Order Date', type: 'date', required: true },
                { name: 'advance', label: 'Advance Received', type: 'number' },
              ]}
              onSubmit={handleConvertToOrder} loading={converting} submitText="Create Order"
              initialValues={{ order_date: today() }}
            />
          </>
        )}
      </Modal>

      {selected && (
        <SendEmailModal
          isOpen={showSendEmail}
          title={`Send Estimate ${selected.estimate_code}`}
          previewFn={() => estimatesAPI.emailPreview(selected.id)}
          sendFn={(data) => estimatesAPI.sendEmail(selected.id, data)}
          onClose={() => setShowSendEmail(false)}
          onSent={(message) => { setShowSendEmail(false); setSuccess(message); }}
        />
      )}
    </div>
  );
}

// --- OrdersPage.jsx ---
const PAGE_SIZE = 25;

const STAGE_OPTIONS = ['Enquiry', 'Designing', 'Approved', 'Material Purchase', 'Cutting', 'Edge Banding',
  'Assembly', 'Painting', 'Ready for Dispatch', 'Installation', 'Completed', 'On Hold', 'Cancelled']
  .map((s) => ({ value: s, label: s }));
const SIMPLE_STATUS_OPTIONS = ['Pending', 'In Progress', 'Completed'].map((s) => ({ value: s, label: s }));
const PRIORITY_OPTIONS = ['Low', 'Medium', 'High', 'Urgent'].map((s) => ({ value: s, label: s }));

function OrdersPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  // workspace holds the one bounded GET /api/orders/workspace response:
  // { summary, orders: {items,total_count,limit,offset}, selected_order }.
  // Nothing here is fetched/derived a second time client-side.
  const [workspace, setWorkspace] = useState(null);
  const [selectedOrderId, setSelectedOrderId] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  // clients is only needed for the New Order modal's client picker, so
  // (unlike the previous implementation) it is fetched lazily when that
  // modal actually opens, not on every page load/filter change.
  const [clients, setClients] = useState([]);
  const [clientsLoading, setClientsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  // Server-side search (order code/business ID/client name/client
  // code) - matches GET /api/orders/workspace's new `search` param, same
  // pattern Clients/Estimates already use: DB-filtered, never a
  // frontend/client-side filter over a fully-loaded page.
  const [search, setSearch] = useState('');
  const location = useLocation();
  const [sortByRisk, setSortByRisk] = useState(!!location.state?.sortByRisk);
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [orderLineItems, setOrderLineItems] = useState([emptyRow()]);
  const [selectedClientId, setSelectedClientId] = useState('');
  const [statusOrder, setStatusOrder] = useState(null);
  // When true, the Update Status modal is being used as "Close Order":
  // same statusOrder/handleStatusUpdate/guardrail flow, just with the
  // form's initial values pre-set toward Completed instead of the
  // order's current stage. statusOrder itself always holds the order's
  // real current field values (handleStatusUpdate's guardrail check
  // depends on that), so this never touches the underlying update logic.
  const [closePreset, setClosePreset] = useState(false);
  const [editingOrder, setEditingOrder] = useState(null);
  // Balance-Before-Dispatch Guardrail: holds the
  // pending status-update payload and the balance figure explaining why
  // it's paused, while the person is asked for an explicit override
  // reason. Null means no guardrail prompt is showing.
  const [dispatchGuardrail, setDispatchGuardrail] = useState(null);
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);
  const [overrideError, setOverrideError] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const activeFilters = () => {
    const params = {};
    if (statusFilter) params.status = statusFilter;
    if (priorityFilter) params.priority = priorityFilter;
    if (overdueOnly) params.overdue_only = true;
    if (search) params.search = search;
    if (sortByRisk) params.sort = 'risk';
    return params;
  };

  // activeFilters reads statusFilter/priorityFilter/overdueOnly/sortByRisk
  // directly, so its identity legitimately changes on every render. The
  // mount effect below must call the *current* filters at the moment it
  // runs, but must NOT re-run when filters change (every filter change
  // already triggers its own explicit load(...) call via applyFilters /
  // toggleSortByRisk / handleFilterChange / etc.) - re-running here would
  // duplicate those requests. A ref keeps the effect's dependency array
  // free of activeFilters' churn while still reading its latest version.
  const activeFiltersRef = useRef(activeFilters);
  activeFiltersRef.current = activeFilters;

  // Same treatment for selectedOrderId - load() (full page/filter load)
  // carries whatever order is currently selected so the detail panel
  // stays in sync with the list, but selecting a row must not force
  // load()'s identity to change (that would re-trigger effects keyed on
  // it for an unrelated reason).
  const selectedOrderIdRef = useRef(selectedOrderId);
  selectedOrderIdRef.current = selectedOrderId;

  // load() reads no component state directly - only stable setters, the
  // module-level PAGE_SIZE constant, the ordersAPI import, and the refs
  // above - so its dependency array is genuinely empty. One bounded
  // /api/orders/workspace request replaces the previous
  // ordersAPI.list() + clientsAPI.list() + per-row clients.find(...) chain.
  const load = useCallback((filterParams, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    setPageLoading(true);
    setLoadError(false);
    ordersAPI.workspace({
      ...filterParams, limit: PAGE_SIZE, offset,
      selected_order_id: selectedOrderIdRef.current || undefined,
    }).then((res) => {
      setWorkspace(res.data);
      if (res.data.selected_order) setSelectedOrderId(res.data.selected_order.id);
    }).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
  }, []);

  useEffect(() => {
    load(activeFiltersRef.current());
  }, [load]);

  // If the page loads (or a filter change reloads) with nothing selected
  // yet but the list isn't empty, default the detail panel to the first
  // row instead of leaving it empty - a real order's data, not a mock.
  useEffect(() => {
    if (!pageLoading && workspace && !selectedOrderId && workspace.orders?.items?.length) {
      handleSelectOrder(workspace.orders.items[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageLoading, workspace]);

  const handleSelectOrder = (orderId) => {
    if (orderId === selectedOrderId && workspace?.selected_order) return;
    setSelectedOrderId(orderId);
    setDetailLoading(true);
    ordersAPI.workspace({ selected_order_id: orderId, detail_only: true }).then((res) => {
      setWorkspace((prev) => (prev ? { ...prev, selected_order: res.data.selected_order } : prev));
    }).catch(() => {}).finally(() => setDetailLoading(false));
  };

  const openNewOrderModal = () => {
    setShowAdd(true);
    if (!clients.length) {
      setClientsLoading(true);
      clientsAPI.list().then((res) => setClients(res.data)).catch(() => {}).finally(() => setClientsLoading(false));
    }
  };

  const applyFilters = (nextStatus, nextPriority, nextOverdue, nextSearch = search) => {
    const params = {};
    if (nextStatus) params.status = nextStatus;
    if (nextPriority) params.priority = nextPriority;
    if (nextOverdue) params.overdue_only = true;
    if (nextSearch) params.search = nextSearch;
    if (sortByRisk) params.sort = 'risk';
    setPage(1);
    load(params, 1);
  };

  const toggleSortByRisk = () => {
    const next = !sortByRisk;
    setSortByRisk(next);
    const params = activeFilters();
    if (next) params.sort = 'risk';
    else delete params.sort;
    setPage(1);
    load(params, 1);
  };

  const handleFilterChange = (e) => {
    const value = e.target.value;
    setStatusFilter(value);
    applyFilters(value, priorityFilter, overdueOnly);
  };

  const handlePriorityFilterChange = (e) => {
    const value = e.target.value;
    setPriorityFilter(value);
    applyFilters(statusFilter, value, overdueOnly);
  };

  const handleOverdueChange = (e) => {
    const checked = e.target.checked;
    setOverdueOnly(checked);
    applyFilters(statusFilter, priorityFilter, checked);
  };

  const handleSearch = (e) => {
    e.preventDefault();
    applyFilters(statusFilter, priorityFilter, overdueOnly, search);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(activeFilters(), pageNum);
  };

  // Mirrors the Clients page's own exportUrl() exactly - "Export
  // Orders" previously always downloaded every order regardless of the
  // current stage/priority/balance filters, unlike Export Clients
  // (which already respected its filters). Now the export matches what's
  // on screen here too. sortByRisk is deliberately left out - it only
  // changes row ORDER, not which rows are included, and export_orders
  // doesn't (and doesn't need to) support a sort param.
  const exportUrl = () => {
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);
    if (priorityFilter) params.set('priority', priorityFilter);
    if (overdueOnly) params.set('overdue_only', 'true');
    const qs = params.toString();
    return reportsAPI.downloadUrl(`orders.xlsx${qs ? `?${qs}` : ''}`);
  };

  const handleCreate = async (formData) => {
    if (!selectedClientId) {
      setError('Please select a client first.');
      return;
    }
    const invalidRow = orderLineItems.find((row) => row.description.trim() && quantityViolatesWholeUnitRule(row.quantity, row.unit));
    if (invalidRow) {
      setError(`"${invalidRow.description}" - ${invalidRow.unit} must be a whole number, not a fractional quantity.`);
      return;
    }
    setLoading(true);
    setError('');
    const validItems = orderLineItems
      .filter((row) => row.description.trim())
      .map((row) => ({
        description: row.description, category: row.category || null,
        quantity: row.quantity || '1', unit: row.unit || null, rate: row.rate || '0',
        product_id: row.product_id ? Number(row.product_id) : null,
      }));
    try {
      await ordersAPI.create({
        ...formData,
        client_id: Number(selectedClientId),
        order_date: new Date(formData.order_date).toISOString(),
        delivery_date: formData.delivery_date ? new Date(formData.delivery_date).toISOString() : null,
        order_value: formData.order_value || '0',
        advance: formData.advance || '0',
        items: validItems,
      });
      setShowAdd(false);
      setOrderLineItems([emptyRow()]);
      setSelectedClientId('');
      setSuccess('Order created.');
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create order');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusUpdate = async (formData) => {
    // Balance-Before-Dispatch Guardrail: only
    // relevant when this update would actually move delivery_status to
    // "Completed" for the first time. Precheck via the read-only
    // dispatch-check endpoint so the person sees WHY before they hit an
    // error, rather than only finding out after submitting. If the
    // precheck itself fails for an unrelated reason (network, etc.),
    // fall through to the normal update - the backend's own guardrail
    // is still the real, authoritative enforcement either way.
    const movingToCompleted = formData.delivery_status === 'Completed' && statusOrder.delivery_status !== 'Completed';
    if (movingToCompleted) {
      try {
        const check = await ordersAPI.dispatchCheck(statusOrder.id);
        if (!check.data.ready_to_dispatch) {
          setDispatchGuardrail({
            formData, orderId: statusOrder.id, orderCode: check.data.order_code,
            balance: check.data.outstanding_balance, reason: check.data.reason,
          });
          return;
        }
      } catch (err) {
        // Precheck failed for an unrelated reason - proceed and let the
        // authoritative server-side check on the real update decide.
      }
    }
    setLoading(true);
    setError('');
    try {
      await ordersAPI.update(statusOrder.id, {
        project_status: formData.project_status,
        design_status: formData.design_status,
        execution_status: formData.execution_status,
        delivery_status: formData.delivery_status,
        progress_percent: Number(formData.progress_percent),
      });
      setStatusOrder(null);
      setClosePreset(false);
      setSuccess('Order updated.');
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update status');
    } finally {
      setLoading(false);
    }
  };

  const handleDispatchOverrideSubmit = async (overrideFormData) => {
    if (!overrideFormData.override_reason || !overrideFormData.override_reason.trim()) {
      setOverrideError('A reason is required to dispatch this order with an outstanding balance.');
      return;
    }
    setOverrideSubmitting(true);
    setOverrideError('');
    try {
      await ordersAPI.update(dispatchGuardrail.orderId, {
        project_status: dispatchGuardrail.formData.project_status,
        design_status: dispatchGuardrail.formData.design_status,
        execution_status: dispatchGuardrail.formData.execution_status,
        delivery_status: dispatchGuardrail.formData.delivery_status,
        progress_percent: Number(dispatchGuardrail.formData.progress_percent),
        override_balance_guardrail: true,
        override_reason: overrideFormData.override_reason.trim(),
      });
      setDispatchGuardrail(null);
      setStatusOrder(null);
      setClosePreset(false);
      setSuccess('Order marked delivered - outstanding balance override recorded.');
      load(activeFilters(), page);
    } catch (err) {
      setOverrideError(err.response?.data?.detail || 'Failed to record the override.');
    } finally {
      setOverrideSubmitting(false);
    }
  };

  const handleDetailsUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await ordersAPI.update(editingOrder.id, {
        project_type: formData.project_type,
        order_value: formData.order_value,
        delivery_date: formData.delivery_date ? new Date(formData.delivery_date).toISOString() : null,
        priority: formData.priority,
        supervisor: formData.supervisor,
        site_address: formData.site_address,
        remarks: formData.remarks,
      });
      setEditingOrder(null);
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update order');
    } finally {
      setLoading(false);
    }
  };

  // Compact detail object for the "Edit Details" form, built from the
  // workspace's selected_order shape (status/design_status/... use
  // different key names there than the Order-list row the old modal used
  // to receive) - same fields the existing Form/handleDetailsUpdate
  // already expect, just sourced from the new response.
  const editableDetails = (order) => order && {
    id: order.id, order_code: order.order_code, project_type: order.project_type,
    order_value: order.order_value, delivery_date: order.delivery_date, priority: order.priority,
    supervisor: order.supervisor, site_address: order.site_address, remarks: order.remarks,
  };

  // "Update Order" and "Close Order" (Zone 3) both open the exact same
  // existing Update Status modal/handleStatusUpdate/guardrail flow - no
  // second implementation. statusOrder always carries the order's real
  // current field values (handleStatusUpdate's guardrail check compares
  // against statusOrder.delivery_status); closePreset only changes what
  // the form's initialValues show, never the update logic itself.
  const openStatusModal = (preset) => {
    const sel = workspace?.selected_order;
    if (!sel) return;
    setStatusOrder({
      id: sel.id, order_code: sel.order_code, project_status: sel.status,
      design_status: sel.design_status, execution_status: sel.execution_status,
      delivery_status: sel.delivery_status, progress_percent: sel.progress_percent,
    });
    setClosePreset(preset);
  };

  const createFields = [
    { name: 'project_type', label: 'Project Type' },
    { name: 'order_date', label: 'Order Date', type: 'date', required: true },
    { name: 'delivery_date', label: 'Delivery Date', type: 'date', advanced: true },
    { name: 'order_value', label: 'Order Value', type: 'number', advanced: true,
      hint: 'Only used if no line items are added below - line items compute this automatically.' },
    { name: 'discount', label: 'Discount (amount)', type: 'number', advanced: true },
    { name: 'tax_percent', label: 'GST %', type: 'number', advanced: true },
    { name: 'advance', label: 'Advance', type: 'number', advanced: true },
    { name: 'priority', label: 'Priority', type: 'select', advanced: true, options: PRIORITY_OPTIONS },
    { name: 'supervisor', label: 'Supervisor', advanced: true },
    { name: 'site_address', label: 'Site Address', type: 'textarea', advanced: true },
  ];

  const detailsFields = [
    { name: 'project_type', label: 'Project Type' },
    { name: 'order_value', label: 'Order Value', type: 'number', required: true },
    { name: 'delivery_date', label: 'Delivery Date', type: 'date' },
    { name: 'priority', label: 'Priority', type: 'select', options: PRIORITY_OPTIONS },
    { name: 'supervisor', label: 'Supervisor' },
    { name: 'site_address', label: 'Site Address', type: 'textarea' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  const summary = workspace?.summary || null;
  const orderRows = workspace?.orders?.items || [];
  const totalCount = workspace?.orders?.total_count || 0;
  const offsetStart = workspace?.orders?.offset ?? (page - 1) * PAGE_SIZE;
  const selected = workspace?.selected_order || null;

  const topStages = summary?.order_pipeline?.stage_breakdown
    ? [...summary.order_pipeline.stage_breakdown].filter((s) => s.count > 0).sort((a, b) => b.count - a.count).slice(0, 3)
    : [];

  // All 5 KPI chips come straight from workspace.summary - nothing
  // invented client-side. Payment Due is a financial aggregate, so (like
  // every other financial figure here) it's simply absent for a
  // non-master viewer rather than shown as 0/fabricated.
  const kpiItems = summary ? [
    { label: 'Active Orders', value: summary.active_orders, icon: OrderIcon },
    { label: 'Materials at Risk', value: summary.materials_at_risk, icon: MaterialIcon, tone: summary.materials_at_risk > 0 ? 'warning' : 'default' },
    { label: 'Deliveries Due', value: summary.deliveries_due, icon: TruckIcon, tone: summary.deliveries_due > 0 ? 'warning' : 'default' },
    ...(summary.payment_due != null ? [{ label: 'Payment Due', value: summary.payment_due, icon: PaymentIcon, tone: summary.payment_due > 0 ? 'warning' : 'default' }] : []),
    { label: 'Active Employees', value: summary.active_employees, icon: EmployeeIcon },
  ] : [];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>
            Orders
            {summary && <span className="home-card-chip" style={{ marginLeft: 10, verticalAlign: 'middle' }}>{summary.active_orders} Active Orders</span>}
          </h1>
          <p className="page-summary">Track every order from confirmation through delivery and payment.</p>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {summary && <KpiStrip items={kpiItems} />}

      <div className="orders-workspace-toolbar">
        {isPrivileged && <button className="btn-primary" onClick={openNewOrderModal}>+ New Order</button>}
        <a className="btn-secondary" href={exportUrl()} target="_blank" rel="noreferrer">Export Orders</a>
        {isPrivileged && <button className="btn-secondary" onClick={() => navigate('/orders/import')}>Import Orders</button>}
      </div>

      <div className="orders-summary-cards">
        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Orders Overview</span>
            {summary && <span className="home-card-chip">{summary.active_orders} Active</span>}
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.orders_overview.pipeline_count}</span>
                <span className="orders-card-hero-caption">Total Orders</span>
                {isPrivileged && summary.orders_overview.total_order_value != null && (
                  <span className="orders-card-hero-side">Total Value {formatCurrency(summary.orders_overview.total_order_value)}</span>
                )}
              </div>
              <div className="orders-card-footer-row">
                <span>Order Pipeline</span>
                <strong>{summary.order_pipeline.active_orders} Active</strong>
              </div>
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Order Pipeline</span>
            {summary && <span className="home-card-chip">{summary.order_pipeline.active_orders} Active</span>}
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.order_pipeline.active_orders}</span>
                <span className="orders-card-hero-caption">Active Pipeline</span>
                {topStages.length > 0 && (
                  <span className="orders-card-hero-side">{topStages.map((s) => `${s.count} ${s.status}`).join(' • ')}</span>
                )}
              </div>
              {topStages[0] ? (
                <div className="orders-card-footer-row">
                  <span>{topStages[0].status}</span>
                  <strong>{topStages[0].count} Orders</strong>
                </div>
              ) : (
                <div className="orders-card-footer-row"><span>No orders yet.</span></div>
              )}
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Delivery &amp; Risk</span>
            {summary?.delivery_risk?.on_track_percent != null && (
              <span className="home-card-caption">{summary.delivery_risk.on_track_percent}% on track</span>
            )}
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.delivery_risk.on_track_percent}%</span>
                <span className="orders-card-hero-caption">On Track</span>
                <span className="orders-card-hero-side">
                  {summary.delivery_risk.critical_count} Crit &bull; {summary.delivery_risk.at_risk_count} Risk &bull; {summary.delivery_risk.watch_count} Watch
                </span>
              </div>
              <div className="order-health-chips">
                <div className="order-health-chip order-health-danger">
                  <span className="order-health-count">{summary.delivery_risk.critical_count}</span>
                  <span className="order-health-label">Critical</span>
                </div>
                <div className="order-health-chip order-health-warning">
                  <span className="order-health-count">{summary.delivery_risk.at_risk_count}</span>
                  <span className="order-health-label">At Risk</span>
                </div>
                <div className="order-health-chip order-health-success">
                  <span className="order-health-count">{summary.delivery_risk.watch_count}</span>
                  <span className="order-health-label">Watch</span>
                </div>
              </div>
              <div className="orders-card-footer-row">
                <span>Deliveries Due</span>
                <strong>{summary.deliveries_due}</strong>
              </div>
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Payment Overview</span>
            {isPrivileged && summary?.payment_overview && (
              <span className="home-card-chip">{formatCurrency(summary.payment_due)} Due</span>
            )}
          </div>
          {isPrivileged ? (
            summary?.payment_overview ? (
              <div className="orders-card-body">
                <div className="orders-card-hero">
                  <span className="orders-card-hero-number">{formatCurrency(summary.payment_overview.total_received)}</span>
                  <span className="orders-card-hero-caption">Received</span>
                </div>
                <div className="order-detail-split-bar">
                  <div
                    className="order-detail-split-bar-received"
                    style={{ width: `${summary.payment_overview.total_received + summary.payment_overview.outstanding_balance > 0 ? (100 * summary.payment_overview.total_received / (summary.payment_overview.total_received + summary.payment_overview.outstanding_balance)) : 0}%` }}
                  />
                  <div
                    className="order-detail-split-bar-pending"
                    style={{ width: `${summary.payment_overview.total_received + summary.payment_overview.outstanding_balance > 0 ? (100 * summary.payment_overview.outstanding_balance / (summary.payment_overview.total_received + summary.payment_overview.outstanding_balance)) : 0}%` }}
                  />
                </div>
                <div className="orders-card-footer-row">
                  <span>Outstanding</span>
                  <strong>{formatCurrency(summary.payment_overview.outstanding_balance)}</strong>
                </div>
              </div>
            ) : <div className="simple-chart-empty">Loading...</div>
          ) : (
            <div className="simple-chart-empty">Restricted to Master accounts.</div>
          )}
        </Card>
      </div>

      <div className="orders-workspace-grid">
        {/* All Orders - 68%, compact 6-column table, sticky header,
            internal scroll, row click selects (never navigates). The
            existing filter/search controls (unchanged - same state,
            handlers and options as before) now live inside this panel,
            directly under its title row, instead of as a separate
            full-width section above the workspace grid. The two boolean
            filters (overdue-only, sort-by-risk) render as pill toggles
            instead of checkboxes - same state/handlers, just restyled;
            Stage/Priority stay selects since each has too many real
            values for a tab row, but are visually restyled to match. */}
        <div className="card orders-workspace-panel">
          <div className="orders-panel-header">
            <div className="orders-panel-title">
              <h3>All Orders</h3>
              <div className="orders-panel-tabs">
                <button type="button" className={`orders-panel-tab ${!overdueOnly ? 'active' : ''}`} onClick={() => overdueOnly && handleOverdueChange({ target: { checked: false } })}>All</button>
                <button type="button" className={`orders-panel-tab ${overdueOnly ? 'active' : ''}`} onClick={() => !overdueOnly && handleOverdueChange({ target: { checked: true } })}>Balance 30+ Days</button>
                <button type="button" className={`orders-panel-tab ${sortByRisk ? 'active' : ''}`} onClick={toggleSortByRisk}>Sort by Risk</button>
              </div>
            </div>
            <span className="home-card-caption">{totalCount} total</span>
          </div>
          <form
            className="page-search"
            onSubmit={handleSearch}
            style={{ maxWidth: 'none', flexWrap: 'wrap', padding: 'var(--space-3) var(--space-4)', margin: 0, borderBottom: '1px solid var(--border-subtle)' }}
          >
            <input
              type="text" placeholder="Search by Order ID or client name..." value={search}
              onChange={(e) => setSearch(e.target.value)} className="form-input"
            />
            <button type="submit" className="btn-secondary">Search</button>
            <select className="form-input" style={{ borderRadius: 100 }} value={statusFilter} onChange={handleFilterChange}>
              <option value="">All Stages</option>
              {STAGE_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <select className="form-input" style={{ borderRadius: 100 }} value={priorityFilter} onChange={handlePriorityFilterChange}>
              <option value="">All Priorities</option>
              {PRIORITY_OPTIONS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </form>
          <div className="orders-table-scroll">
            {loadError ? (
              <div className="simple-chart-empty">
                Failed to load orders. <button className="btn-link" onClick={() => load(activeFilters(), page)}>Retry</button>
              </div>
            ) : pageLoading ? (
              <div className="simple-chart-empty">Loading orders...</div>
            ) : orderRows.length === 0 ? (
              <div className="simple-chart-empty">
                No orders yet.
                {isPrivileged && <><br /><button className="btn-link" onClick={openNewOrderModal}>Create your first order</button></>}
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Order ID</th><th>Client</th><th>Project Type</th>
                    <th>Completion %</th><th>Order Value</th><th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {orderRows.map((row) => (
                    <tr
                      key={row.id}
                      className={`clickable ${row.id === selectedOrderId ? 'orders-row-selected' : ''}`}
                      tabIndex={0}
                      role="button"
                      onClick={() => handleSelectOrder(row.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelectOrder(row.id); } }}
                    >
                      <td>{row.order_code}</td>
                      <td>{row.client?.name || '-'}</td>
                      <td>{row.project_type || '-'}</td>
                      <td>{row.progress_percent != null ? `${row.progress_percent}%` : '-'}</td>
                      <td>{row.order_value != null ? formatCurrency(row.order_value) : 'Restricted'}</td>
                      <td>
                        {row.needs_attention && (
                          <span
                            title={row.attention_risk_level}
                            style={{
                              display: 'inline-block', width: 7, height: 7, borderRadius: '50%', marginRight: 6,
                              background: row.attention_risk_level === 'CRITICAL' ? 'var(--danger)' : 'var(--warning)',
                            }}
                          />
                        )}
                        <span className={`status-badge ${statusClass(row.status)}`}>{row.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="orders-panel-footer">
            <span>{orderRows.length ? `Showing ${offsetStart + 1}-${offsetStart + orderRows.length} of ${totalCount}` : `${totalCount} orders`}</span>
            {totalCount > PAGE_SIZE && (
              <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />
            )}
          </div>
        </div>

        {/* Order Details - 32%, three fixed/scroll/fixed zones. */}
        <div className="card orders-workspace-panel">
          <div className="orders-panel-header">
            <div className="orders-panel-title"><h3>Order Details</h3></div>
            {selected && <button className="btn-link" onClick={() => navigate(`/orders/${selected.id}`)}>Full Detail</button>}
          </div>
          {!selected ? (
            <div className="order-detail-empty">
              {detailLoading ? 'Loading...' : 'Select an order from the list to see its details.'}
            </div>
          ) : (
            <>
              <div className="order-detail-top">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <h3 style={{ margin: 0 }}>{selected.order_code}</h3>
                  <button type="button" className="order-detail-icon-btn" title="Print" onClick={() => window.print()}>
                    <PrinterIcon />
                  </button>
                </div>
                <div className="order-detail-top-meta" style={{ marginTop: 6 }}>
                  <span className={`status-badge status-badge-dot ${statusClass(selected.status)}`}>{selected.status}</span>
                  {selected.priority && (
                    <span className={`status-badge ${statusClass(selected.priority === 'Urgent' || selected.priority === 'High' ? 'overdue' : selected.priority)}`}>{selected.priority}</span>
                  )}
                  {selected.client?.client_type === 'Business' && (
                    <span className="home-card-chip">Business / Premium</span>
                  )}
                  {isPrivileged && (
                    <button className="btn-link" onClick={() => setEditingOrder(editableDetails(selected))}>Edit Details</button>
                  )}
                </div>
                {selected.client && (
                  <div className="order-detail-client">
                    {selected.client.name}{selected.client.phone ? ` - ${selected.client.phone}` : ''}
                  </div>
                )}
              </div>

              <div className="order-detail-scroll">
                <div>
                  <div className="order-detail-section-label">Completion</div>
                  <div className="order-detail-progress-track">
                    <div className="order-detail-progress-fill" style={{ width: `${selected.progress_percent || 0}%` }} />
                  </div>
                  <div className="order-detail-row" style={{ marginTop: 4 }}><span>{selected.progress_percent ?? 0}% complete</span></div>
                </div>

                <div>
                  <div className="order-detail-section-label">Delivery</div>
                  <div className="order-detail-row">
                    <span>Delivery Date</span>
                    <strong>{selected.delivery_date ? new Date(selected.delivery_date).toLocaleDateString() : 'Not set'}</strong>
                  </div>
                  <div className="order-detail-row">
                    <span>Delivery Status</span>
                    <strong>{selected.delivery_status || '-'}</strong>
                  </div>
                </div>

                {isPrivileged && (
                  <div>
                    <div className="order-detail-section-label">Payment</div>
                    <div className="order-detail-row"><span>Order Value</span><strong>{selected.order_value != null ? formatCurrency(selected.order_value) : '-'}</strong></div>
                    {selected.order_value > 0 && (
                      <div className="order-detail-split-bar">
                        <div className="order-detail-split-bar-received" style={{ width: `${Math.min(100, 100 * (selected.total_received || 0) / selected.order_value)}%` }} />
                        <div className="order-detail-split-bar-pending" style={{ width: `${Math.max(0, 100 - (100 * (selected.total_received || 0) / selected.order_value))}%` }} />
                      </div>
                    )}
                    <div className="order-detail-row"><span>Received</span><strong>{selected.total_received != null ? formatCurrency(selected.total_received) : '-'}</strong></div>
                    <div className="order-detail-row"><span>Balance</span><strong>{selected.balance != null ? formatCurrency(selected.balance) : '-'}</strong></div>
                    {selected.payment_status && <div className="order-detail-row"><span>Status</span><strong>{selected.payment_status}</strong></div>}
                  </div>
                )}

                {selected.items?.length > 0 && (
                  <div>
                    <div className="order-detail-section-label">Items ({selected.items.length})</div>
                    {selected.items.map((item) => (
                      <div className="order-detail-item-row" key={item.id}>
                        <span>{item.description}</span>
                        <span>{item.quantity} {item.unit || ''}</span>
                      </div>
                    ))}
                  </div>
                )}

                {selected.risk && (
                  <div>
                    <div className="order-detail-section-label">Risk</div>
                    <div className="order-detail-row"><span>Level</span><strong>{selected.risk.risk_level}</strong></div>
                    {selected.risk.reasons?.map((reason, i) => (
                      <div className="order-detail-row" key={i}><span>{reason}</span></div>
                    ))}
                  </div>
                )}

                {selected.materials?.shortages?.length > 0 && (
                  <div>
                    <div className="order-detail-section-label">Material Shortages</div>
                    {selected.materials.shortages.map((m, i) => (
                      <div className="order-detail-row" key={i}>
                        <span>{m.material_name}</span>
                        <strong>{m.shortage} {m.unit}</strong>
                      </div>
                    ))}
                  </div>
                )}

                {selected.remarks && (
                  <div>
                    <div className="order-detail-section-label">Remarks</div>
                    <div className="order-detail-row"><span>{selected.remarks}</span></div>
                  </div>
                )}

                {selected.comments?.length > 0 && (
                  <div>
                    <div className="order-detail-section-label">Recent Comments</div>
                    {selected.comments.map((c) => (
                      <div className="order-detail-comment" key={c.id}>
                        <strong>{c.author}</strong> - {c.text}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="order-detail-bottom">
                <button className="btn-secondary" style={{ flex: 1 }} onClick={() => openStatusModal(false)}>Update Order</button>
                <button className="btn-primary" style={{ flex: 1 }} onClick={() => openStatusModal(true)}>Close Order</button>
              </div>
            </>
          )}
        </div>
      </div>

      <Modal isOpen={showAdd} title="New Order" size="wide" onClose={() => { setShowAdd(false); setSelectedClientId(''); setOrderLineItems([emptyRow()]); }}>
        <div className="form-group">
          <label className="form-label">Client *</label>
          <select className="form-input" value={selectedClientId} onChange={(e) => setSelectedClientId(e.target.value)}>
            <option value="">{clientsLoading ? 'Loading clients...' : 'Select a client...'}</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <h4 style={{ marginBottom: 8 }}>Order Items</h4>
        <LineItemEditor items={orderLineItems} onChange={setOrderLineItems} clientId={selectedClientId} />
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Create Order" />
      </Modal>

      <Modal isOpen={!!editingOrder} title={`Edit Order - ${editingOrder?.order_code || ''}`} onClose={() => setEditingOrder(null)}>
        {editingOrder && (
          <Form
            fields={detailsFields}
            onSubmit={handleDetailsUpdate}
            loading={loading}
            submitText="Save Changes"
            initialValues={{
              project_type: editingOrder.project_type, order_value: editingOrder.order_value,
              delivery_date: editingOrder.delivery_date ? editingOrder.delivery_date.slice(0, 10) : '',
              priority: editingOrder.priority, supervisor: editingOrder.supervisor,
              site_address: editingOrder.site_address, remarks: editingOrder.remarks,
            }}
          />
        )}
      </Modal>

      <Modal
        isOpen={!!statusOrder}
        title={`${closePreset ? 'Close Order' : 'Update Order'} - ${statusOrder?.order_code || ''}`}
        onClose={() => { setStatusOrder(null); setClosePreset(false); }}
      >
        {statusOrder && (
          <Form
            fields={[
              { name: 'project_status', label: 'Overall Stage', type: 'select', required: true, options: STAGE_OPTIONS },
              { name: 'design_status', label: 'Design Status', type: 'select', required: true, options: SIMPLE_STATUS_OPTIONS },
              { name: 'execution_status', label: 'Execution Status', type: 'select', required: true, options: SIMPLE_STATUS_OPTIONS },
              { name: 'delivery_status', label: 'Delivery Status', type: 'select', required: true, options: SIMPLE_STATUS_OPTIONS },
              { name: 'progress_percent', label: 'Progress %', type: 'number', required: true },
            ]}
            onSubmit={handleStatusUpdate}
            loading={loading}
            submitText={closePreset ? 'Close Order' : 'Update Order'}
            initialValues={{
              project_status: closePreset ? 'Completed' : statusOrder.project_status,
              design_status: closePreset ? 'Completed' : statusOrder.design_status,
              execution_status: closePreset ? 'Completed' : statusOrder.execution_status,
              delivery_status: closePreset ? 'Completed' : statusOrder.delivery_status,
              progress_percent: closePreset ? 100 : statusOrder.progress_percent,
            }}
          />
        )}
      </Modal>

      {/* Balance-Before-Dispatch Guardrail.
          Shown instead of silently applying the update when marking an
          order Delivered/Completed while a balance is still outstanding.
          Cancelling returns to the status form unchanged; confirming
          requires a reason, which is recorded on the order's audit
          trail alongside the override itself. */}
      <Modal
        isOpen={!!dispatchGuardrail}
        title={`Outstanding Balance - ${dispatchGuardrail?.orderCode || ''}`}
        onClose={() => { setDispatchGuardrail(null); setOverrideError(''); }}
      >
        {dispatchGuardrail && (
          <>
            <Alert
              type="error"
              message={dispatchGuardrail.reason || (
                `This order has an outstanding balance of ${formatCurrency(dispatchGuardrail.balance)} and has not been fully paid.`
              )}
              onClose={() => {}}
            />
            {overrideError && <Alert type="error" message={overrideError} onClose={() => setOverrideError('')} />}
            <Form
              fields={[
                { name: 'override_reason', label: 'Reason for dispatching with a balance due', type: 'textarea', required: true },
              ]}
              onSubmit={handleDispatchOverrideSubmit}
              loading={overrideSubmitting}
              submitText="Confirm Dispatch Anyway"
              initialValues={{ override_reason: '' }}
            />
          </>
        )}
      </Modal>
    </div>
  );
}

export { EstimatesPage, OrdersPage };
