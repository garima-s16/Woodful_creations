// Procurement pages: suppliers workspace, purchases list/detail, and
// purchase Excel import. Combines the former SuppliersPage.jsx,
// SupplierDetailPage.jsx, PurchasesPage.jsx, PurchaseDetailPage.jsx,
// and PurchaseImportPage.jsx.
//
// SuppliersPage below is rebuilt on the finalized Orders/Clients
// command-center workspace as the visual master (KPI strip / toolbar /
// 4 summary cards / 68-32 list+detail grid / 3-zone detail panel) -
// see OrdersPage in ../../sales/pages/SalesListPages.jsx and
// ClientsPage in ../../clients/pages/ClientPages.jsx for the reference
// implementation this mirrors. Reuses the exact same CSS classes
// (kpi-strip/orders-workspace-*/order-detail-*) - shared workspace-
// layout primitives, not Orders-specific styling - so this page is
// visually identical in spacing/typography/cards/table density to
// Orders/Clients. SupplierDetailPage's former standalone-route
// functionality (Supplier Details / Purchase History / Documents) now
// lives inside the workspace's right-hand inspector panel, reusing the
// exact same underlying data and role-based restrictions.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { documentsAPI, locationsAPI, materialsAPI, purchaseImportAPI, purchasesAPI, reportsAPI, suppliersAPI } from '../../../utils/api';
import { Alert, Card, ConfirmDialog, Form, KpiStrip, Modal, Pagination, Table } from '../../../components/common/UI';
import { DocumentsPanel } from '../../../components/Assistant';
import { classifyLoadError, formatCurrency, statusClass, today } from '../../../utils/utils';
import { PurchaseIcon, PaymentIcon, TruckIcon, CheckCircleIcon, AlertTriangleIcon, PrinterIcon } from '../../../components/icons';
import { ProcurementRequirementsPage } from './RequirementsCartPages';

// --- SuppliersPage.jsx ---
const PAGE_SIZE = 25;

