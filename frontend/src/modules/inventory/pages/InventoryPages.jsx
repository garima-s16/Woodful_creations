// Inventory list pages: inventory overview and materials list.
// Combines the former InventoryPage.jsx and MaterialsPage.jsx.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { MaterialAttributesEditor } from './MaterialPages';
import { useLocation, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { dashboardAPI, issuesAPI, locationsAPI, materialCategoriesAPI, materialsAPI, ordersAPI, purchasesAPI, reportsAPI, stockAPI, suppliersAPI } from '../../../utils/api';
import { Alert, Card, ConfirmDialog, Form, KpiCard, MaterialCard, Modal, Pagination, Table } from '../../../components/common/UI';
import { formatCurrency, formatNumber, statusClass, today } from '../../../utils/utils';
import { addToCart } from '../../../redux/slices';
import { CartIcon, GridIcon, ListIcon, SearchIcon, SlidersIcon } from '../../../components/icons';
import '../../../styles/modules.css';

// --- InventoryPage.jsx ---
// The single operational home for inventory. Every
// section below is a VIEW over the existing Material/Purchase/Issue/
// Location/StockService backend - no new stock table, no new stock
// calculation, no new purchase/issue system. See:
//   /api/dashboard/stock            - overview + purchase-required (A2, A8)
//   /api/materials                  - stock list (A3)
//   /api/stock/ledger, /api/stock/locations/{id} - movements + locations (A4, A7)
//   /api/purchases, /api/issues     - stock in / stock out (A5, A6)
//   /api/stock/transfers, /adjustments - master-only stock ops (A9, A10)
const ALL_TABS = ['Overview', 'Stock', 'Movements', 'Purchases', 'Issues', 'Locations', 'Purchase Required'];

function InventoryPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isMaster = user?.role === 'master';

  // Purchases (list) is master-only on the backend (require_role("master")
  // in app/api/routes/purchases.py) - so a normal user never even sees
  // that tab, rather than seeing it and hitting a 403 (A9, A10).
  const tabs = isMaster ? ALL_TABS : ALL_TABS.filter((t) => t !== 'Purchases');
  const [tab, setTab] = useState('Overview');

  const [overview, setOverview] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(true);

  const [materials, setMaterials] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [locations, setLocations] = useState([]);
  const [materialsLoading, setMaterialsLoading] = useState(true);
  // Defect repair (F138 P4.3): the Stock/Purchases/Issues tabs below
  // previously had no error state at all - a load failure silently
  // wiped whatever was already showing down to "No materials match
  // these filters." / "No purchases recorded yet." / "No issues
  // recorded yet." with no indication anything had gone wrong and no
  // way to retry, unlike the Movements tab's ledgerError/onRetryLedger
  // right below, which already follows this codebase's established
  // error/onRetry-on-Table convention.
  const [materialsError, setMaterialsError] = useState(false);

  const [purchases, setPurchases] = useState([]);
  const [purchasesLoading, setPurchasesLoading] = useState(false);
  const [purchasesError, setPurchasesError] = useState(false);
  const [pendingDeletePurchase, setPendingDeletePurchase] = useState(null);
  const [deletingPurchase, setDeletingPurchase] = useState(false);
  const [issuesError, setIssuesError] = useState(false);
  const [issues, setIssues] = useState([]);
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [orders, setOrders] = useState([]);

  const [error, setError] = useState('');

  // Stock view filters (A3) - search/category/active_only go to the
  // existing materials API server-side; location/status filter the
  // already-returned rows client-side (no duplicate stock calculation,
  // just filtering fields the backend already computed).
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Movements (A4)
  const [ledgerMaterialId, setLedgerMaterialId] = useState('');
  const [ledgerEntries, setLedgerEntries] = useState([]);
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [ledgerError, setLedgerError] = useState(false);

  // Locations (A7)
  const [locationMaterialId, setLocationMaterialId] = useState('');
  const [locationBreakdown, setLocationBreakdown] = useState(null);
  const [locationBreakdownLoading, setLocationBreakdownLoading] = useState(false);

  // Quick actions - Adjust / Transfer (A9), master-only (A10), reusing
  // the exact same stockAPI.adjust / stockAPI.transfer calls already
  // used on MaterialDetailPage, just with a material picker up front
  // since Inventory isn't scoped to one material.
  const [showAdjust, setShowAdjust] = useState(false);
  const [showTransfer, setShowTransfer] = useState(false);
  const [showReceive, setShowReceive] = useState(false);
  const [showIssue, setShowIssue] = useState(false);
  const [actionMaterial, setActionMaterial] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadOverview = useCallback(() => {
    setOverviewLoading(true);
    dashboardAPI.stock().then((res) => setOverview(res.data)).catch(() => setOverview(null))
      .finally(() => setOverviewLoading(false));
  }, []);

  const loadMaterials = useCallback(() => {
    setMaterialsLoading(true);
    setMaterialsError(false);
    materialsAPI.list({ active_only: true }).then((res) => setMaterials(res.data)).catch(() => { setMaterials([]); setMaterialsError(true); })
      .finally(() => setMaterialsLoading(false));
  }, []);

  const loadPurchases = useCallback(() => {
    if (!isMaster) return;
    setPurchasesLoading(true);
    setPurchasesError(false);
    purchasesAPI.list().then((res) => setPurchases(res.data)).catch(() => { setPurchases([]); setPurchasesError(true); })
      .finally(() => setPurchasesLoading(false));
  }, [isMaster]);

  const loadIssues = useCallback(() => {
    setIssuesLoading(true);
    setIssuesError(false);
    issuesAPI.list().then((res) => setIssues(res.data)).catch(() => { setIssues([]); setIssuesError(true); }).finally(() => setIssuesLoading(false));
  }, []);

  useEffect(loadOverview, [loadOverview]);
  useEffect(loadMaterials, [loadMaterials]);
  useEffect(loadPurchases, [loadPurchases]);
  useEffect(loadIssues, [loadIssues]);

  // Suppliers/locations/orders are reference data for the adjust/
  // transfer/receive/issue action forms, not tied to any one
  // material - fetched once per page visit rather than on every
  // refreshAll() (every stock action taken on this page).
  useEffect(() => {
    suppliersAPI.list().then((res) => setSuppliers(res.data)).catch(() => setSuppliers([]));
    locationsAPI.list().then((res) => setLocations(res.data)).catch(() => setLocations([]));
    ordersAPI.list().then((res) => setOrders(res.data)).catch(() => setOrders([]));
  }, []);

  const refreshAll = () => { loadOverview(); loadMaterials(); loadPurchases(); loadIssues(); };

  // Server-side search/category (same params the existing Materials page
  // already sends to this same endpoint).
  useEffect(() => {
    const timer = setTimeout(() => {
      setMaterialsLoading(true);
      setMaterialsError(false);
      const params = { active_only: true };
      if (search) params.search = search;
      if (categoryFilter) params.category = categoryFilter;
      if (statusFilter === 'LOW STOCK' || statusFilter === 'OUT OF STOCK') params.low_stock_only = true;
      materialsAPI.list(params).then((res) => setMaterials(res.data)).catch(() => { setMaterials([]); setMaterialsError(true); })
        .finally(() => setMaterialsLoading(false));
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, categoryFilter, statusFilter]);

  const categories = useMemo(() => [...new Set(materials.map((m) => m.category).filter(Boolean))].sort(), [materials]);

  const visibleStock = useMemo(() => materials.filter((m) => {
    if (locationFilter && String(m.location_id || '') !== locationFilter) return false;
    if (statusFilter && m.stock_status !== statusFilter) return false;
    return true;
  }), [materials, locationFilter, statusFilter]);

  const supplierName = (id) => suppliers.find((s) => s.id === id)?.name;
  const locationName = (id) => locations.find((l) => l.id === id)?.full_path;

  const loadLedger = (materialId) => {
    setLedgerMaterialId(materialId);
    if (!materialId) { setLedgerEntries([]); setLedgerError(false); return; }
    setLedgerLoading(true);
    setLedgerError(false);
    stockAPI.ledger(materialId).then((res) => setLedgerEntries(res.data)).catch(() => { setLedgerEntries([]); setLedgerError(true); })
      .finally(() => setLedgerLoading(false));
  };

  const loadLocationBreakdown = (materialId) => {
    setLocationMaterialId(materialId);
    if (!materialId) { setLocationBreakdown(null); return; }
    setLocationBreakdownLoading(true);
    stockAPI.locationStock(materialId).then((res) => setLocationBreakdown(res.data)).catch(() => setLocationBreakdown(null))
      .finally(() => setLocationBreakdownLoading(false));
  };

  const openAdjust = (material) => { setActionMaterial(material); setError(''); setShowAdjust(true); };
  const openTransfer = (material) => { setActionMaterial(material); setError(''); setShowTransfer(true); };

  const handleAdjust = async (formData) => {
    setActionLoading(true);
    setError('');
    try {
      const isReturn = formData.adjustment_type === 'Return from Issue';
      const delta = isReturn
        ? Math.abs(Number(formData.quantity))
        : (formData.direction === 'decrease' ? -Math.abs(Number(formData.quantity)) : Math.abs(Number(formData.quantity)));
      await stockAPI.adjust({
        material_id: actionMaterial.id, adjustment_type: formData.adjustment_type,
        quantity_delta: delta, reason: formData.reason,
        related_issue_id: isReturn ? Number(formData.related_issue_id) : undefined,
        location_id: formData.location_id ? Number(formData.location_id) : undefined,
      });
      setShowAdjust(false);
      refreshAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Adjustment failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleTransfer = async (formData) => {
    setActionLoading(true);
    setError('');
    try {
      await stockAPI.transfer({
        material_id: actionMaterial.id, quantity: Number(formData.quantity),
        to_location_id: Number(formData.to_location_id),
        from_location_id: formData.from_location_id ? Number(formData.from_location_id) : undefined,
        remarks: formData.remarks,
      });
      setShowTransfer(false);
      refreshAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Transfer failed');
    } finally {
      setActionLoading(false);
    }
  };

  const openReceive = (material) => { setActionMaterial(material || null); setError(''); setShowReceive(true); };
  const openIssue = (material) => { setActionMaterial(material || null); setError(''); setShowIssue(true); };

  const handleReceive = async (formData) => {
    setActionLoading(true);
    setError('');
    try {
      // unit is a display-only "computed" field (see its definition
      // below) - it is never actually written into formData by Form.js
      // (only fields with a real onChange are), so it must be derived
      // here too, from the same source, to make sure the real request
      // actually carries the material's own unit rather than
      // submitting it as missing/blank.
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
      setShowReceive(false);
      refreshAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record purchase');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeletePurchase = async () => {
    if (!pendingDeletePurchase) return;
    setDeletingPurchase(true);
    setError('');
    try {
      await purchasesAPI.remove(pendingDeletePurchase.id);
      setPendingDeletePurchase(null);
      refreshAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete this purchase.');
      setPendingDeletePurchase(null);
    } finally {
      setDeletingPurchase(false);
    }
  };

  const handleIssue = async (formData) => {
    setActionLoading(true);
    setError('');
    try {
      // unit is a display-only "computed" field (see its definition
      // below, and handleReceive's identical comment above) - never
      // actually written into formData by Form.js, so it must be
      // derived here too from the same source, or the request would
      // carry it as missing/blank and fail record_issue's unit-match
      // validation even though the form visibly showed the right unit.
      const selectedMaterial = materials.find((m) => String(m.id) === String(formData.material_id));
      await issuesAPI.create({
        ...formData,
        material_id: Number(formData.material_id),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        location_id: formData.location_id ? Number(formData.location_id) : null,
        date: new Date(formData.date).toISOString(),
        unit: selectedMaterial?.unit || '',
      });
      setShowIssue(false);
      refreshAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record issue');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Inventory</h1>
          <p className="page-summary">The single operational home for stock - current levels, movements, receipts, issues, locations and what needs reordering.</p>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="tab-bar">
        {tabs.map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && (
        <OverviewTab
          overview={overview} loading={overviewLoading} isMaster={isMaster}
          onOpenPurchaseRequired={() => setTab('Purchase Required')}
          onOpenStock={(status) => { setStatusFilter(status || ''); setTab('Stock'); }}
        />
      )}

      {tab === 'Stock' && (
        <StockTab
          materials={visibleStock} loading={materialsLoading} error={materialsError} onRetry={() => loadMaterials()} isMaster={isMaster}
          search={search} setSearch={setSearch}
          categoryFilter={categoryFilter} setCategoryFilter={setCategoryFilter} categories={categories}
          locationFilter={locationFilter} setLocationFilter={setLocationFilter} locations={locations}
          statusFilter={statusFilter} setStatusFilter={setStatusFilter}
          supplierName={supplierName}
          onOpenMaterial={(m) => navigate(`/materials/${m.id}`)}
          onAdjust={openAdjust} onTransfer={openTransfer}
          onViewLedger={(m) => { setTab('Movements'); loadLedger(String(m.id)); }}
          onViewLocations={(m) => { setTab('Locations'); loadLocationBreakdown(String(m.id)); }}
          onReceive={openReceive} onIssue={openIssue}
        />
      )}

      {tab === 'Movements' && (
        <MovementsTab
          recent={overview?.recent_stock_movement || []}
          materials={materials}
          ledgerMaterialId={ledgerMaterialId} onSelectMaterial={loadLedger}
          ledgerEntries={ledgerEntries} ledgerLoading={ledgerLoading} ledgerError={ledgerError}
          onRetryLedger={() => loadLedger(ledgerMaterialId)}
          locationName={locationName}
        />
      )}

      {tab === 'Purchases' && isMaster && (
        <PurchasesTab
          purchases={purchases} loading={purchasesLoading} error={purchasesError} onRetry={loadPurchases}
          materials={materials} suppliers={suppliers}
          onOpen={(p) => navigate(`/purchases/${p.id}`)}
          onReceiveStock={() => openReceive()}
          onDelete={(p) => setPendingDeletePurchase(p)}
        />
      )}

      <ConfirmDialog
        isOpen={!!pendingDeletePurchase}
        title="Delete Purchase"
        message={pendingDeletePurchase ? `Delete ${pendingDeletePurchase.purchase_code}? This cannot be undone.` : ''}
        onConfirm={handleDeletePurchase}
        onCancel={() => setPendingDeletePurchase(null)}
        loading={deletingPurchase}
      />

      {tab === 'Issues' && (
        <IssuesTab
          issues={issues} loading={issuesLoading} error={issuesError} onRetry={loadIssues} isMaster={isMaster}
          materials={materials} orders={orders}
          onIssueStock={() => openIssue()}
        />
      )}

      {tab === 'Locations' && (
        <LocationsTab
          locations={locations} materials={materials}
          locationMaterialId={locationMaterialId} onSelectMaterial={loadLocationBreakdown}
          breakdown={locationBreakdown} loading={locationBreakdownLoading}
        />
      )}

      {tab === 'Purchase Required' && (
        <PurchaseRequiredTab
          items={overview?.low_stock_action_list || []} loading={overviewLoading} isMaster={isMaster}
          onOrder={(item) => openReceive(materials.find((m) => m.id === item.id) || { id: item.id, unit: '' })}
        />
      )}

      {actionMaterial && (
        <Modal isOpen={showAdjust} title={`Adjust Stock - ${actionMaterial.name}`} onClose={() => setShowAdjust(false)}>
          <p style={{ marginTop: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Current stock: {actionMaterial.current_stock} {actionMaterial.unit}. Every adjustment is recorded with a reason.
          </p>
          <Form
            fields={[
              { name: 'adjustment_type', label: 'Type', type: 'select', required: true, options: [
                { value: 'Physical Count Increase', label: 'Physical Count Increase' },
                { value: 'Physical Count Decrease', label: 'Physical Count Decrease' },
                { value: 'Damage', label: 'Damage' },
                { value: 'Wastage', label: 'Wastage' },
                { value: 'Theft/Loss', label: 'Theft/Loss' },
                { value: 'Correction', label: 'Correction' },
                { value: 'Return from Issue', label: 'Return from Issue' },
              ] },
              { name: 'related_issue_id', label: 'Issue Being Returned Against', type: 'select',
                visibleIf: (fd) => fd.adjustment_type === 'Return from Issue', required: true,
                options: issues.filter((i) => i.material_id === actionMaterial.id).map((i) => ({
                  value: i.id, label: `${i.issue_code} - ${i.quantity_issued} ${actionMaterial.unit} (${new Date(i.date).toLocaleDateString()})`,
                })) },
              { name: 'direction', label: 'Direction', type: 'select', required: true,
                visibleIf: (fd) => fd.adjustment_type !== 'Return from Issue',
                options: [{ value: 'increase', label: 'Increase stock' }, { value: 'decrease', label: 'Decrease stock' }] },
              { name: 'quantity', label: `Quantity (${actionMaterial.unit})`, type: 'number', required: true },
              { name: 'location_id', label: 'Location', type: 'select',
                options: locations.map((l) => ({ value: l.id, label: l.full_path })),
                placeholder: actionMaterial.location || 'Primary location' },
              { name: 'reason', label: 'Reason', type: 'textarea', required: true },
            ]}
            onSubmit={handleAdjust} loading={actionLoading} submitText="Confirm Adjustment"
          />
        </Modal>
      )}

      {actionMaterial && (
        <Modal isOpen={showTransfer} title={`Transfer ${actionMaterial.name}`} onClose={() => setShowTransfer(false)}>
          <p style={{ marginTop: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Current stock: {actionMaterial.current_stock} {actionMaterial.unit} at {actionMaterial.location || 'no location set'}.
          </p>
          <Form
            fields={[
              { name: 'to_location_id', label: 'Transfer To', type: 'select', required: true, options: locations.map((l) => ({ value: l.id, label: l.full_path })) },
              { name: 'from_location_id', label: 'Transfer From', type: 'select',
                options: locations.map((l) => ({ value: l.id, label: l.full_path })), placeholder: actionMaterial.location || 'Primary location' },
              { name: 'quantity', label: `Quantity (${actionMaterial.unit})`, type: 'number', required: true },
              { name: 'remarks', label: 'Remarks', type: 'textarea' },
            ]}
            onSubmit={handleTransfer} loading={actionLoading} submitText="Confirm Transfer"
          />
        </Modal>
      )}

      <Modal isOpen={showReceive} title={actionMaterial ? `Receive Stock - ${actionMaterial.name}` : 'Receive Stock'} onClose={() => setShowReceive(false)}>
        <Form
          fields={[
            { name: 'supplier_id', label: 'Supplier', type: 'select', required: true, section: 'Supplier & Invoice', options: suppliers.map((s) => ({ value: s.id, label: s.name })) },
            { name: 'date', label: 'Date', type: 'date', required: true, section: 'Supplier & Invoice' },
            { name: 'material_id', label: 'Material', type: 'select', required: true, section: 'Material', options: materials.map((m) => ({ value: m.id, label: m.name })) },
            { name: 'quantity', label: 'Quantity', type: 'number', required: true, section: 'Quantity & Cost' },
            {
              name: 'unit', label: 'Unit', section: 'Quantity & Cost', type: 'computed',
              // Genuinely locked to the selected Material's own
              // recorded unit (e.g. "Sheets"/"Sets"/"Litres") - never
              // free-typed, so it can't silently diverge into
              // something like the quantity value itself being typed
              // in by mistake. Falls back to the placeholder text
              // only until a material is actually chosen.
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
          ]}
          onSubmit={handleReceive} loading={actionLoading} submitText="Record Purchase"
          initialValues={{ date: today(), ...(actionMaterial ? { material_id: actionMaterial.id, unit: actionMaterial.unit } : {}) }}
        />
      </Modal>

      <Modal isOpen={showIssue} title={actionMaterial ? `Issue Stock - ${actionMaterial.name}` : 'Issue Stock'} onClose={() => setShowIssue(false)}>
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'material_id', label: 'Material', type: 'select', required: true, options: materials.map((m) => ({ value: m.id, label: `${m.name} (${m.current_stock} in stock)` })) },
            { name: 'order_id', label: 'Order (Project)', type: 'select', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
            { name: 'quantity_issued', label: 'Quantity Issued', type: 'number', required: true },
            {
              name: 'unit', label: 'Unit', type: 'computed',
              // Defect repair (F138 P21 API-contract audit): this was a
              // free-typed text field seeded once from the pre-selected
              // material's unit, so switching the Material dropdown
              // after opening (or typing something else) could easily
              // leave it out of sync - and record_issue's own strict
              // exact-match validation against the material's real unit
              // (see inventory/services.py) then rejects the submission.
              // Locked the same way the Receive Stock form's own unit
              // field already is: always the currently-selected
              // material's actual unit, never independently editable.
              compute: (formData) => materials.find((m) => String(m.id) === String(formData.material_id))?.unit || '',
            },
            { name: 'location_id', label: 'Issue From Location', type: 'select', options: locations.map((l) => ({ value: l.id, label: l.full_path })), placeholder: 'Primary location' },
            { name: 'issued_to', label: 'Issued To' },
            { name: 'department', label: 'Department' },
            { name: 'purpose', label: 'Purpose' },
            { name: 'approved_by', label: 'Approved By' },
          ]}
          onSubmit={handleIssue} loading={actionLoading} submitText="Record Issue"
          initialValues={{ date: today(), ...(actionMaterial ? { material_id: actionMaterial.id, unit: actionMaterial.unit } : {}) }}
        />
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------------
// A2 - Overview
// ---------------------------------------------------------------------
function OverviewTab({ overview, loading, isMaster, onOpenPurchaseRequired, onOpenStock }) {
  if (loading) return <div className="table-container"><p style={{ padding: 'var(--space-4)' }}>Loading overview...</p></div>;
  if (!overview) return <Alert type="error" message="Unable to load the inventory overview." onClose={() => {}} />;

  return (
    <>
      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Total Materials</div><h3>{formatNumber((overview.category_summary || []).reduce((s, c) => s + c.items, 0))}</h3></div></Card>
        {isMaster && (
          <Card><div className="card-body"><div className="detail-meta-label">Total Stock Value</div><h3>{formatCurrency(overview.total_stock_value)}</h3></div></Card>
        )}
        <Card className="kpi-warning"><div className="card-body" onClick={() => onOpenStock('LOW STOCK')} style={{ cursor: 'pointer' }}><div className="detail-meta-label">Low Stock</div><h3>{overview.low_stock_items}</h3></div></Card>
        <Card className="kpi-danger"><div className="card-body" onClick={() => onOpenStock('OUT OF STOCK')} style={{ cursor: 'pointer' }}><div className="detail-meta-label">Out of Stock</div><h3>{overview.out_of_stock_items}</h3></div></Card>
        <Card><div className="card-body" onClick={onOpenPurchaseRequired} style={{ cursor: 'pointer' }}><div className="detail-meta-label">Purchase Required</div><h3>{(overview.low_stock_action_list || []).length}</h3></div></Card>
      </div>

      <Card title="Recent Stock Movements">
        <RecentMovementsTable rows={overview.recent_stock_movement || []} />
      </Card>

      {overview.category_summary?.length > 0 && (
        <Card title="Stock by Category">
          <Table
            columns={[
              { key: 'category', label: 'Category' },
              { key: 'items', label: 'Materials' },
              { key: 'stock_quantity', label: 'Total Quantity', render: (v) => formatNumber(v) },
              ...(isMaster ? [{ key: 'stock_value', label: 'Stock Value', render: (v) => formatCurrency(v) }] : []),
            ]}
            data={overview.category_summary}
            emptyMessage="No materials yet."
          />
        </Card>
      )}
    </>
  );
}

function RecentMovementsTable({ rows }) {
  return (
    <Table
      columns={[
        { key: 'date', label: 'Date', render: (v) => (v ? new Date(v).toLocaleDateString() : '-') },
        { key: 'type', label: 'Type', render: (v) => <span className={`status-badge ${v === 'IN' ? 'status-ok' : 'status-warning'}`}>{v === 'IN' ? 'Stock In' : 'Stock Out'}</span> },
        { key: 'material', label: 'Material' },
        { key: 'quantity', label: 'Quantity', render: (v, row) => `${formatNumber(v)} ${row.unit || ''}` },
        { key: 'reference', label: 'Reference' },
        { key: 'detail', label: 'Detail' },
      ]}
      data={rows}
      emptyMessage="No recent stock movements."
    />
  );
}

// ---------------------------------------------------------------------
// A3 - Stock (main operational list)
// ---------------------------------------------------------------------
function StockTab({
  materials, loading, error, onRetry, isMaster, search, setSearch, categoryFilter, setCategoryFilter, categories,
  locationFilter, setLocationFilter, locations, statusFilter, setStatusFilter, supplierName,
  onOpenMaterial, onAdjust, onTransfer, onViewLedger, onViewLocations, onReceive, onIssue,
}) {
  const columns = [
    { key: 'name', label: 'Material' },
    { key: 'material_code', label: 'Code' },
    { key: 'category', label: 'Category', render: (v) => v || '-' },
    { key: 'unit', label: 'UOM' },
    { key: 'current_stock', label: 'Current Stock', render: (v) => formatNumber(v) },
    { key: 'minimum_stock', label: 'Reorder Level', render: (v) => formatNumber(v) },
    { key: 'stock_status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
    { key: 'location', label: 'Location', render: (v) => v || '-' },
    { key: 'supplier_id', label: 'Preferred Supplier', render: (v) => supplierName(v) || '-' },
    ...(isMaster ? [
      { key: 'average_rate', label: 'Avg Rate', render: (v) => (v != null ? formatCurrency(v) : '-') },
      { key: 'stock_value', label: 'Stock Value', render: (v) => (v != null ? formatCurrency(v) : '-') },
    ] : []),
    {
      key: 'actions', label: 'Actions',
      render: (_v, row) => (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }} onClick={(e) => e.stopPropagation()}>
          <button className="btn-link" onClick={() => onViewLedger(row)}>Ledger</button>
          <button className="btn-link" onClick={() => onViewLocations(row)}>Locations</button>
          {isMaster && <button className="btn-link" onClick={() => onAdjust(row)}>Adjust</button>}
          {isMaster && <button className="btn-link" onClick={() => onTransfer(row)}>Transfer</button>}
          {isMaster && <button className="btn-link" onClick={() => onReceive(row)}>Receive</button>}
          <button className="btn-link" onClick={() => onIssue(row)}>Issue</button>
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="page-search" style={{ maxWidth: 'none', flexWrap: 'wrap' }}>
        <input type="text" placeholder="Search materials by name or code..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="form-input" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="form-input" value={locationFilter} onChange={(e) => setLocationFilter(e.target.value)}>
          <option value="">All locations</option>
          {locations.map((l) => <option key={l.id} value={l.id}>{l.full_path}</option>)}
        </select>
        <select className="form-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="STOCK OK">Stock OK</option>
          <option value="LOW STOCK">Low Stock</option>
          <option value="OUT OF STOCK">Out of Stock</option>
        </select>
      </div>
      <Table columns={columns} data={materials} loading={loading} error={error} onRetry={onRetry} onRowClick={onOpenMaterial}
        emptyMessage="No materials match these filters." />
    </>
  );
}

// ---------------------------------------------------------------------
// A4 - Stock Movements / Ledger
// ---------------------------------------------------------------------
function MovementsTab({ recent, materials, ledgerMaterialId, onSelectMaterial, ledgerEntries, ledgerLoading, ledgerError, onRetryLedger, locationName }) {
  return (
    <>
      <Card title="Recent Stock Movements">
        <RecentMovementsTable rows={recent} />
      </Card>

      <Card title="Full Ledger for a Material">
        <div className="page-search" style={{ maxWidth: 420 }}>
          <select className="form-input" value={ledgerMaterialId} onChange={(e) => onSelectMaterial(e.target.value)}>
            <option value="">Select a material...</option>
            {materials.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.material_code})</option>)}
          </select>
        </div>
        {ledgerMaterialId && (
          <Table
            columns={[
              { key: 'created_at', label: 'Date', render: (v) => new Date(v).toLocaleString() },
              { key: 'entry_type', label: 'Movement Type' },
              { key: 'quantity_delta', label: 'Quantity', render: (v) => (v > 0 ? `+${v}` : v) },
              { key: 'balance_after', label: 'Balance After' },
              { key: 'location_id', label: 'Location', render: (v) => locationName(v) || '-' },
              { key: 'reference_type', label: 'Reference', render: (v, row) => (v ? `${v} #${row.reference_id}` : '-') },
              { key: 'remarks', label: 'Remarks', render: (v) => v || '-' },
            ]}
            data={ledgerEntries}
            loading={ledgerLoading}
            error={ledgerError}
            onRetry={onRetryLedger}
            emptyMessage="No ledger entries for this material yet."
          />
        )}
      </Card>
    </>
  );
}

// ---------------------------------------------------------------------
// A5 - Purchases / Stock In (master only, per existing backend RBAC)
// ---------------------------------------------------------------------
function PurchasesTab({ purchases, loading, error, onRetry, materials, suppliers, onOpen, onReceiveStock, onDelete }) {
  return (
    <>
      <div className="page-actions" style={{ marginBottom: 'var(--space-4)' }}>
        <button className="btn-primary" onClick={onReceiveStock}>Receive Stock</button>
      </div>
      <Table
        columns={[
          { key: 'purchase_code', label: 'Reference' },
          { key: 'material_id', label: 'Material', render: (v) => materials.find((m) => m.id === v)?.name || v },
          { key: 'supplier_id', label: 'Supplier', render: (v) => suppliers.find((s) => s.id === v)?.name || v },
          { key: 'quantity', label: 'Quantity', render: (v, row) => `${formatNumber(v)} ${row.unit || ''}` },
          { key: 'rate', label: 'Rate', render: (v) => formatCurrency(v) },
          { key: 'date', label: 'Date', render: (v) => (v ? new Date(v).toLocaleDateString() : '-') },
          { key: 'receipt_status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
          {
            key: 'actions', label: '',
            render: (v, row) => row.receipt_status !== 'Received' && (
              <button
                type="button" className="btn-link"
                onClick={(e) => { e.stopPropagation(); onDelete(row); }}
              >
                Delete
              </button>
            ),
          },
        ]}
        data={purchases}
        loading={loading}
        error={error}
        onRetry={onRetry}
        onRowClick={onOpen}
        emptyMessage="No purchases recorded yet."
      />
    </>
  );
}

// ---------------------------------------------------------------------
// A6 - Issues / Stock Out
// ---------------------------------------------------------------------
function IssuesTab({ issues, loading, error, onRetry, isMaster, materials, orders, onIssueStock }) {
  return (
    <>
      {isMaster && (
        <div className="page-actions" style={{ marginBottom: 'var(--space-4)' }}>
          <button className="btn-primary" onClick={onIssueStock}>Issue Stock</button>
        </div>
      )}
      <Table
        columns={[
          { key: 'issue_code', label: 'Reference' },
          { key: 'material_id', label: 'Material', render: (v) => materials.find((m) => m.id === v)?.name || v },
          { key: 'quantity_issued', label: 'Quantity', render: (v, row) => `${formatNumber(v)} ${row.unit || ''}` },
          { key: 'date', label: 'Date', render: (v) => (v ? new Date(v).toLocaleDateString() : '-') },
          { key: 'order_id', label: 'Order', render: (v, row) => orders.find((o) => o.id === v)?.order_code || row.issued_to || '-' },
          { key: 'remarks', label: 'Remarks', render: (v) => v || '-' },
        ]}
        data={issues}
        loading={loading}
        error={error}
        onRetry={onRetry}
        emptyMessage="No issues recorded yet."
      />
    </>
  );
}

// ---------------------------------------------------------------------
// A7 - Locations (per-material, location-wise breakdown)
// ---------------------------------------------------------------------
function LocationsTab({ locations, materials, locationMaterialId, onSelectMaterial, breakdown, loading }) {
  return (
    <>
      <Card title="Locations">
        <Table
          columns={[
            { key: 'full_path', label: 'Location' },
            { key: 'name', label: 'Name' },
          ]}
          data={locations}
          emptyMessage="No locations set up yet."
        />
      </Card>

      <Card title="Stock by Location for a Material">
        <div className="page-search" style={{ maxWidth: 420 }}>
          <select className="form-input" value={locationMaterialId} onChange={(e) => onSelectMaterial(e.target.value)}>
            <option value="">Select a material...</option>
            {materials.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.material_code})</option>)}
          </select>
        </div>
        {loading && <p>Loading...</p>}
        {breakdown && (
          <Table
            columns={[
              { key: 'location_name', label: 'Location' },
              { key: 'quantity', label: 'Quantity', render: (v) => `${formatNumber(v)} ${breakdown.unit}` },
            ]}
            data={[...breakdown.locations, { location_name: 'Total', quantity: breakdown.total }]}
            emptyMessage="No location-wise stock recorded for this material."
          />
        )}
      </Card>
    </>
  );
}

// ---------------------------------------------------------------------
// A8 - Purchase Required (existing max(minimum - current, 0) business
// logic from /api/dashboard/stock - not recomputed here)
// ---------------------------------------------------------------------
function PurchaseRequiredTab({ items, loading, isMaster, onOrder }) {
  return (
    <Table
      columns={[
        { key: 'material', label: 'Material' },
        { key: 'current', label: 'Current Stock', render: (v) => formatNumber(v) },
        { key: 'minimum', label: 'Minimum/Reorder Level', render: (v) => formatNumber(v) },
        { key: 'suggested_order', label: 'Shortage Quantity', render: (v) => formatNumber(v) },
        { key: 'supplier', label: 'Preferred Supplier', render: (v) => v || '-' },
        ...(isMaster ? [{
          key: 'actions', label: 'Actions',
          render: (_v, row) => <button className="btn-link" onClick={() => onOrder(row)}>Order</button>,
        }] : []),
      ]}
      data={items}
      loading={loading}
      emptyMessage="Nothing needs reordering right now."
    />
  );
}

// --- MaterialsPage.jsx ---
const PAGE_SIZE = 25;
const SORT_OPTIONS = [
  { value: 'name-asc', label: 'Name (A-Z)' },
  { value: 'price-asc', label: 'Price: Low to High' },
  { value: 'price-desc', label: 'Price: High to Low' },
  { value: 'stock-asc', label: 'Stock: Low to High' },
  { value: 'stock-desc', label: 'Stock: High to Low' },
];

function MaterialsPage() {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const isStrictlyMaster = user?.role === 'master';
  const location = useLocation();

  const [materials, setMaterials] = useState([]);
  const [allMaterials, setAllMaterials] = useState([]); // unfiltered, for KPIs + filter option lists
  const [suppliers, setSuppliers] = useState([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [brand, setBrand] = useState('');
  const [thickness, setThickness] = useState('');
  const [sort, setSort] = useState('name-asc');
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filterCategories, setFilterCategories] = useState([]);
  const [filterCategoryId, setFilterCategoryId] = useState('');
  const [filterSubcategoryId, setFilterSubcategoryId] = useState('');
  const [filterAttributeDefs, setFilterAttributeDefs] = useState([]);
  const [filterAttributeValues, setFilterAttributeValues] = useState({}); // attribute_definition_id -> value
  const [allLocations, setAllLocations] = useState([]);
  const [view, setView] = useState('grid'); // grid | list | table
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingMaterial, setEditingMaterial] = useState(null);
  const [error, setError] = useState('');
  const [addedFlash, setAddedFlash] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hierarchySelection, setHierarchySelection] = useState({ subcategoryId: null, attributeValues: [] });
  const [pageLoading, setPageLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // "Intelligent defaults" for the Add Material form. The
  // interpretation itself lives entirely in the backend
  // (materialsAPI.interpretName -> existing material_interpreter.py);
  // this is only the suggestion box + the two refs used to apply it
  // into the existing Form/MaterialAttributesEditor without turning
  // either into a parent-controlled component.
  const [nameSuggestion, setNameSuggestion] = useState(null);
  const [suggestionDismissed, setSuggestionDismissed] = useState(false);
  const createFormRef = useRef(null);
  const createAttributesRef = useRef(null);
  const suggestTimerRef = useRef(null);
  const suggestRequestIdRef = useRef(0);

  const load = (params, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    setPageLoading(true);
    setError('');
    materialsAPI.list({ ...params, limit: PAGE_SIZE, offset }).then((res) => {
      setMaterials(res.data);
      setTotalCount(Number(res.headers['x-total-count'] || res.data.length));
    }).catch(() => {
      // Defect repair (F138 P4.2): a failed refetch (pagination, filter
      // change, retry) used to wipe the already-loaded materials list to
      // [] here, so a transient blip during a background reload blanked
      // an already-populated catalog down to "No materials match your
      // filters." The previously-loaded page of materials/totalCount is
      // left in place; only the error banner above is shown.
      setError('Could not load materials. Check that the backend server is running and reachable.');
    }).finally(() => setPageLoading(false));
  };

  useEffect(() => load(), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Full material list (for name-suggestion/matching), suppliers,
  // categories, and locations are reference data, not tied to the
  // current filter/page - previously refetched (materials list
  // unbounded, no pagination) on every filter change, page click, and
  // clear-filters click. Fetched once per page visit instead.
  useEffect(() => {
    materialsAPI.list().then((res) => setAllMaterials(res.data)).catch(() => setAllMaterials([]));
    suppliersAPI.list().then((res) => setSuppliers(res.data)).catch(() => setSuppliers([]));
    materialCategoriesAPI.list().then((res) => setFilterCategories(res.data)).catch(() => setFilterCategories([]));
    locationsAPI.list().then((res) => setAllLocations(res.data)).catch(() => setAllLocations([]));
  }, []);

  // Server-side filters: search, category, low-stock, and now the real
  // dynamic subcategory/attribute filters (built server-side against
  // MaterialAttributeValue, not client-side against the legacy
  // brand_grade/thickness_size strings). These reset pagination.
  const serverFilters = () => {
    const params = {};
    if (search) params.search = search;
    if (category) params.category = category;
    if (lowStockOnly) params.low_stock_only = true;
    if (filterSubcategoryId) params.subcategory_id = filterSubcategoryId;
    const activeAttrFilters = Object.entries(filterAttributeValues).filter(([, v]) => v);
    if (activeAttrFilters.length > 0) params.attribute_filters = JSON.stringify(Object.fromEntries(activeAttrFilters));
    return params;
  };

  const applyServerFilters = (e) => {
    e?.preventDefault();
    setPage(1);
    load(serverFilters(), 1);
  };

  const handleFilterCategoryChange = (e) => {
    const id = e.target.value;
    setFilterCategoryId(id);
    setFilterSubcategoryId('');
    setFilterAttributeDefs([]);
    setFilterAttributeValues({});
  };

  const handleFilterSubcategoryChange = (e) => {
    const id = e.target.value;
    setFilterSubcategoryId(id);
    setFilterAttributeValues({});
    if (!id) {
      setFilterAttributeDefs([]);
      return;
    }
    const cat = filterCategories.find((c) => String(c.id) === filterCategoryId);
    const sub = cat?.subcategories.find((s) => String(s.id) === id);
    setFilterAttributeDefs(sub?.attribute_definitions || []);
  };

  const handleFilterAttributeChange = (attrId, value) => {
    setFilterAttributeValues((prev) => ({ ...prev, [attrId]: value }));
  };

  const selectCategory = (cat) => {
    setCategory(cat);
    setPage(1);
    load({ ...serverFilters(), category: cat || undefined }, 1);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(serverFilters(), pageNum);
  };

  // Brand/thickness/sort are refined client-side on the current page,
  // since the backend doesn't expose those as query filters yet.
  const categories = useMemo(
    () => [...new Set(allMaterials.map((m) => m.category).filter(Boolean))].sort(),
    [allMaterials]
  );
  const brands = useMemo(
    () => [...new Set(allMaterials.map((m) => m.brand_grade).filter(Boolean))].sort(),
    [allMaterials]
  );
  const thicknesses = useMemo(
    () => [...new Set(allMaterials.map((m) => m.thickness_size).filter(Boolean))].sort(),
    [allMaterials]
  );

  const visibleMaterials = useMemo(() => {
    let list = materials.filter((m) => (!brand || m.brand_grade === brand) && (!thickness || m.thickness_size === thickness));
    const [field, dir] = sort.split('-');
    list = [...list].sort((a, b) => {
      let diff = 0;
      if (field === 'name') diff = (a.name || '').localeCompare(b.name || '');
      if (field === 'price') diff = (Number(a.average_rate) || 0) - (Number(b.average_rate) || 0);
      if (field === 'stock') diff = (Number(a.current_stock) || 0) - (Number(b.current_stock) || 0);
      return dir === 'desc' ? -diff : diff;
    });
    return list;
  }, [materials, brand, thickness, sort]);

  // Fires on every keystroke in the create form (Form's onFieldChange),
  // but only the "name" field triggers anything here. Debounced so it
  // doesn't call the backend on every keystroke, and guarded with a
  // request id so a slow earlier response can never clobber a newer one.
  const handleCreateFieldChange = (fieldName, value) => {
    if (fieldName !== 'name') return;
    setSuggestionDismissed(false);
    if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
    const typed = (value || '').trim();
    if (typed.length < 3) {
      setNameSuggestion(null);
      return;
    }
    suggestTimerRef.current = setTimeout(() => {
      const requestId = ++suggestRequestIdRef.current;
      materialsAPI.interpretName(typed).then((res) => {
        if (requestId !== suggestRequestIdRef.current) return; // superseded by a newer keystroke
        // Confidence "none" means the interpreter genuinely has nothing
        // to go on - do nothing gracefully, not an error.
        if (res.data && res.data.confidence !== 'none') {
          setNameSuggestion({ ...res.data, for_name: typed });
        } else {
          setNameSuggestion(null);
        }
      }).catch(() => setNameSuggestion(null));
    }, 400);
  };

  const applyNameSuggestion = () => {
    if (!nameSuggestion) return;
    if (nameSuggestion.thickness_size) {
      createFormRef.current?.setValue('thickness_size', nameSuggestion.thickness_size);
    }
    if (nameSuggestion.subcategory_id) {
      createAttributesRef.current?.applySuggestedSubcategory(nameSuggestion.subcategory_id);
    }
    setSuggestionDismissed(true);
  };

  const resetCreateSuggestionState = () => {
    if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
    setNameSuggestion(null);
    setSuggestionDismissed(false);
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await materialsAPI.create({
        ...formData,
        minimum_stock: Number(formData.minimum_stock || 0),
        opening_stock: Number(formData.opening_stock || 0),
        average_rate: formData.average_rate || '0',
        supplier_id: formData.supplier_id ? Number(formData.supplier_id) : null,
        location_id: formData.location_id ? Number(formData.location_id) : null,
        subcategory_id: hierarchySelection.subcategoryId,
        attribute_values: hierarchySelection.attributeValues,
      });
      setShowAdd(false);
      setHierarchySelection({ subcategoryId: null, attributeValues: [] });
      resetCreateSuggestionState();
      applyServerFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add material');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await materialsAPI.update(editingMaterial.id, {
        name: formData.name, category: formData.category, brand_grade: formData.brand_grade,
        thickness_size: formData.thickness_size, unit: formData.unit,
        minimum_stock: Number(formData.minimum_stock || 0), average_rate: formData.average_rate,
        supplier_id: formData.supplier_id ? Number(formData.supplier_id) : null, location: formData.location,
        location_id: formData.location_id ? Number(formData.location_id) : null,
        subcategory_id: hierarchySelection.subcategoryId,
        attribute_values: hierarchySelection.attributeValues,
      });
      setEditingMaterial(null);
      applyServerFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update material');
    } finally {
      setLoading(false);
    }
  };

  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const handleDelete = (material) => setPendingDelete(material);
  const confirmDelete = async () => {
    setError('');
    setDeleting(true);
    try {
      await materialsAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      applyServerFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete material');
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  const handleAddToCart = (material, qty) => {
    const supplier = suppliers.find((s) => s.id === material.supplier_id);
    dispatch(addToCart({
      materialId: material.id,
      name: material.name,
      unit: material.unit,
      rate: material.average_rate,
      supplierId: material.supplier_id,
      supplierName: supplier?.name,
      quantity: qty,
      currentStock: material.current_stock,
    }));
    setAddedFlash(material.id);
    setTimeout(() => setAddedFlash(null), 1200);
  };

  const columns = [
    { key: 'material_code', label: 'Material ID' }, { key: 'name', label: 'Name' },
    { key: 'category', label: 'Category' }, { key: 'unit', label: 'Unit' },
    { key: 'current_stock', label: 'Available Stock' }, { key: 'minimum_stock', label: 'Reorder Level' },
    { key: 'stock_status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
    { key: 'average_rate', label: 'Avg Rate', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'stock_value', label: 'Stock Value', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'location', label: 'Location' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingMaterial(row); }}>Edit</button> : null
      ),
    },
    {
      key: 'delete_action', label: '', render: (v, row) => (
        isStrictlyMaster ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); handleDelete(row); }}>Delete</button> : null
      ),
    },
  ];

  const createFields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets' },
    { name: 'opening_stock', label: 'Opening Stock', type: 'number', advanced: true },
    { name: 'minimum_stock', label: 'Reorder Level', type: 'number', advanced: true },
    { name: 'average_rate', label: 'Average Rate', type: 'number', advanced: true },
    { name: 'supplier_id', label: 'Primary Supplier', type: 'select', options: suppliers.map((s) => ({ value: s.id, label: s.name })), advanced: true },
    { name: 'location_id', label: 'Location', type: 'select', options: allLocations.map((l) => ({ value: l.id, label: l.full_path })), advanced: true },
    // Legacy fields, kept for backward compatibility but deliberately not
    // shown alongside the primary fields above - the real
    // category/specifications entry is MaterialAttributesEditor, rendered
    // above this form. These only matter for edge cases (a category that
    // doesn't fit the new hierarchy yet, or migrating old data by hand).
    { name: 'category', label: 'Category (only if not using Category/Subcategory above)', advanced: true },
    { name: 'brand_grade', label: 'Brand/Grade (only if not using Specifications above)', advanced: true },
    { name: 'thickness_size', label: 'Thickness/Size (only if not using Specifications above)', advanced: true },
    { name: 'location', label: 'Location (free text, only if not using the Location dropdown above)', advanced: true },
  ];

  const editFields = createFields.filter((f) => !['opening_stock'].includes(f.name));

  const inventoryValue = allMaterials.reduce((sum, m) => sum + (m.stock_value || 0), 0);
  const lowStockCount = allMaterials.filter((m) => m.stock_status === 'LOW STOCK').length;
  const outOfStockCount = allMaterials.filter((m) => m.stock_status === 'OUT OF STOCK').length;

  const hasAnyMaterials = allMaterials.length > 0;
  const activeFilterCount = [category, brand, thickness, lowStockOnly].filter(Boolean).length;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Material Catalog</h1>
          <p className="page-summary">Browse, compare, and stock up on every material Woodful works with.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('stock-dashboard.xlsx')} target="_blank" rel="noreferrer">
            Export Stock Dashboard
          </a>
          <a className="btn-secondary" href={reportsAPI.downloadUrl('materials.xlsx')} target="_blank" rel="noreferrer">
            Export Material List
          </a>
          {isPrivileged && <button className="btn-secondary" onClick={() => navigate('/materials/import')}>Import Excel</button>}
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Material</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="kpi-row">
        {isPrivileged && <KpiCard label="Inventory Value" value={formatCurrency(inventoryValue)} />}
        <KpiCard label="Low Stock" value={lowStockCount} tone={lowStockCount > 0 ? 'warning' : 'success'} />
        <KpiCard label="Out of Stock" value={outOfStockCount} tone={outOfStockCount > 0 ? 'danger' : 'success'} />
      </div>

      {hasAnyMaterials && (
        <>
          {categories.length > 0 && (
            <div className="category-pills">
              <button className={`category-pill ${!category ? 'active' : ''}`} onClick={() => selectCategory('')}>All</button>
              {categories.map((c) => (
                <button key={c} className={`category-pill ${category === c ? 'active' : ''}`} onClick={() => selectCategory(c)}>{c}</button>
              ))}
            </div>
          )}

          <div className="catalog-toolbar">
            <form className="catalog-search" onSubmit={applyServerFilters}>
              <SearchIcon width={16} height={16} />
              <input
                type="text" placeholder="Search materials by name or code..." value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <button type="submit" className="btn-secondary catalog-search-btn">Search</button>
            </form>

            <button
              className={`btn-secondary catalog-filter-toggle ${activeFilterCount ? 'has-active' : ''}`}
              onClick={() => setShowFilters((v) => !v)}
            >
              <SlidersIcon width={15} height={15} /> Filters {activeFilterCount > 0 && <span className="filter-count">{activeFilterCount}</span>}
            </button>

            <select className="catalog-sort" value={sort} onChange={(e) => setSort(e.target.value)}>
              {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>

            <div className="view-toggle">
              <button className={view === 'grid' ? 'active' : ''} onClick={() => setView('grid')} title="Grid view" aria-label="Grid view"><GridIcon width={16} height={16} /></button>
              <button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')} title="List view" aria-label="List view"><ListIcon width={16} height={16} /></button>
              <button className={view === 'table' ? 'active' : ''} onClick={() => setView('table')} title="Table view" aria-label="Table view">Table</button>
            </div>
          </div>

          {showFilters && (
            <div className="catalog-filter-panel">
              <label className="catalog-filter-field">
                Category
                <select value={filterCategoryId} onChange={handleFilterCategoryChange}>
                  <option value="">All categories</option>
                  {filterCategories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </label>
              {filterCategoryId && (
                <label className="catalog-filter-field">
                  Subcategory
                  <select value={filterSubcategoryId} onChange={handleFilterSubcategoryChange}>
                    <option value="">All subcategories</option>
                    {(filterCategories.find((c) => String(c.id) === filterCategoryId)?.subcategories || [])
                      .map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </label>
              )}
              {filterAttributeDefs.map((def) => (
                <label className="catalog-filter-field" key={def.id}>
                  {def.name}{def.unit_label && ` (${def.unit_label})`}
                  {def.data_type === 'select' ? (
                    <select value={filterAttributeValues[def.id] || ''} onChange={(e) => handleFilterAttributeChange(def.id, e.target.value)}>
                      <option value="">Any {def.name}</option>
                      {(def.select_options || '').split(',').map((o) => o.trim()).filter(Boolean).map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={def.data_type === 'number' ? 'number' : 'text'}
                      value={filterAttributeValues[def.id] || ''}
                      onChange={(e) => handleFilterAttributeChange(def.id, e.target.value)}
                      placeholder={`Any ${def.name}`}
                    />
                  )}
                </label>
              ))}
              {!filterSubcategoryId && brands.length > 0 && (
                <label className="catalog-filter-field">
                  Brand / Grade (legacy)
                  <select value={brand} onChange={(e) => setBrand(e.target.value)}>
                    <option value="">All brands</option>
                    {brands.map((b) => <option key={b} value={b}>{b}</option>)}
                  </select>
                </label>
              )}
              {!filterSubcategoryId && thicknesses.length > 0 && (
                <label className="catalog-filter-field">
                  Thickness / Size (legacy)
                  <select value={thickness} onChange={(e) => setThickness(e.target.value)}>
                    <option value="">All sizes</option>
                    {thicknesses.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </label>
              )}
              <label className="catalog-filter-field catalog-filter-checkbox">
                <input type="checkbox" checked={lowStockOnly} onChange={(e) => setLowStockOnly(e.target.checked)} />
                Low stock only
              </label>
              <button className="btn-secondary" onClick={applyServerFilters}>Apply</button>
              <button
                className="btn-link"
                onClick={() => {
                  setBrand(''); setThickness(''); setLowStockOnly(false); setCategory(''); setSearch('');
                  setFilterCategoryId(''); setFilterSubcategoryId(''); setFilterAttributeDefs([]); setFilterAttributeValues({});
                  setPage(1); load({}, 1);
                }}
              >
                Clear all
              </button>
            </div>
          )}
        </>
      )}

      {!hasAnyMaterials && !pageLoading ? (
        <div className="catalog-empty-state">
          <div className="catalog-empty-icon"><CartIcon width={28} height={28} /></div>
          <h3>No materials in the catalog yet</h3>
          <p>Add your first material to start browsing stock, prices, and suppliers in one place.</p>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Material</button>}
        </div>
      ) : view === 'table' ? (
        <>
          <Table columns={columns} data={visibleMaterials} loading={pageLoading} onRowClick={(row) => navigate(`/materials/${row.id}`)} emptyMessage="No materials match your filters." />
          {totalCount > PAGE_SIZE && (
            <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />
          )}
        </>
      ) : pageLoading ? (
        <div className={view === 'grid' ? 'material-grid' : 'material-list'}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className={view === 'grid' ? 'material-card-skeleton' : 'material-row-skeleton'} />
          ))}
        </div>
      ) : visibleMaterials.length === 0 ? (
        <div className="catalog-empty-state">
          <h3>No materials match your filters</h3>
          <p>Try a different search term, or clear filters to see the full catalog.</p>
          <button className="btn-secondary" onClick={() => { setBrand(''); setThickness(''); setLowStockOnly(false); setCategory(''); setSearch(''); setPage(1); load({}, 1); }}>Clear filters</button>
        </div>
      ) : (
        <>
          <div className={view === 'grid' ? 'material-grid' : 'material-list'}>
            {visibleMaterials.map((m) => (
              <div key={m.id} className={addedFlash === m.id ? 'material-card-added' : ''}>
                <MaterialCard material={m} view={view} onOpen={(mat) => navigate(`/materials/${mat.id}`)} onAddToCart={handleAddToCart} />
              </div>
            ))}
          </div>
          {totalCount > PAGE_SIZE && (
            <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />
          )}
        </>
      )}

      <Modal isOpen={showAdd} title="Add Material" onClose={() => { setShowAdd(false); setHierarchySelection({ subcategoryId: null, attributeValues: [] }); resetCreateSuggestionState(); }}>
        {nameSuggestion && !suggestionDismissed && (
          <div className="material-suggestion-box">
            <div className="material-suggestion-text">
              <strong>{nameSuggestion.for_name}</strong> looks like{' '}
              {nameSuggestion.subcategory_name
                ? <>a <strong>{nameSuggestion.subcategory_name}</strong>{nameSuggestion.category_name ? ` (${nameSuggestion.category_name})` : ''}</>
                : 'a known material'}
              {nameSuggestion.thickness_size ? <>, <strong>{nameSuggestion.thickness_size}</strong> thick</> : ''}.
            </div>
            <div className="material-suggestion-actions">
              <button type="button" className="btn-secondary btn-small" onClick={applyNameSuggestion}>Use this</button>
              <button type="button" className="btn-link" onClick={() => setSuggestionDismissed(true)}>Dismiss</button>
            </div>
          </div>
        )}
        <MaterialAttributesEditor ref={createAttributesRef} onChange={setHierarchySelection} />
        <Form ref={createFormRef} fields={createFields} onSubmit={handleCreate} onFieldChange={handleCreateFieldChange} loading={loading} submitText="Add Material" />
      </Modal>
      <Modal isOpen={!!editingMaterial} title={`Edit ${editingMaterial?.name || ''}`} onClose={() => { setEditingMaterial(null); setHierarchySelection({ subcategoryId: null, attributeValues: [] }); }}>
        {editingMaterial && (
          <>
            <MaterialAttributesEditor
              onChange={setHierarchySelection}
              initialSubcategoryId={editingMaterial.subcategory_id}
              initialAttributeValues={editingMaterial.attribute_values}
            />
            <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingMaterial} />
          </>
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

export { InventoryPage, MaterialsPage };
