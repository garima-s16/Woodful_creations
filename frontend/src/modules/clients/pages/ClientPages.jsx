// Client pages: list/CRUD and Excel import. Combines the former
// ClientsPage.jsx and ClientImportPage.jsx. ClientDetailPage.jsx
// remains separate - the deep-detail destination this compact
// workspace's "Full Detail" link opens, exactly like Orders' own
// /orders/:id relationship to /orders.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { clientDocumentsAPI, clientImportAPI, clientsAPI, ordersAPI, reportsAPI, settingsAPI } from '../../../utils/api';
import { Alert, Card, ConfirmDialog, Form, KpiStrip, Modal, Pagination } from '../../../components/common/UI';
import { formatCurrency, statusClass, today } from '../../../utils/utils';
import { ClientIcon, CheckCircleIcon, AnalyticsIcon, PaymentIcon, ChatIcon, PrinterIcon } from '../../../components/icons';

// --- ClientsPage.jsx ---
// Rebuilt on the finalized Orders command-center workspace as the
// visual master (KPI strip / toolbar / 4 summary cards / 68-32
// list+detail grid / 3-zone detail panel) - see OrdersPage in
// ../../sales/pages/SalesListPages.jsx for the reference
// implementation this mirrors. Reuses the exact same CSS classes
// (kpi-strip/orders-workspace-*/order-detail-*) so this page is
// pixel-identical in spacing/typography/cards/table density to
// Orders; those classes are shared workspace-layout primitives, not
// Orders-specific styling, and nothing in Orders' own JSX or CSS is
// touched by reusing them here.
const PAGE_SIZE = 25;

function ClientsPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isStrictlyMaster = user?.role === 'master';
  // workspace holds the one bounded GET /api/clients/workspace
  // response: { summary, clients: {items,total_count,limit,offset},
  // selected_client }.
  const [workspace, setWorkspace] = useState(null);
  const [selectedClientId, setSelectedClientId] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [leadSources, setLeadSources] = useState([]);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState(''); // '' | 'Active' | 'Inactive'
  const [search, setSearch] = useState('');
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingClient, setEditingClient] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  // Possible-duplicate check on create: the backend already exposes
  // GET /api/clients/check-duplicates (fuzzy name match) - unchanged.
  const [duplicateMatches, setDuplicateMatches] = useState(null);
  const [pendingCreateData, setPendingCreateData] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  // Detail-panel footer's "+ New Order" action - the exact same real
  // Create Order workflow ClientDetailPage's own handleCreateOrder
  // already uses (ordersAPI.create with this client preselected),
  // never a second/simplified order-creation path.
  const [showNewOrder, setShowNewOrder] = useState(false);
  const [newOrderLoading, setNewOrderLoading] = useState(false);
  const [newOrderError, setNewOrderError] = useState('');

  const activeFilters = () => {
    const params = {};
    if (statusFilter) params.status = statusFilter;
    if (search) params.search = search;
    return params;
  };

  const activeFiltersRef = useRef(activeFilters);
  activeFiltersRef.current = activeFilters;
  const selectedClientIdRef = useRef(selectedClientId);
  selectedClientIdRef.current = selectedClientId;

  const load = useCallback((filterParams, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    setPageLoading(true);
    setLoadError(false);
    clientsAPI.workspace({
      ...filterParams, limit: PAGE_SIZE, offset,
      selected_client_id: selectedClientIdRef.current || undefined,
    }).then((res) => {
      setWorkspace(res.data);
      if (res.data.selected_client) setSelectedClientId(res.data.selected_client.id);
    }).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
  }, []);

  useEffect(() => {
    load(activeFiltersRef.current());
    settingsAPI.list('lead-sources').then((res) => setLeadSources(res.data)).catch(() => setLeadSources([]));
  }, [load]);

  useEffect(() => {
    if (!pageLoading && workspace && !selectedClientId && workspace.clients?.items?.length) {
      handleSelectClient(workspace.clients.items[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageLoading, workspace]);

  const handleSelectClient = (clientId) => {
    if (clientId === selectedClientId && workspace?.selected_client) return;
    setSelectedClientId(clientId);
    setDetailLoading(true);
    clientsAPI.workspace({ selected_client_id: clientId, detail_only: true }).then((res) => {
      setWorkspace((prev) => (prev ? { ...prev, selected_client: res.data.selected_client } : prev));
    }).catch(() => {}).finally(() => setDetailLoading(false));
  };

  const applyFilters = (nextStatus, nextSearch) => {
    const params = {};
    if (nextStatus) params.status = nextStatus;
    if (nextSearch) params.search = nextSearch;
    setPage(1);
    load(params, 1);
  };

  const handleSearch = (e) => {
    e.preventDefault();
    applyFilters(statusFilter, search);
  };

  const handleStatusTab = (nextStatus) => {
    setStatusFilter(nextStatus);
    applyFilters(nextStatus, search);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(activeFilters(), pageNum);
  };

  const createClient = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await clientsAPI.create(formData);
      setShowAdd(false);
      setDuplicateMatches(null);
      setPendingCreateData(null);
      setSuccess('Client created.');
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add client');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (formData) => {
    setError('');
    try {
      const res = await clientsAPI.checkDuplicates(formData.name);
      const matches = res.data?.possible_duplicates || [];
      if (matches.length > 0) {
        setDuplicateMatches(matches);
        setPendingCreateData(formData);
        return;
      }
    } catch {
      // Duplicate check is advisory only - if it fails, don't block adding the client.
    }
    createClient(formData);
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await clientsAPI.update(editingClient.id, formData);
      setEditingClient(null);
      setSuccess('Client updated.');
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update client');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = (clientRow) => setPendingDelete(clientRow);
  const confirmDelete = async () => {
    setError('');
    setDeleting(true);
    try {
      await clientsAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      if (pendingDelete.id === selectedClientId) setSelectedClientId(null);
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete client');
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  // "+ New Order" footer action - identical payload shape to
  // ClientDetailPage's handleCreateOrder, this client preselected.
  const handleCreateOrderForClient = async (formData) => {
    const sel = workspace?.selected_client;
    if (!sel) return;
    setNewOrderLoading(true);
    setNewOrderError('');
    try {
      await ordersAPI.create({
        ...formData, client_id: sel.id,
        order_date: new Date(formData.order_date).toISOString(),
        order_value: formData.order_value || '0', advance: formData.advance || '0',
      });
      setShowNewOrder(false);
      setSuccess('Order created.');
      load(activeFilters(), page);
    } catch (err) {
      setNewOrderError(err.response?.data?.detail || 'Failed to create order');
    } finally {
      setNewOrderLoading(false);
    }
  };

  const fields = [
    { name: 'name', label: 'Client Name', required: true },
    {
      name: 'client_type', label: 'Client Type', type: 'select', required: true,
      options: [{ value: 'Individual', label: 'Individual' }, { value: 'Business', label: 'Business' }],
    },
    {
      name: 'phone', label: 'Phone', required: true,
      hint: 'Exactly 10 digits.',
      validate: (value) => (/^[0-9]{10}$/.test(value) ? '' : 'Please enter valid mobile number'),
    },
    { name: 'contact_person', label: 'Contact Person', placeholder: 'Who to actually call, if different from the client name' },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'status', label: 'Status', type: 'select', options: [
      { value: 'Active', label: 'Active' }, { value: 'Inactive', label: 'Inactive' },
    ] },
    { name: 'alternate_phone', label: 'Alternate Phone', advanced: true,
      hint: 'Exactly 10 digits.',
      validate: (value) => (/^[0-9]{10}$/.test(value) ? '' : 'Please enter valid mobile number') },
    { name: 'address', label: 'Address', type: 'textarea', advanced: true },
    { name: 'site_address', label: 'Site Address', type: 'textarea', advanced: true,
      hint: 'Where the work actually happens, if different from the address above.' },
    { name: 'city', label: 'City', advanced: true },
    { name: 'state', label: 'State', advanced: true },
    { name: 'pincode', label: 'Pincode', advanced: true },
    { name: 'gstin', label: 'GSTIN', advanced: true,
      validate: (value) => (value.length === 15 ? '' : 'GSTIN must contain 15 characters') },
    { name: 'lead_source', label: 'Lead Source', type: 'select', advanced: true,
      options: leadSources.map((s) => ({ value: s.name, label: s.name })) },
    { name: 'remarks', label: 'Notes', type: 'textarea', advanced: true },
  ];

  const editFields = fields.filter((f) => f.name !== 'client_code');

  const newOrderFields = [
    { name: 'project_type', label: 'Project Type' },
    { name: 'order_value', label: 'Order Value', type: 'number', required: true },
    { name: 'advance', label: 'Advance', type: 'number' },
    { name: 'order_date', label: 'Order Date', type: 'date', required: true },
  ];

  const exportUrl = () => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (statusFilter) params.set('status', statusFilter);
    const qs = params.toString();
    return reportsAPI.downloadUrl(`clients.xlsx${qs ? `?${qs}` : ''}`);
  };

  const summary = workspace?.summary || null;
  const clientRows = workspace?.clients?.items || [];
  const totalCount = workspace?.clients?.total_count || 0;
  const offsetStart = workspace?.clients?.offset ?? (page - 1) * PAGE_SIZE;
  const selected = workspace?.selected_client || null;

  // 5 KPI chips, all sourced from workspace.summary - nothing invented
  // client-side. Payment Due is a financial aggregate, so (matching
  // Orders' own workspace) it's simply absent for a non-master viewer.
  const kpiItems = summary ? [
    { label: 'Total Clients', value: summary.total_clients, icon: ClientIcon },
    { label: 'Active Accounts', value: summary.active_clients, icon: CheckCircleIcon },
    // "VIP / Premium" has no dedicated flag in the Client Master - this
    // reuses client_type="Business" (see backend clients_workspace),
    // the closest existing classification, rather than inventing one.
    { label: 'Business / Premium Clients', value: summary.business_clients, icon: AnalyticsIcon },
    ...(summary.payment_due_amount != null ? [{
      label: 'Payment Due', value: formatCurrency(summary.payment_due_amount), icon: PaymentIcon,
      tone: summary.payment_due_amount > 0 ? 'warning' : 'default',
    }] : []),
    { label: 'Active Relationships', value: summary.active_relationships, icon: ChatIcon },
  ] : [];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>
            Clients
            {summary && <span className="home-card-chip" style={{ marginLeft: 10, verticalAlign: 'middle' }}>{summary.active_clients} Active Clients</span>}
          </h1>
          <p className="page-summary">Manage client profiles, projects, and business history in one place.</p>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {summary && <KpiStrip items={kpiItems} />}

      <div className="orders-workspace-toolbar">
        <button className="btn-primary" onClick={() => setShowAdd(true)}>+ New Client</button>
        <a className="btn-secondary" href={exportUrl()} target="_blank" rel="noreferrer">Export Clients</a>
        {isStrictlyMaster && <button className="btn-secondary" onClick={() => navigate('/clients/import')}>Import Clients</button>}
      </div>

      <div className="orders-summary-cards">
        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Client Portfolio</span>
            {summary && <span className="home-card-chip">{summary.portfolio.total_clients} Total</span>}
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.portfolio.active_clients}</span>
                <span className="orders-card-hero-caption">Active Clients</span>
                <span className="orders-card-hero-side">{summary.portfolio.inactive_clients} Inactive</span>
              </div>
              <div className="orders-card-footer-row">
                <span>Total Clients</span>
                <strong>{summary.portfolio.total_clients}</strong>
              </div>
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Account Standing</span>
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.account_standing.in_good_standing}</span>
                <span className="orders-card-hero-caption">Good Standing</span>
              </div>
              <div className="order-health-chips">
                <div className="order-health-chip order-health-success">
                  <span className="order-health-count">{summary.account_standing.in_good_standing}</span>
                  <span className="order-health-label">Good Standing</span>
                </div>
                <div className="order-health-chip order-health-warning">
                  <span className="order-health-count">{summary.account_standing.overdue_balance}</span>
                  <span className="order-health-label">Overdue 30+ Days</span>
                </div>
              </div>
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Receivables Overview</span>
          </div>
          {isStrictlyMaster ? (
            summary?.receivables_overview ? (
              <div className="orders-card-body">
                <div className="orders-card-hero">
                  <span className="orders-card-hero-number">{formatCurrency(summary.receivables_overview.total_received)}</span>
                  <span className="orders-card-hero-caption">Received</span>
                </div>
                <div className="order-detail-split-bar">
                  <div
                    className="order-detail-split-bar-received"
                    style={{ width: `${summary.receivables_overview.total_order_value > 0 ? Math.min(100, 100 * summary.receivables_overview.total_received / summary.receivables_overview.total_order_value) : 0}%` }}
                  />
                  <div
                    className="order-detail-split-bar-pending"
                    style={{ width: `${summary.receivables_overview.total_order_value > 0 ? Math.max(0, 100 - (100 * summary.receivables_overview.total_received / summary.receivables_overview.total_order_value)) : 0}%` }}
                  />
                </div>
                <div className="orders-card-footer-row">
                  <span>Outstanding</span>
                  <strong>{formatCurrency(summary.receivables_overview.outstanding_balance)}</strong>
                </div>
              </div>
            ) : <div className="simple-chart-empty">Loading...</div>
          ) : (
            <div className="simple-chart-empty">Restricted to Master accounts.</div>
          )}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Active Orders</span>
            {summary && <span className="home-card-chip">{summary.active_orders_card.active_order_count} Active</span>}
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.active_orders_card.active_order_count}</span>
                <span className="orders-card-hero-caption">Active Orders</span>
                {isStrictlyMaster && summary.active_orders_card.active_order_value != null && (
                  <span className="orders-card-hero-side">{formatCurrency(summary.active_orders_card.active_order_value)}</span>
                )}
              </div>
              {summary.active_orders_card.stage_breakdown
                .filter((s) => s.count > 0).sort((a, b) => b.count - a.count).slice(0, 2)
                .map((s) => (
                  <div className="orders-card-stat-row" key={s.status}><span>{s.status}</span><strong>{s.count}</strong></div>
                ))}
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>
      </div>

      <div className="orders-workspace-grid">
        {/* All Clients - 68%, compact 6-column table, sticky header,
            internal scroll, row click selects (never navigates). The
            existing search box (unchanged - same state/handler) now
            lives inside this panel, under its title/tabs row, instead
            of as a separate full-width section above the workspace grid. */}
        <div className="card orders-workspace-panel">
          <div className="orders-panel-header">
            <div className="orders-panel-title">
              <h3>All Clients</h3>
              <div className="orders-panel-tabs">
                {[{ value: '', label: 'All' }, { value: 'Active', label: 'Active' }, { value: 'Inactive', label: 'Inactive' }].map((t) => (
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
              type="text" placeholder="Search by name, code, phone, or email..." value={search}
              onChange={(e) => setSearch(e.target.value)} className="form-input"
            />
            <button type="submit" className="btn-secondary">Search</button>
          </form>
          <div className="orders-table-scroll">
            {loadError ? (
              <div className="simple-chart-empty">
                Failed to load clients. <button className="btn-link" onClick={() => load(activeFilters(), page)}>Retry</button>
              </div>
            ) : pageLoading ? (
              <div className="simple-chart-empty">Loading clients...</div>
            ) : clientRows.length === 0 ? (
              <div className="simple-chart-empty">
                No clients yet.
                <br /><button className="btn-link" onClick={() => setShowAdd(true)}>Add your first client</button>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Client ID</th><th>Client Name</th><th>Contact</th>
                    <th>Active Orders</th><th>Client Value</th><th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {clientRows.map((row) => (
                    <tr
                      key={row.id}
                      className={`clickable ${row.id === selectedClientId ? 'orders-row-selected' : ''}`}
                      tabIndex={0}
                      role="button"
                      onClick={() => handleSelectClient(row.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelectClient(row.id); } }}
                    >
                      <td>
                        <span className="business-id-badge">{row.business_id || '-'}</span>
                        <span className="client-id-ref">{row.client_code}</span>
                      </td>
                      <td>{row.name}</td>
                      <td>{row.phone || row.email || '-'}</td>
                      <td>{row.active_orders}</td>
                      <td>{row.client_value != null ? formatCurrency(row.client_value) : 'Restricted'}</td>
                      <td><span className={`status-badge ${statusClass(row.status)}`}>{row.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="orders-panel-footer">
            <span>{clientRows.length ? `Showing ${offsetStart + 1}-${offsetStart + clientRows.length} of ${totalCount}` : `${totalCount} clients`}</span>
            {totalCount > PAGE_SIZE && (
              <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />
            )}
          </div>
        </div>

        {/* Client Details - 32%, three fixed/scroll/fixed zones. */}
        <div className="card orders-workspace-panel">
          <div className="orders-panel-header">
            <div className="orders-panel-title"><h3>Client Details</h3></div>
            {selected && <button className="btn-link" onClick={() => navigate(`/clients/${selected.id}`)}>Full Detail</button>}
          </div>
          {!selected ? (
            <div className="order-detail-empty">
              {detailLoading ? 'Loading...' : 'Select a client from the list to see its details.'}
            </div>
          ) : (
            <>
              <div className="order-detail-top">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <h3 style={{ margin: 0 }}>{selected.name}</h3>
                  <button type="button" className="order-detail-icon-btn" title="Print" onClick={() => window.print()}>
                    <PrinterIcon />
                  </button>
                </div>
                <div className="order-detail-top-meta" style={{ marginTop: 6 }}>
                  <span className="business-id-badge">{selected.business_id || selected.client_code}</span>
                  <span className={`status-badge status-badge-dot ${statusClass(selected.status)}`}>{selected.status}</span>
                  {selected.client_type === 'Business' && <span className="status-badge status-info">Business / Premium</span>}
                  <button className="btn-link" onClick={() => setEditingClient(selected)}>Edit</button>
                  {isStrictlyMaster && (
                    <button className="btn-link" onClick={() => handleDelete(selected)}>Delete</button>
                  )}
                </div>
                <div className="order-detail-client">
                  {selected.contact.contact_person || selected.name}
                  {selected.contact.phone ? ` - ${selected.contact.phone}` : ''}
                </div>
              </div>

              <div className="order-detail-scroll">
                <div>
                  <div className="order-detail-section-label">Contact Information</div>
                  <div className="order-detail-row"><span>Phone</span><strong>{selected.contact.phone || '-'}</strong></div>
                  {selected.contact.alternate_phone && (
                    <div className="order-detail-row"><span>Alternate Phone</span><strong>{selected.contact.alternate_phone}</strong></div>
                  )}
                  <div className="order-detail-row"><span>Email</span><strong>{selected.contact.email || '-'}</strong></div>
                  <div className="order-detail-row"><span>Billing Address</span><strong>{selected.address.billing_address || '-'}</strong></div>
                  {selected.address.site_address && (
                    <div className="order-detail-row"><span>Site Address</span><strong>{selected.address.site_address}</strong></div>
                  )}
                  {selected.address.gstin && (
                    <div className="order-detail-row"><span>GSTIN</span><strong>{selected.address.gstin}</strong></div>
                  )}
                </div>

                <div>
                  <div className="order-detail-section-label">Account Overview</div>
                  <div className="order-detail-row"><span>Total Orders</span><strong>{selected.account_overview.total_orders}</strong></div>
                  {isStrictlyMaster && (
                    <>
                      <div className="order-detail-row"><span>Total Order Value</span><strong>{formatCurrency(selected.account_overview.total_order_value)}</strong></div>
                      {selected.account_overview.total_order_value > 0 && (
                        <div className="order-detail-split-bar">
                          <div className="order-detail-split-bar-received" style={{ width: `${Math.min(100, 100 * (selected.account_overview.total_received || 0) / selected.account_overview.total_order_value)}%` }} />
                          <div className="order-detail-split-bar-pending" style={{ width: `${Math.max(0, 100 - (100 * (selected.account_overview.total_received || 0) / selected.account_overview.total_order_value))}%` }} />
                        </div>
                      )}
                      <div className="order-detail-row"><span>Received</span><strong>{formatCurrency(selected.account_overview.total_received)}</strong></div>
                      <div className="order-detail-row"><span>Outstanding</span><strong>{formatCurrency(selected.account_overview.outstanding_balance)}</strong></div>
                    </>
                  )}
                </div>

                <div>
                  <div className="order-detail-section-label">Orders ({selected.orders.length})</div>
                  {selected.orders.length === 0 ? (
                    <div className="order-detail-row"><span>No orders yet.</span></div>
                  ) : selected.orders.map((o) => (
                    <div
                      className="order-detail-item-row" key={o.id} style={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/orders/${o.id}`)}
                    >
                      <span>{o.order_code} &middot; {o.project_status}</span>
                      <span>{o.order_value != null ? formatCurrency(o.order_value) : 'Restricted'}</span>
                    </div>
                  ))}
                </div>

                <div>
                  <div className="order-detail-section-label">Estimates ({selected.estimates.length})</div>
                  {selected.estimates.length === 0 ? (
                    <div className="order-detail-row"><span>No estimates yet.</span></div>
                  ) : selected.estimates.map((e) => (
                    <div
                      className="order-detail-item-row" key={e.id} style={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/estimates/${e.id}`)}
                    >
                      <span>{e.estimate_code} &middot; {e.status}</span>
                      <span>{e.total_cost != null ? formatCurrency(e.total_cost) : 'Restricted'}</span>
                    </div>
                  ))}
                </div>

                {selected.recent_activity.length > 0 && (
                  <div>
                    <div className="order-detail-section-label">Recent Activity</div>
                    {selected.recent_activity.map((a, i) => (
                      <div className="order-detail-comment" key={i}>
                        <strong>{a.type}</strong> - {a.text}
                      </div>
                    ))}
                  </div>
                )}

                <div>
                  <div className="order-detail-section-label">Documents ({selected.documents.length})</div>
                  {selected.documents.length === 0 ? (
                    <div className="order-detail-row"><span>No documents yet.</span></div>
                  ) : selected.documents.map((d) => (
                    <div className="order-detail-item-row" key={d.id}>
                      <a href={clientDocumentsAPI.downloadUrl(selected.id, d.id)} target="_blank" rel="noreferrer">{d.original_filename}</a>
                      <span>{d.description || ''}</span>
                    </div>
                  ))}
                </div>

                {selected.remarks && (
                  <div>
                    <div className="order-detail-section-label">Notes</div>
                    <div className="order-detail-row"><span>{selected.remarks}</span></div>
                  </div>
                )}
              </div>

              <div className="order-detail-bottom">
                <button className="btn-secondary" style={{ flex: 1 }} onClick={() => setEditingClient(selected)}>Edit Client</button>
                <button className="btn-primary" style={{ flex: 1 }} onClick={() => setShowNewOrder(true)}>+ New Order</button>
              </div>
            </>
          )}
        </div>
      </div>

      <Modal isOpen={showAdd} title="Add Client" onClose={() => { setShowAdd(false); setDuplicateMatches(null); setPendingCreateData(null); }}>
        {duplicateMatches ? (
          <div>
            <Alert
              type="warning" onClose={() => {}}
              message={`This might be a duplicate - ${duplicateMatches.length} existing client(s) have a similar name. Review below, or continue if this is genuinely a different client.`}
            />
            <ul className="duplicate-match-list">
              {duplicateMatches.map((m) => (
                <li key={m.id}>
                  <strong>{m.name}</strong> &middot; {m.client_code} {m.phone ? `\u00b7 ${m.phone}` : ''}
                </li>
              ))}
            </ul>
            <div className="page-actions" style={{ marginTop: 16 }}>
              <button className="btn-secondary" onClick={() => { setDuplicateMatches(null); setPendingCreateData(null); }} disabled={loading}>
                Go Back
              </button>
              <button className="btn-primary" onClick={() => createClient(pendingCreateData)} disabled={loading}>
                {loading ? 'Adding...' : 'Add Anyway'}
              </button>
            </div>
          </div>
        ) : (
          <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Client" />
        )}
      </Modal>
      <Modal isOpen={!!editingClient} title={`Edit ${editingClient?.name || ''}`} onClose={() => setEditingClient(null)}>
        {editingClient && (
          <Form
            fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
            initialValues={{
              // editingClient is always set from `selected` (the workspace
              // detail payload's selected_client), which nests contact
              // fields under `contact` and address fields under `address`.
              name: editingClient.name, client_type: editingClient.client_type,
              phone: editingClient.contact?.phone,
              contact_person: editingClient.contact?.contact_person,
              email: editingClient.contact?.email,
              status: editingClient.status,
              alternate_phone: editingClient.contact?.alternate_phone,
              address: editingClient.address?.billing_address,
              site_address: editingClient.address?.site_address,
              city: editingClient.address?.city,
              state: editingClient.address?.state,
              pincode: editingClient.address?.pincode,
              gstin: editingClient.address?.gstin,
              lead_source: editingClient.lead_source,
              remarks: editingClient.remarks,
            }}
          />
        )}
      </Modal>

      <Modal isOpen={showNewOrder} title={`New Order - ${selected?.name || ''}`} onClose={() => { setShowNewOrder(false); setNewOrderError(''); }}>
        {newOrderError && <Alert type="error" message={newOrderError} onClose={() => setNewOrderError('')} />}
        <Form
          fields={newOrderFields} onSubmit={handleCreateOrderForClient} loading={newOrderLoading} submitText="Create Order"
          initialValues={{ order_date: today() }}
        />
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDelete}
        message={pendingDelete ? `Delete ${pendingDelete.name}? This cannot be undone.` : ''}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
        loading={deleting}
      />
    </div>
  );
}

// --- ClientImportPage.jsx ---
function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function rowStatus(row, resolution) {
  if (row.errors.length > 0) return { label: 'ERROR', className: 'status-danger' };
  if (row.is_duplicate) return { label: 'EXISTING CLIENT', className: 'status-info' };
  if (row.possible_match_client_id && resolution === 'existing') return { label: 'WILL USE EXISTING', className: 'status-info' };
  if (row.possible_match_client_id && resolution !== 'new') return { label: 'POSSIBLE MATCH - REVIEW', className: 'status-warning' };
  return { label: 'NEW', className: 'status-gold' };
}

function ClientImportPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [lastUploadedFile, setLastUploadedFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({}); // row_number -> true if user opted out
  // A possible (fuzzy) match is never auto-resolved.
  // row_number -> 'existing' | 'new', unset until the user picks one.
  const [matchResolutions, setMatchResolutions] = useState({});
  const [stage, setStage] = useState('empty'); // empty | selected | validating | preview | importing | success | error
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  const resetFile = () => {
    setFile(null);
    setPreview(null);
    setExcludedRows({});
    setMatchResolutions({});
    setLastUploadedFile(null);
    setStage('empty');
    setError('');
  };

  const handleFileSelected = (selected) => {
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith('.xlsx')) {
      setError('Please choose a .xlsx file - other formats are not supported.');
      return;
    }
    setFile(selected);
    setPreview(null);
    setResult(null);
    setError('');
    setStage('selected');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFileSelected(e.dataTransfer.files?.[0]);
  };

  const handleValidate = async () => {
    if (!file) return;
    setStage('validating');
    setError('');
    try {
      const res = await clientImportAPI.preview(file);
      setPreview(res.data);
      setLastUploadedFile(file);
      // Every error-free, non-matched row is included by default;
      // existing-client matches are always reused (never excludable -
      // excluding one would just mean "don't reuse it", but there's no
      // create-a-duplicate-anyway option per the Client Recognition rule)
      // and error rows can never be included until fixed and re-uploaded.
      setExcludedRows({});
      setMatchResolutions({});
      setStage('preview');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not read this file. Make sure you used the downloaded template.');
      setStage('selected');
    }
  };

  const handleImport = async () => {
    if (!preview) return;
    setStage('importing');
    setError('');
    try {
      const rowsToCommit = preview.rows
        .filter((r) => r.errors.length === 0)
        .map((r) => {
          const resolution = matchResolutions[r.row_number];
          const usingExisting = r.possible_match_client_id && resolution === 'existing';
          // A possible (not exact) match that hasn't been explicitly resolved
          // yet is never imported silently as either choice - skip it until
          // the user picks "Use Existing" or "Create New".
          const unresolvedPossibleMatch = r.possible_match_client_id && !resolution;
          return {
            name: r.name, client_type: r.client_type, contact_person: r.contact_person, phone: r.phone,
            alternate_phone: r.alternate_phone, email: r.email, address: r.address,
            site_address: r.site_address, city: r.city, state: r.state, pincode: r.pincode, gstin: r.gstin,
            lead_source: r.lead_source, remarks: r.remarks,
            matched_client_id: usingExisting ? r.possible_match_client_id : r.matched_client_id,
            skip: !!excludedRows[r.row_number] || unresolvedPossibleMatch,
          };
        });
      const res = await clientImportAPI.commit(rowsToCommit);
      setResult(res.data);
      setPreview(null);
      setFile(null);
      setStage(res.data.error ? 'error' : 'success');
    } catch (err) {
      setError(err.response?.data?.detail || 'Import failed. Please try again.');
      setStage('preview');
    }
  };

  const [downloadingErrors, setDownloadingErrors] = useState(false);
  const downloadErrorReport = async () => {
    if (!lastUploadedFile) return;
    setDownloadingErrors(true);
    setError('');
    try {
      const res = await clientImportAPI.errorReport(lastUploadedFile);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Client_Import_Errors.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not generate the error report. Please try again.');
    } finally {
      setDownloadingErrors(false);
    }
  };

  const errorCount = preview ? preview.rows.filter((r) => r.errors.length > 0).length : 0;
  const importableCount = preview ? preview.rows.filter((r) => {
    if (r.errors.length > 0 || excludedRows[r.row_number]) return false;
    if (r.possible_match_client_id && !matchResolutions[r.row_number]) return false;
    return true;
  }).length : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Import Clients from Excel</h1>
          <p className="page-summary">
            Download the template, fill in one row per client, then upload it here for review before anything is saved.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => navigate('/clients')}>Back to Clients</button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {(stage === 'success' || stage === 'error') && result && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>{stage === 'error' ? 'Import Partially Complete' : 'Import Complete'}</h3>
            <div className="import-result-grid">
              <div><span className="import-result-number">{result.created_clients}</span><span className="import-result-label">New Clients</span></div>
              <div><span className="import-result-number">{result.matched_existing}</span><span className="import-result-label">Existing Clients Matched</span></div>
              <div><span className="import-result-number">{result.skipped}</span><span className="import-result-label">Skipped</span></div>
            </div>
            {result.error && <Alert type="warning" message={result.error} />}
            <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
              <button className="btn-primary" onClick={() => navigate('/clients')}>View Imported Clients</button>
              <button className="btn-secondary" onClick={resetFile}>Import Another File</button>
            </div>
          </div>
        </Card>
      )}

      {(stage === 'empty' || stage === 'selected' || stage === 'validating') && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={clientImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
                Download Template
              </a>
            </p>

            {!file && (
              <div
                className={`import-dropzone ${dragOver ? 'drag-over' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
              >
                <p className="import-dropzone-title">Drag and drop your Excel file here</p>
                <p className="import-dropzone-hint">or click to choose a file &middot; accepts .xlsx only</p>
                <input
                  ref={fileInputRef} type="file" accept=".xlsx" style={{ display: 'none' }}
                  onChange={(e) => handleFileSelected(e.target.files?.[0])}
                />
              </div>
            )}

            {file && (
              <div className="import-file-selected">
                <div>
                  <span className="import-file-name">{file.name}</span>
                  <span className="import-file-size">{formatFileSize(file.size)}</span>
                </div>
                <button className="btn-link" onClick={resetFile} disabled={stage === 'validating'}>Remove</button>
              </div>
            )}

            <button
              className="btn-primary" style={{ marginTop: 16 }}
              onClick={handleValidate} disabled={!file || stage === 'validating'}
            >
              {stage === 'validating' ? 'Validating...' : 'Validate & Preview'}
            </button>
          </div>
        </Card>
      )}

      {(stage === 'preview' || stage === 'importing') && preview && (
        <>
          <Card>
            <div className="card-body">
              <h3 style={{ marginTop: 0 }}>{preview.total_rows} row{preview.total_rows !== 1 ? 's' : ''} detected</h3>
              <p>
                {preview.new_rows} new client{preview.new_rows !== 1 ? 's' : ''} &middot;{' '}
                {preview.duplicate_rows} existing client{preview.duplicate_rows !== 1 ? 's' : ''} matched &middot;{' '}
                {preview.error_rows} row{preview.error_rows !== 1 ? 's' : ''} rejected
                {preview.error_rows > 0 ? ' (won\u2019t be imported)' : ''}.
              </p>
              {errorCount > 0 && (
                <button className="btn-link" onClick={downloadErrorReport} disabled={downloadingErrors}>
                  {downloadingErrors ? 'Preparing report...' : 'Download Error Report'}
                </button>
              )}
            </div>
          </Card>

          <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th></th><th>Client Name</th><th>Type</th><th>Phone</th><th>Email</th><th>City</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r) => {
                const resolution = matchResolutions[r.row_number];
                const status = rowStatus(r, resolution);
                const canExclude = r.errors.length === 0 && !r.is_duplicate;
                return (
                  <tr key={r.row_number} style={{ opacity: excludedRows[r.row_number] ? 0.5 : 1 }}>
                    <td>
                      {canExclude && (
                        <input
                          type="checkbox" checked={!excludedRows[r.row_number]}
                          onChange={(e) => setExcludedRows((prev) => ({ ...prev, [r.row_number]: !e.target.checked }))}
                        />
                      )}
                    </td>
                    <td>{r.name || '-'}</td>
                    <td>{r.client_type || '-'}</td>
                    <td>{r.phone || '-'}</td>
                    <td>{r.email || '-'}</td>
                    <td>{r.city || '-'}</td>
                    <td>
                      <span className={`status-badge ${status.className}`}>{status.label}</span>
                      {r.errors.length > 0 && (
                        <div className="import-row-error">{r.errors.join('; ')}</div>
                      )}
                      {r.possible_match_client_id && !r.is_duplicate && r.errors.length === 0 && (
                        <div className="import-row-possible-match">
                          <span>You entered <strong>{r.name}</strong> - an existing client named{' '}
                            <strong>{r.possible_match_name}</strong> looks similar. Is this the same client?</span>
                          <div style={{ marginTop: 6, display: 'flex', gap: 8 }}>
                            <button
                              type="button" className="btn-link"
                              onClick={() => setMatchResolutions((prev) => ({ ...prev, [r.row_number]: 'existing' }))}
                            >
                              Use Existing
                            </button>
                            <button
                              type="button" className="btn-link"
                              onClick={() => setMatchResolutions((prev) => ({ ...prev, [r.row_number]: 'new' }))}
                            >
                              Create New (Different Client)
                            </button>
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>

          <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="btn-primary" onClick={handleImport} disabled={stage === 'importing' || importableCount === 0}>
              {stage === 'importing' ? 'Importing...' : `Confirm Import (${importableCount} row${importableCount !== 1 ? 's' : ''})`}
            </button>
            <button className="btn-secondary" onClick={resetFile} disabled={stage === 'importing'}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}

export { ClientsPage, ClientImportPage };