function SuppliersPage() {
  const navigate = useNavigate();
  // Route compatibility: /suppliers/:supplierId (the former standalone
  // SupplierDetailPage route) now renders this same workspace with
  // that supplier pre-selected, instead of a separate detail screen.
  const { supplierId: routeSupplierId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const isStrictlyMaster = user?.role === 'master';
  // workspace holds the one bounded GET /api/suppliers/workspace
  // response: { summary, suppliers: {items,total_count,limit,offset},
  // selected_supplier }.
  const [workspace, setWorkspace] = useState(null);
  const [selectedSupplierId, setSelectedSupplierId] = useState(routeSupplierId ? Number(routeSupplierId) : null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [search, setSearch] = useState('');
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingSupplier, setEditingSupplier] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const activeFilters = () => {
    const params = {};
    if (categoryFilter) params.category = categoryFilter;
    if (search) params.search = search;
    return params;
  };

  const activeFiltersRef = useRef(activeFilters);
  activeFiltersRef.current = activeFilters;
  const selectedSupplierIdRef = useRef(selectedSupplierId);
  selectedSupplierIdRef.current = selectedSupplierId;

  const load = useCallback((filterParams, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    setPageLoading(true);
    setLoadError(false);
    suppliersAPI.workspace({
      ...filterParams, limit: PAGE_SIZE, offset,
      selected_supplier_id: selectedSupplierIdRef.current || undefined,
    }).then((res) => {
      setWorkspace(res.data);
      if (res.data.selected_supplier) setSelectedSupplierId(res.data.selected_supplier.id);
    }).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
  }, []);

  useEffect(() => {
    load(activeFiltersRef.current());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  useEffect(() => {
    if (!pageLoading && workspace && !selectedSupplierId && workspace.suppliers?.items?.length) {
      handleSelectSupplier(workspace.suppliers.items[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageLoading, workspace]);

  const handleSelectSupplier = (supplierIdVal) => {
    if (supplierIdVal === selectedSupplierId && workspace?.selected_supplier) return;
    setSelectedSupplierId(supplierIdVal);
    setDetailLoading(true);
    suppliersAPI.workspace({ selected_supplier_id: supplierIdVal, detail_only: true }).then((res) => {
      setWorkspace((prev) => (prev ? { ...prev, selected_supplier: res.data.selected_supplier } : prev));
    }).catch(() => {}).finally(() => setDetailLoading(false));
  };

  const applyFilters = (nextCategory, nextSearch) => {
    const params = {};
    if (nextCategory) params.category = nextCategory;
    if (nextSearch) params.search = nextSearch;
    setPage(1);
    load(params, 1);
  };

  const handleSearch = (e) => {
    e.preventDefault();
    applyFilters(categoryFilter, search);
  };

  const handleCategoryTab = (nextCategory) => {
    setCategoryFilter(nextCategory);
    applyFilters(nextCategory, search);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(activeFilters(), pageNum);
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await suppliersAPI.create(formData);
      setShowAdd(false);
      setSuccess('Supplier created.');
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add supplier');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await suppliersAPI.update(editingSupplier.id, formData);
      setEditingSupplier(null);
      setSuccess('Supplier updated.');
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update supplier');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = (supplierRow) => setPendingDelete(supplierRow);
  const confirmDelete = async () => {
    setError('');
    setDeleting(true);
    try {
      await suppliersAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      if (pendingDelete.id === selectedSupplierId) setSelectedSupplierId(null);
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete supplier');
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'category', label: 'Category' },
    { name: 'phone', label: 'Phone', hint: 'Exactly 10 digits.',
      validate: (value) => (/^[0-9]{10}$/.test(value) ? '' : 'Please enter valid mobile number') },
    { name: 'contact_person', label: 'Contact Person', advanced: true },
    { name: 'address', label: 'Address', type: 'textarea', advanced: true },
    {
      name: 'gstin', label: 'GSTIN', advanced: true,
      hint: '15-character GST identification number',
      validate: (value) => (value.length !== 15 ? 'GSTIN must contain 15 characters.' : null),
    },
    { name: 'payment_terms', label: 'Payment Terms', advanced: true },
    { name: 'remarks', label: 'Remarks', type: 'textarea', advanced: true },
  ];

  const editFields = fields.filter((f) => f.name !== 'supplier_code');

  const summary = workspace?.summary || null;
  const supplierRows = workspace?.suppliers?.items || [];
  const totalCount = workspace?.suppliers?.total_count || 0;
  const offsetStart = workspace?.suppliers?.offset ?? (page - 1) * PAGE_SIZE;
  const selected = workspace?.selected_supplier || null;

  // Real category tabs, sourced from workspace.summary.overview.category_breakdown -
  // nothing invented client-side. "Uncategorized" (null category) is
  // shown as a KPI/summary figure but isn't a clickable filter tab,
  // since Supplier.category == null can't be expressed as a category
  // query value the same way a real category string can.
  const categoryTabs = [
    { value: '', label: 'All' },
    ...(summary?.overview?.category_breakdown || [])
      .filter((c) => c.category && c.category !== 'Uncategorized')
      .sort((a, b) => b.count - a.count)
      .slice(0, 4)
      .map((c) => ({ value: c.category, label: c.category })),
  ];

  // 4 KPI chips, all sourced from workspace.summary. "Active Suppliers"
  // has no dedicated status field on Supplier (see backend
  // suppliers_workspace's own docstring) - "Suppliers with Purchase
  // Activity" is the real, derivable aggregate used instead.
  const kpiItems = summary ? [
    { label: 'Total Suppliers', value: summary.total_suppliers, icon: PurchaseIcon },
    { label: 'Suppliers with Purchase Activity', value: summary.suppliers_with_purchases, icon: CheckCircleIcon },
    { label: 'Total Purchases', value: summary.total_purchase_count, icon: TruckIcon },
    ...(summary.outstanding_invoice_count != null ? [{
      label: 'Outstanding Invoices', value: summary.outstanding_invoice_count, icon: PaymentIcon,
      tone: summary.outstanding_invoice_count > 0 ? 'warning' : 'default',
    }] : []),
  ] : [];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>
            Suppliers
            {summary && <span className="home-card-chip" style={{ marginLeft: 10, verticalAlign: 'middle' }}>{summary.total_suppliers} Suppliers</span>}
          </h1>
          <p className="page-summary">Track supplier relationships and purchase history in one place.</p>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {summary && <KpiStrip items={kpiItems} />}

      <div className="orders-workspace-toolbar">
        {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>+ New Supplier</button>}
        <a className="btn-secondary" href={reportsAPI.downloadUrl('suppliers.xlsx')} target="_blank" rel="noreferrer">Export Excel</a>
      </div>

      <div className="orders-summary-cards">
        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Supplier Overview</span>
            {summary && <span className="home-card-chip">{summary.overview.total_suppliers} Total</span>}
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.overview.total_suppliers}</span>
                <span className="orders-card-hero-caption">Total Suppliers</span>
              </div>
              {summary.overview.category_breakdown.slice(0, 3).map((c) => (
                <div className="orders-card-stat-row" key={c.category}><span>{c.category}</span><strong>{c.count}</strong></div>
              ))}
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Purchase Activity</span>
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.purchase_activity.total_purchase_count}</span>
                <span className="orders-card-hero-caption">Total Purchases</span>
                {isPrivileged && summary.purchase_activity.total_purchased_value != null && (
                  <span className="orders-card-hero-side">{formatCurrency(summary.purchase_activity.total_purchased_value)}</span>
                )}
              </div>
              <div className="orders-card-footer-row">
                <span>Suppliers with Activity</span>
                <strong>{summary.purchase_activity.suppliers_with_purchases}</strong>
              </div>
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Payables Overview</span>
          </div>
          {isPrivileged ? (
            summary ? (
              <div className="orders-card-body">
                <div className="orders-card-hero">
                  <span className="orders-card-hero-number">{formatCurrency(summary.payables_overview.outstanding_amount)}</span>
                  <span className="orders-card-hero-caption">Outstanding</span>
                </div>
                <div className="orders-card-footer-row">
                  <span>Unpaid/Part Paid Invoices</span>
                  <strong>{summary.payables_overview.outstanding_invoice_count}</strong>
                </div>
              </div>
            ) : <div className="simple-chart-empty">Loading...</div>
          ) : (
            <div className="simple-chart-empty">Restricted to Master accounts.</div>
          )}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Delivery / Purchase Performance</span>
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="order-health-chips">
                {summary.performance.receipt_status_breakdown.map((s) => (
                  <div
                    className={`order-health-chip ${s.status === 'Received' ? 'order-health-success' : s.status === 'Ordered' ? 'order-health-warning' : 'order-health-danger'}`}
                    key={s.status}
                  >
                    <span className="order-health-count">{s.count}</span>
                    <span className="order-health-label">{s.status}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>
      </div>

      <div className="orders-workspace-grid">
        {/* All Suppliers - 68%, compact table, sticky header, internal
            scroll, row click selects (never navigates). */}
        <div className="card orders-workspace-panel">
          <div className="orders-panel-header">
            <div className="orders-panel-title">
              <h3>All Suppliers</h3>
              <div className="orders-panel-tabs">
                {categoryTabs.map((t) => (
                  <button
                    key={t.label} type="button"
                    className={`orders-panel-tab ${categoryFilter === t.value ? 'active' : ''}`}
                    onClick={() => handleCategoryTab(t.value)}
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
              type="text" placeholder="Search by name, code, category, contact, or phone..." value={search}
              onChange={(e) => setSearch(e.target.value)} className="form-input"
            />
            <button type="submit" className="btn-secondary">Search</button>
          </form>
          <div className="orders-table-scroll">
            {loadError ? (
              <div className="simple-chart-empty">
                Failed to load suppliers. <button className="btn-link" onClick={() => load(activeFilters(), page)}>Retry</button>
              </div>
            ) : pageLoading ? (
              <div className="simple-chart-empty">Loading suppliers...</div>
            ) : supplierRows.length === 0 ? (
              <div className="simple-chart-empty">
                No suppliers yet.
                {isPrivileged && <><br /><button className="btn-link" onClick={() => setShowAdd(true)}>Add your first supplier</button></>}
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Supplier ID</th><th>Name</th><th>Category</th><th>Contact Person</th>
                    <th>Phone</th><th>Payment Terms</th>
                    {isPrivileged && <th>Outstanding</th>}
                  </tr>
                </thead>
                <tbody>
                  {supplierRows.map((row) => (
                    <tr
                      key={row.id}
                      className={`clickable ${row.id === selectedSupplierId ? 'orders-row-selected' : ''}`}
                      tabIndex={0}
                      role="button"
                      onClick={() => handleSelectSupplier(row.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelectSupplier(row.id); } }}
                    >
                      <td>
                        <span className="business-id-badge">{row.business_id || '-'}</span>
                        <span className="client-id-ref">{row.supplier_code}</span>
                      </td>
                      <td>{row.name}</td>
                      <td>{row.category || 'Uncategorized'}</td>
                      <td>{row.contact_person || '-'}</td>
                      <td>{row.phone || '-'}</td>
                      <td>{row.payment_terms || '-'}</td>
                      {isPrivileged && (
                        <td>
                          {row.outstanding_purchase_count > 0
                            ? <span className="status-badge status-warning">{row.outstanding_purchase_count} Unpaid</span>
                            : <span className="status-badge status-success">Clear</span>}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="orders-panel-footer">
            <span>{supplierRows.length ? `Showing ${offsetStart + 1}-${offsetStart + supplierRows.length} of ${totalCount}` : `${totalCount} suppliers`}</span>
            {totalCount > PAGE_SIZE && (
              <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />
            )}
          </div>
        </div>

        {/* Supplier Details - 32%, three fixed/scroll/fixed zones. */}
        <div className="card orders-workspace-panel">
          <div className="orders-panel-header">
            <div className="orders-panel-title"><h3>Supplier Details</h3></div>
          </div>
          {!selected ? (
            <div className="order-detail-empty">
              {detailLoading ? 'Loading...' : 'Select a supplier from the list to see its details.'}
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
                  <span className="business-id-badge">{selected.business_id || selected.supplier_code}</span>
                  <span className="status-badge status-info">{selected.category || 'Uncategorized'}</span>
                  {isPrivileged && <button className="btn-link" onClick={() => setEditingSupplier(selected)}>Edit</button>}
                  {isStrictlyMaster && (
                    <button className="btn-link" onClick={() => handleDelete(selected)}>Delete</button>
                  )}
                </div>
              </div>

              <div className="order-detail-scroll">
                <div>
                  <div className="order-detail-section-label">Supplier Details</div>
                  <div className="order-detail-row"><span>Contact Person</span><strong>{selected.details.contact_person || '-'}</strong></div>
                  <div className="order-detail-row"><span>Phone</span><strong>{selected.details.phone || '-'}</strong></div>
                  <div className="order-detail-row"><span>Address</span><strong>{selected.details.address || '-'}</strong></div>
                  <div className="order-detail-row"><span>GSTIN</span><strong>{selected.details.gstin || '-'}</strong></div>
                  <div className="order-detail-row"><span>Payment Terms</span><strong>{selected.details.payment_terms || '-'}</strong></div>
                  {selected.details.remarks && (
                    <div className="order-detail-row"><span>Remarks</span><strong>{selected.details.remarks}</strong></div>
                  )}
                </div>

                {isPrivileged && (
                  <div>
                    <div className="order-detail-section-label">Purchase Summary</div>
                    <div className="order-detail-row"><span>Total Purchased</span><strong>{formatCurrency(selected.purchase_summary.total_purchased)}</strong></div>
                    <div className="order-detail-row"><span>Purchase Count</span><strong>{selected.purchase_summary.purchase_count}</strong></div>
                    <div className="order-detail-row"><span>Unpaid/Part Paid Invoices</span><strong>{selected.purchase_summary.outstanding_invoice_count}</strong></div>
                  </div>
                )}

                <div>
                  <div className="order-detail-section-label">Materials Supplied ({selected.materials_supplied.length})</div>
                  {selected.materials_supplied.length === 0 ? (
                    <div className="order-detail-row"><span>No materials linked to this supplier yet.</span></div>
                  ) : selected.materials_supplied.map((m) => (
                    <div className="order-detail-item-row" key={m.link_id}>
                      <span>{m.material_name}{m.is_preferred ? ' ★' : ''}</span>
                      <span>{m.supplier_price != null ? formatCurrency(m.supplier_price) : 'Restricted'}</span>
                    </div>
                  ))}
                </div>

                {isPrivileged && (
                  <div>
                    <div className="order-detail-section-label">Purchase History ({selected.purchase_history.length})</div>
                    {selected.purchase_history.length === 0 ? (
                      <div className="order-detail-row"><span>No purchases recorded from this supplier yet.</span></div>
                    ) : selected.purchase_history.map((p) => (
                      <div className="order-detail-item-row" key={p.id}>
                        <span>{p.purchase_code} &middot; {p.payment_status}</span>
                        <span>{p.invoice_total != null ? formatCurrency(p.invoice_total) : 'Restricted'}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div>
                  <div className="order-detail-section-label">Documents</div>
                  <DocumentsPanel title="" api={{
                    list: () => documentsAPI.list('supplier', selected.id),
                    upload: (file, description) => documentsAPI.upload('supplier', selected.id, file, description),
                    downloadUrl: (documentId) => documentsAPI.downloadUrl('supplier', selected.id, documentId),
                    remove: (documentId) => documentsAPI.remove('supplier', selected.id, documentId),
                  }} canUpload={isPrivileged} />
                </div>
              </div>

              <div className="order-detail-bottom">
                {isPrivileged && <button className="btn-primary" style={{ flex: 1 }} onClick={() => setEditingSupplier(selected)}>Edit Supplier</button>}
              </div>
            </>
          )}
        </div>
      </div>

      <Modal isOpen={showAdd} title="Add Supplier" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Supplier" />
      </Modal>
      <Modal isOpen={!!editingSupplier} title={`Edit ${editingSupplier?.name || ''}`} onClose={() => setEditingSupplier(null)}>
        {editingSupplier && (
          <Form
            fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
            initialValues={{
              // editingSupplier is always set from `selected` (the
              // workspace detail payload's selected_supplier), which
              // nests contact/address fields under `details`.
              name: editingSupplier.name, category: editingSupplier.category,
              phone: editingSupplier.details?.phone,
              contact_person: editingSupplier.details?.contact_person,
              address: editingSupplier.details?.address,
              gstin: editingSupplier.details?.gstin,
              payment_terms: editingSupplier.details?.payment_terms,
              remarks: editingSupplier.details?.remarks,
            }}
          />
        )}
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

// --- PurchasesPage.jsx ---
function PurchasesPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [purchases, setPurchases] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [locations, setLocations] = useState([]);
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate && !location.state?.bulkRows);
  const [showBulkAdd, setShowBulkAdd] = useState(!!location.state?.bulkRows?.length);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    purchasesAPI.list().then((res) => setPurchases(res.data)).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view purchases.' : 'Unable to load purchases. Please try again.');
    }).finally(() => setPageLoading(false));
    suppliersAPI.list().then((res) => setSuppliers(res.data));
    materialsAPI.list().then((res) => setMaterials(res.data));
    locationsAPI.list().then((res) => setLocations(res.data)).catch(() => setLocations([]));
  };
  useEffect(load, []);

  const handleReceive = async (purchaseId) => {
    setError('');
    try {
      await purchasesAPI.receive(purchaseId);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to mark this purchase as received');
    }
  };

  const [pendingDeletePurchase, setPendingDeletePurchase] = useState(null);
  const [deletingPurchase, setDeletingPurchase] = useState(false);
  const handleDeletePurchase = async () => {
    if (!pendingDeletePurchase) return;
    setDeletingPurchase(true);
    setError('');
    try {
      await purchasesAPI.remove(pendingDeletePurchase.id);
      setPendingDeletePurchase(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete this purchase.');
      setPendingDeletePurchase(null);
    } finally {
      setDeletingPurchase(false);
    }
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      // unit is a display-only "computed" field (see its definition
      // below) - Form.js never writes a computed field's value into
      // formData, so the actual request must derive it here too, from
      // the same source, or the submitted purchase would carry a
      // missing/blank unit.
      const selectedMaterial = materials.find((m) => String(m.id) === String(formData.material_id));
      await purchasesAPI.create({
        ...formData,
        supplier_id: Number(formData.supplier_id),
        material_id: Number(formData.material_id),
        quantity: formData.quantity, rate: formData.rate, unit: selectedMaterial?.unit || '',
        gst_percent: formData.gst_percent || '18',
        location_id: formData.location_id ? Number(formData.location_id) : null,
        date: new Date(formData.date).toISOString(),
      });
      setShowAdd(false);
      setSuccess('Purchase saved.');
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record purchase');
    } finally {
      setLoading(false);
    }
  };

  const emptyBulkRow = () => ({ material_id: '', quantity: '', rate: '', unit: '', location_id: '' });
  const [bulkSupplierId, setBulkSupplierId] = useState(location.state?.bulkRows?.[0]?.supplier_id || '');
  const [bulkDate, setBulkDate] = useState(today());
  const [bulkGstPercent, setBulkGstPercent] = useState('18');
  const [bulkPaymentStatus, setBulkPaymentStatus] = useState('Paid');
  const [bulkReceiptStatus, setBulkReceiptStatus] = useState('Received');
  const [bulkRows, setBulkRows] = useState(
    location.state?.bulkRows?.length
      ? location.state.bulkRows.map((r) => ({
          material_id: r.material_id || '', quantity: r.quantity || '', rate: r.rate || '',
          unit: r.unit || '', location_id: '',
        }))
      : [emptyBulkRow()]
  );
  const updateBulkRow = (index, field, value) => {
    setBulkRows((rows) => rows.map((r, i) => {
      if (i !== index) return r;
      const updated = { ...r, [field]: value };
      if (field === 'material_id') {
        const material = materials.find((m) => m.id === Number(value));
        if (material?.unit) updated.unit = material.unit;
      }
      return updated;
    }));
  };
  const addBulkRow = () => setBulkRows((rows) => [...rows, emptyBulkRow()]);
  const removeBulkRow = (index) => setBulkRows((rows) => rows.filter((_, i) => i !== index));

  const handleBulkCreate = async () => {
    setLoading(true);
    setError('');
    const validRows = bulkRows.filter((r) => r.material_id && r.quantity && r.rate && r.unit);
    if (!bulkSupplierId || validRows.length === 0) {
      setError('Pick a supplier and fill in at least one complete material row (material, quantity, rate, unit).');
      setLoading(false);
      return;
    }
    let created = 0;
    for (const row of validRows) {
      try {
        await purchasesAPI.create({
          supplier_id: Number(bulkSupplierId), material_id: Number(row.material_id),
          quantity: row.quantity, rate: row.rate, unit: row.unit,
          gst_percent: bulkGstPercent || '18',
          location_id: row.location_id ? Number(row.location_id) : null,
          date: new Date(bulkDate).toISOString(),
          payment_status: bulkPaymentStatus, receipt_status: bulkReceiptStatus,
        });
        created += 1;
      } catch (err) {
        setError(`Created ${created} of ${validRows.length} purchases, then stopped: ${err.response?.data?.detail || 'a purchase failed to save'}. The successfully-created ones above are already saved - fix the remaining rows and try again for just those.`);
        setLoading(false);
        load();
        return;
      }
    }
    setShowBulkAdd(false);
    setSuccess(`${created} purchase${created === 1 ? '' : 's'} saved from ${suppliers.find((s) => s.id === Number(bulkSupplierId))?.name || 'the supplier'}.`);
    setLoading(false);
    load();
  };
  const columns = [
    { key: 'purchase_code', label: 'Purchase ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'supplier_id', label: 'Supplier', render: (v) => suppliers.find((s) => s.id === v)?.name || v },
    { key: 'material_id', label: 'Material', render: (v) => materials.find((m) => m.id === v)?.name || v },
    { key: 'quantity', label: 'Quantity' }, { key: 'unit', label: 'Unit' }, { key: 'rate', label: 'Rate' },
    { key: 'invoice_total', label: 'Invoice Total', render: (v) => formatCurrency(v) },
    { key: 'payment_status', label: 'Payment Status' },
    { key: 'receipt_status', label: 'Receipt Status', render: (v) => (
      <span className={`status-badge ${statusClass(v)}`}>{v}</span>
    ) },
    { key: 'actions', label: '', render: (_, row) => (
      <>
        {row.receipt_status === 'Ordered' && (
          <button className="btn-link" onClick={(e) => { e.stopPropagation(); handleReceive(row.id); }}>Mark Received</button>
        )}
        {row.receipt_status !== 'Received' && (
          <button className="btn-link" onClick={(e) => { e.stopPropagation(); setPendingDeletePurchase(row); }}>Delete</button>
        )}
      </>
    ) },
  ];

  const fields = [
    { name: 'supplier_id', label: 'Supplier', type: 'select', required: true, section: 'Supplier & Invoice', options: suppliers.map((s) => ({ value: s.id, label: s.name })) },
    { name: 'date', label: 'Date', type: 'date', required: true, section: 'Supplier & Invoice' },
    { name: 'material_id', label: 'Material', type: 'select', required: true, section: 'Material', options: materials.map((m) => ({ value: m.id, label: m.name })) },
    { name: 'quantity', label: 'Quantity', type: 'number', required: true, section: 'Quantity & Cost' },
    {
      name: 'unit', label: 'Unit', section: 'Quantity & Cost', type: 'computed',
      // Genuinely locked to the selected Material's own recorded unit
      // - never free-typed (matches the same fix in InventoryPage.jsx's
      // Receive Stock wizard).
      compute: (formData) => materials.find((m) => String(m.id) === String(formData.material_id))?.unit || '',
    },
    { name: 'rate', label: 'Rate', type: 'number', required: true, section: 'Quantity & Cost' },
    { name: 'location_id', label: 'Receiving Location', type: 'select', section: 'Quantity & Cost',
      options: locations.map((l) => ({ value: l.id, label: l.full_path })), placeholder: "Material's primary location" },
    { name: 'gst_percent', label: 'GST %', type: 'number', placeholder: '18', section: 'Tax' },
    { name: 'payment_status', label: 'Payment Status', type: 'select', section: 'Payment', options: [
      { value: 'Paid', label: 'Paid' }, { value: 'Part Paid', label: 'Part Paid' }, { value: 'Credit', label: 'Credit' },
    ] },
    { name: 'receipt_status', label: 'Receipt Status', type: 'select', section: 'Payment', options: [
      { value: 'Received', label: 'Received - stock updates immediately' },
      { value: 'Ordered', label: 'Ordered - not yet arrived, stock stays unchanged until received' },
    ] },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Purchases (Stock In)</h1>
          <p className="page-summary">Record material receipts from suppliers and keep purchase history in one place.</p>
        </div>
        <div className="page-actions">
          {/* IA consolidation: Suppliers is no longer a separate
              primary Sidebar item - it's reached from here instead,
              since supplier management is part of the Purchases
              workflow. Same existing SuppliersPage/route, just a
              contextual entry point. */}
          <button className="btn-secondary" onClick={() => navigate('/suppliers')}>Suppliers</button>
          <a className="btn-secondary" href={reportsAPI.downloadUrl('purchases.xlsx')} target="_blank" rel="noreferrer">Export</a>
          {isPrivileged && <a className="btn-secondary" href={purchaseImportAPI.templateUrl}>Download Template</a>}
          {isPrivileged && <button className="btn-secondary" onClick={() => navigate('/purchases/import')}>Import Excel</button>}
          {isPrivileged && <button className="btn-secondary" onClick={() => setShowBulkAdd(true)}>Buy Multiple Items</button>}
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Record Purchase</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}
      <Table columns={columns} data={purchases} loading={pageLoading} error={loadError} onRetry={load} onRowClick={(row) => navigate(`/purchases/${row.id}`)} emptyMessage="No purchases recorded yet. Record your first purchase to start tracking inventory." emptyAction={isPrivileged ? { label: 'Record Purchase', onClick: () => setShowAdd(true) } : undefined} />

      <ConfirmDialog
        isOpen={!!pendingDeletePurchase}
        title="Delete Purchase"
        message={pendingDeletePurchase ? `Delete ${pendingDeletePurchase.purchase_code}? This cannot be undone.` : ''}
        onConfirm={handleDeletePurchase}
        onCancel={() => setPendingDeletePurchase(null)}
        loading={deletingPurchase}
      />
      <Modal isOpen={showAdd} title="Record Purchase" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Record Purchase"
          initialValues={{ date: today(), ...(location.state?.prefill || {}) }} />
      </Modal>
      <Modal isOpen={showBulkAdd} title="Buy Multiple Items From One Supplier" onClose={() => setShowBulkAdd(false)}>
        <div className="bulk-purchase-form">
          <p className="page-summary" style={{ marginBottom: 'var(--space-4)' }}>
            One supplier, one invoice date - as many materials as you need. Each row is saved as its own purchase record.
          </p>
          <div className="bulk-purchase-shared-fields">
            <label>
              Supplier
              <select value={bulkSupplierId} onChange={(e) => setBulkSupplierId(e.target.value)}>
                <option value="">Select supplier...</option>
                {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label>
              Date
              <input type="date" value={bulkDate} onChange={(e) => setBulkDate(e.target.value)} />
            </label>
            <label>
              GST %
              <input type="number" value={bulkGstPercent} onChange={(e) => setBulkGstPercent(e.target.value)} placeholder="18" />
            </label>
            <label>
              Payment Status
              <select value={bulkPaymentStatus} onChange={(e) => setBulkPaymentStatus(e.target.value)}>
                <option value="Paid">Paid</option>
                <option value="Part Paid">Part Paid</option>
                <option value="Credit">Credit</option>
              </select>
            </label>
            <label>
              Receipt Status
              <select value={bulkReceiptStatus} onChange={(e) => setBulkReceiptStatus(e.target.value)}>
                <option value="Received">Received - stock updates immediately</option>
                <option value="Ordered">Ordered - not yet arrived</option>
              </select>
            </label>
          </div>

          <div className="bulk-purchase-rows">
            {bulkRows.map((row, i) => (
              <div className="bulk-purchase-row" key={i}>
                <select value={row.material_id} onChange={(e) => updateBulkRow(i, 'material_id', e.target.value)}>
                  <option value="">Select material...</option>
                  {materials.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
                <input type="number" placeholder="Qty" value={row.quantity} onChange={(e) => updateBulkRow(i, 'quantity', e.target.value)} />
                <input placeholder="Unit" value={row.unit} readOnly disabled className="form-input-readonly" title="Set automatically from the selected material" />
                <input type="number" placeholder="Rate" value={row.rate} onChange={(e) => updateBulkRow(i, 'rate', e.target.value)} />
                <select value={row.location_id} onChange={(e) => updateBulkRow(i, 'location_id', e.target.value)}>
                  <option value="">Location...</option>
                  {locations.map((l) => <option key={l.id} value={l.id}>{l.full_path}</option>)}
                </select>
                <button type="button" className="cart-drawer-remove" onClick={() => removeBulkRow(i)} aria-label="Remove row" disabled={bulkRows.length === 1}>
                  &times;
                </button>
              </div>
            ))}
          </div>
          <button type="button" className="btn-secondary" onClick={addBulkRow}>+ Add Another Material</button>

          <div className="bulk-purchase-actions">
            <button type="button" className="btn-primary" onClick={handleBulkCreate} disabled={loading}>
              {loading ? 'Saving...' : `Save ${bulkRows.filter((r) => r.material_id && r.quantity && r.rate && r.unit).length || ''} Purchase${bulkRows.length === 1 ? '' : 's'}`}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// --- PurchaseDetailPage.jsx ---
function PurchaseDetailPage() {
  const { purchaseId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [purchase, setPurchase] = useState(null);
  const [supplier, setSupplier] = useState(null);
  const [material, setMaterial] = useState(null);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState(null);

  const load = useCallback(() => {
    setLoadError(null);
    purchasesAPI.get(purchaseId).then((res) => {
      setPurchase(res.data);
      if (res.data.supplier_id) suppliersAPI.get(res.data.supplier_id).then((r) => setSupplier(r.data)).catch(() => setSupplier('error'));
      if (res.data.material_id) materialsAPI.get(res.data.material_id).then((r) => setMaterial(r.data)).catch(() => setMaterial('error'));
    }).catch((err) => setLoadError(classifyLoadError(err, 'purchase')));
  }, [purchaseId]);

  useEffect(load, [load]);

  const [receiving, setReceiving] = useState(false);
  const handleReceive = async () => {
    // This business-critical mutation
    // (marking a purchase received) had no in-flight guard on its own
    // button, unlike every other action button on this same page
    // (handleBulkCreate/handlePreview/handleCommit above, all
    // disabled={loading}) - a double-click or an impatient second
    // click during a slow network round trip could fire
    // purchasesAPI.receive() twice.
    setReceiving(true);
    setError('');
    try {
      await purchasesAPI.receive(purchaseId);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to mark this purchase as received');
    } finally {
      setReceiving(false);
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
  if (!purchase) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{purchase.purchase_code}</h1>
          <div className="detail-subtitle">
            {supplier === 'error' ? 'Supplier unavailable' : (supplier?.name || 'Supplier')} &middot; {material === 'error' ? 'Material unavailable' : (material?.name || 'Material')}
            {' '}<span className={`status-badge ${purchase.receipt_status === 'Ordered' ? 'status-warning' : 'status-ok'}`}>{purchase.receipt_status}</span>
            {purchase.business_id && <span className="business-id-badge">{purchase.business_id}</span>}
          </div>
        </div>
        {purchase.receipt_status === 'Ordered' && (
          <div className="detail-header-actions">
            <button className="btn-primary" onClick={handleReceive} disabled={receiving}>{receiving ? 'Marking...' : 'Mark Received'}</button>
          </div>
        )}
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Quantity</div><h3>{Number(purchase.quantity)} {purchase.unit}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Rate</div><h3>{formatCurrency(purchase.rate)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">GST ({Number(purchase.gst_percent)}%)</div><h3>{formatCurrency(purchase.gst_amount)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Invoice Total</div><h3>{formatCurrency(purchase.invoice_total)}</h3></div></Card>
      </div>

      <Card title="Purchase Details">
        <div className="card-body">
          <div className="detail-meta">
            <div className="detail-meta-item">
              <span className="detail-meta-label">Date</span>
              <span className="detail-meta-value">{new Date(purchase.date).toLocaleDateString()}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Supplier</span>
              <span className="detail-meta-value">{supplier === 'error' ? 'Unavailable' : (supplier?.name || '-')}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Material</span>
              <span className="detail-meta-value">{material === 'error' ? 'Unavailable' : (material?.name || '-')}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Taxable Value</span>
              <span className="detail-meta-value">{formatCurrency(purchase.taxable_value)}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Payment Status</span>
              <span className={`status-badge ${statusClass(purchase.payment_status)}`}>{purchase.payment_status}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Receipt Status</span>
              <span className={`status-badge ${purchase.receipt_status === 'Ordered' ? 'status-warning' : 'status-ok'}`}>{purchase.receipt_status}</span>
            </div>
          </div>
        </div>
      </Card>

      {isPrivileged && (
        <DocumentsPanel title="Documents" api={{
          list: () => documentsAPI.list('purchase', purchaseId),
          upload: (file, description) => documentsAPI.upload('purchase', purchaseId, file, description),
          downloadUrl: (documentId) => documentsAPI.downloadUrl('purchase', purchaseId, documentId),
          remove: (documentId) => documentsAPI.remove('purchase', purchaseId, documentId),
        }} canUpload={isPrivileged} />
      )}
    </div>
  );
}

// --- PurchaseImportPage.jsx ---
function PurchaseImportPage() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({}); // row_number -> true if user opted out
  const [createDecisions, setCreateDecisions] = useState({}); // row_number -> bool, for new-material rows
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [downloadingErrors, setDownloadingErrors] = useState(false);

  const handleFileChange = (e) => {
    setFile(e.target.files[0] || null);
    setPreview(null);
    setResult(null);
    setError('');
  };

  const handlePreview = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    try {
      const res = await purchaseImportAPI.preview(file);
      setPreview(res.data);
      // Default: include every error-free row; default new materials to "create"
      const decisions = {};
      res.data.rows.forEach((r) => { if (r.is_new_material) decisions[r.row_number] = true; });
      setCreateDecisions(decisions);
      setExcludedRows({});
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not read this file. Make sure you used the downloaded template.');
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!preview) return;
    setLoading(true);
    setError('');
    try {
      const rowsToCommit = preview.rows
        .filter((r) => r.errors.length === 0 && !excludedRows[r.row_number])
        .map((r) => ({
          material_name: r.material_name, specification: r.specification,
          matched_material_id: r.matched_material_id, matched_supplier_id: r.matched_supplier_id,
          quantity: r.quantity, unit: r.unit, rate: r.rate, gst_percent: r.gst_percent || '0',
          invoice_date: r.invoice_date, remarks: r.remarks,
          create_new_material: r.is_new_material ? !!createDecisions[r.row_number] : false,
        }))
        .filter((r) => r.matched_material_id || r.create_new_material);

      const res = await purchaseImportAPI.commit(rowsToCommit);
      setResult(res.data);
      setPreview(null);
      setFile(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  const downloadErrorReport = async () => {
    if (!file) return;
    setDownloadingErrors(true);
    setError('');
    try {
      const res = await purchaseImportAPI.errorReport(file);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Purchase_Import_Errors.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not generate the error report. Please try again.');
    } finally {
      setDownloadingErrors(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Import Purchases from Excel</h1>
          <p className="page-summary">
            Download the template, fill in one row per material purchased, then upload it here for review
            before anything is saved.
          </p>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {result && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>Import Complete</h3>
            <p>
              {result.created_purchases} purchase{result.created_purchases !== 1 ? 's' : ''} created
              {result.created_materials > 0 && `, ${result.created_materials} new material${result.created_materials !== 1 ? 's' : ''} added`}.
            </p>
            {result.error && <Alert type="warning" message={result.error} />}
          </div>
        </Card>
      )}

      {!preview && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={purchaseImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
                Download Template
              </a>
            </p>
            <div style={{ marginTop: 16 }}>
              <input type="file" accept=".xlsx" onChange={handleFileChange} />
            </div>
            <button className="btn-primary" style={{ marginTop: 16 }} onClick={handlePreview} disabled={!file || loading}>
              {loading ? 'Reading file...' : 'Preview Import'}
            </button>
          </div>
        </Card>
      )}

      {preview && (
        <>
          <Card>
            <div className="card-body">
              <h3 style={{ marginTop: 0 }}>{preview.total_rows} rows detected</h3>
              <p>
                {preview.matched_rows} matched existing material &middot; {preview.new_material_rows} new material{preview.new_material_rows !== 1 ? 's' : ''} detected &middot;{' '}
                {preview.error_rows} row{preview.error_rows !== 1 ? 's' : ''} with errors
                {preview.error_rows > 0 ? ' (won\'t be imported)' : ''}.
              </p>
              {preview.error_rows > 0 && (
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
                <th></th><th>Material</th><th>Qty</th><th>Unit</th><th>Supplier</th>
                <th>Rate</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r) => (
                <tr key={r.row_number} style={{ opacity: excludedRows[r.row_number] ? 0.5 : 1 }}>
                  <td>
                    {r.errors.length === 0 && (
                      <input
                        type="checkbox" checked={!excludedRows[r.row_number]}
                        onChange={(e) => setExcludedRows((prev) => ({ ...prev, [r.row_number]: !e.target.checked }))}
                      />
                    )}
                  </td>
                  <td>{r.material_name}</td>
                  <td>{r.quantity != null ? Number(r.quantity) : '-'}</td>
                  <td>{r.unit}</td>
                  <td>{r.supplier_name}</td>
                  <td>{r.rate != null ? formatCurrency(r.rate) : '-'}</td>
                  <td>
                    {r.errors.length > 0 ? (
                      <span className="status-badge status-danger">{r.errors.join('; ')}</span>
                    ) : r.is_new_material ? (
                      <label style={{ fontSize: '0.8rem' }}>
                        <input
                          type="checkbox" checked={!!createDecisions[r.row_number]}
                          onChange={(e) => setCreateDecisions((prev) => ({ ...prev, [r.row_number]: e.target.checked }))}
                        />{' '}
                        New - Create Material
                      </label>
                    ) : (
                      <span className="status-badge status-ok">Matched</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>

          <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
            <button className="btn-primary" onClick={handleCommit} disabled={loading}>
              {loading ? 'Importing...' : 'Confirm Import'}
            </button>
            <button className="btn-secondary" onClick={() => { setPreview(null); setFile(null); }}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}

// --- PurchasesProcurementHub.jsx ---
// Woodful navigation/module-structure consolidation: Purchases and
// Procurement Requirements used to be two separate primary Sidebar
// destinations under Inventory. They are now one "Purchases &
// Procurement" workspace reached from a single nav item
// (/purchases-procurement), following the exact same thin
// tab-switcher pattern already established by AttendanceLeaveHub
// (hr/pages/WorkforcePages.jsx) and RecruitmentHub
// (recruitment/pages/RecruitmentPages.jsx): the same existing page
// components, same API calls, same data-loading, same role checks -
// only the selected tab is mounted at a time, so switching tabs never
// fetches more than one tab's data at once (no new/duplicate network
// traffic versus visiting each page directly). /purchases,
// /procurement-requirements, and /suppliers all keep working exactly
// as before - this hub does not replace or redirect them, and
// PurchasesPage's own existing "Suppliers" quick-link (which deep-links
// straight to /suppliers) is untouched.
//
// Suppliers is included as a third tab - not just reachable via that
// quick-link - because the agreed navigation groups Purchases +
// Procurement Requirements + Suppliers under one workspace.
const PURCHASES_PROCUREMENT_TABS = ['Purchases', 'Procurement Requirements', 'Suppliers'];

function PurchasesProcurementHub() {
  const [tab, setTab] = useState('Purchases');
  return (
    <div className="page purchases-procurement-hub">
      <div className="page-header">
        <div>
          <h1>Purchases &amp; Procurement</h1>
          <p className="page-summary">Purchases, procurement requirements, and suppliers in one place.</p>
        </div>
      </div>
      <div className="tab-bar">
        {PURCHASES_PROCUREMENT_TABS.map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)} type="button">{t}</button>
        ))}
      </div>
      {tab === 'Purchases' && <PurchasesPage />}
      {tab === 'Procurement Requirements' && <ProcurementRequirementsPage />}
      {tab === 'Suppliers' && <SuppliersPage />}
    </div>
  );
}

export { SuppliersPage, PurchasesPage, PurchaseDetailPage, PurchaseImportPage, PurchasesProcurementHub };
