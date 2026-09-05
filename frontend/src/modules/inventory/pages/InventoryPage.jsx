import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import {
  dashboardAPI, materialsAPI, purchasesAPI, issuesAPI, locationsAPI, suppliersAPI, stockAPI, ordersAPI,
} from '../../../utils/api';
import Table from '../../../components/common/Table';
import Card from '../../../components/common/Card';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import { statusClass, formatCurrency, formatNumber, today } from '../../../utils/format';

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

  const [purchases, setPurchases] = useState([]);
  const [purchasesLoading, setPurchasesLoading] = useState(false);
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
    materialsAPI.list({ active_only: true }).then((res) => setMaterials(res.data)).catch(() => setMaterials([]))
      .finally(() => setMaterialsLoading(false));
  }, []);

  const loadPurchases = useCallback(() => {
    if (!isMaster) return;
    setPurchasesLoading(true);
    purchasesAPI.list().then((res) => setPurchases(res.data)).catch(() => setPurchases([]))
      .finally(() => setPurchasesLoading(false));
  }, [isMaster]);

  const loadIssues = useCallback(() => {
    setIssuesLoading(true);
    issuesAPI.list().then((res) => setIssues(res.data)).catch(() => setIssues([])).finally(() => setIssuesLoading(false));
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
      const params = { active_only: true };
      if (search) params.search = search;
      if (categoryFilter) params.category = categoryFilter;
      if (statusFilter === 'LOW STOCK' || statusFilter === 'OUT OF STOCK') params.low_stock_only = true;
      materialsAPI.list(params).then((res) => setMaterials(res.data)).catch(() => setMaterials([]))
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
      await purchasesAPI.create({
        ...formData,
        supplier_id: Number(formData.supplier_id),
        material_id: Number(formData.material_id),
        quantity: formData.quantity, rate: formData.rate,
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

  const handleIssue = async (formData) => {
    setActionLoading(true);
    setError('');
    try {
      await issuesAPI.create({
        ...formData,
        material_id: Number(formData.material_id),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        location_id: formData.location_id ? Number(formData.location_id) : null,
        date: new Date(formData.date).toISOString(),
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
          materials={visibleStock} loading={materialsLoading} isMaster={isMaster}
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
          purchases={purchases} loading={purchasesLoading}
          materials={materials} suppliers={suppliers}
          onOpen={(p) => navigate(`/purchases/${p.id}`)}
          onReceiveStock={() => openReceive()}
        />
      )}

      {tab === 'Issues' && (
        <IssuesTab
          issues={issues} loading={issuesLoading} isMaster={isMaster}
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
            { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets', section: 'Quantity & Cost' },
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
            { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets' },
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
  materials, loading, isMaster, search, setSearch, categoryFilter, setCategoryFilter, categories,
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
      <Table columns={columns} data={materials} loading={loading} onRowClick={onOpenMaterial}
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
function PurchasesTab({ purchases, loading, materials, suppliers, onOpen, onReceiveStock }) {
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
        ]}
        data={purchases}
        loading={loading}
        onRowClick={onOpen}
        emptyMessage="No purchases recorded yet."
      />
    </>
  );
}

// ---------------------------------------------------------------------
// A6 - Issues / Stock Out
// ---------------------------------------------------------------------
function IssuesTab({ issues, loading, isMaster, materials, orders, onIssueStock }) {
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

export default InventoryPage;
