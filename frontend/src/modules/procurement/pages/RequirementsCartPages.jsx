// Requirements & cart pages: procurement requirements list/detail
// and the personal cart drawer. Combines the former
// ProcurementRequirementsPage.jsx, ProcurementRequirementDetailPage.jsx,
// and components/CartDrawer.jsx.
import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { materialsAPI, ordersAPI, procurementRequirementsAPI, purchasesAPI } from '../../../utils/api';
import { Alert, Card, Form, Modal, Pagination, Table } from '../../../components/common/UI';
import { formatCurrency, statusClass } from '../../../utils/utils';
import { useDispatch, useSelector } from 'react-redux';
import { clearCart, removeFromCart, updateQuantity } from '../../../redux/slices';
import { CartIcon, CloseIcon } from '../../../components/icons';
import '../../../styles/modules.css';

// --- ProcurementRequirementsPage.jsx ---
// Defect repair (F138 P21 API-contract audit): the backend has always
// paginated this endpoint (limit/offset, X-Total-Count header) since
// ProcurementRequirement is a persisted, never-pruned record that only
// accumulates over time - but this page never read the header or
// requested a second page, so anything past the backend's default
// 500-row cap was silently invisible with no indication more existed.
// Fixed the same way MaterialsPage's own paginated list already is.
const REQUIREMENTS_PAGE_SIZE = 25;

function ProcurementRequirementsPage() {
  const navigate = useNavigate();
  const [requirements, setRequirements] = useState([]);
  const [orders, setOrders] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const load = (pageNum = 1) => {
    setPageLoading(true);
    setLoadError(false);
    const offset = (pageNum - 1) * REQUIREMENTS_PAGE_SIZE;
    procurementRequirementsAPI.list({ limit: REQUIREMENTS_PAGE_SIZE, offset }).then((res) => {
      setRequirements(res.data);
      setTotalCount(Number(res.headers['x-total-count'] || res.data.length));
    }).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view procurement requirements.' : 'Unable to load procurement requirements. Please try again.');
    }).finally(() => setPageLoading(false));
    ordersAPI.list().then((res) => setOrders(res.data)).catch(() => setOrders([]));
    materialsAPI.list().then((res) => setMaterials(res.data)).catch(() => setMaterials([]));
  };
  useEffect(() => load(1), []); // eslint-disable-line react-hooks/exhaustive-deps

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(pageNum);
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await procurementRequirementsAPI.create({
        ...formData, order_id: Number(formData.order_id), material_id: Number(formData.material_id),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create the procurement requirement - the order may already have this material fully available.');
    } finally {
      setLoading(false);
    }
  };

  const fields = [
    { name: 'order_id', label: 'Order', type: 'select', required: true, options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'material_id', label: 'Material', type: 'select', required: true, options: materials.map((m) => ({ value: m.id, label: m.name })) },
    { name: 'priority', label: 'Priority', type: 'select', options: [
      { value: 'High', label: 'High' }, { value: 'Medium', label: 'Medium' }, { value: 'Low', label: 'Low' },
    ] },
    { name: 'required_by_date', label: 'Required By', type: 'date' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Procurement Requirements</h1>
        <button className="btn btn-primary" onClick={() => setShowAdd(true)}>Snapshot Shortage as Requirement</button>
      </div>
      {error && <Alert type="error" message={error} />}
      <Table
        columns={[
          { key: 'material_name', label: 'Material' },
          { key: 'required_quantity', label: 'Required' },
          { key: 'available_quantity_at_creation', label: 'Available (at creation)' },
          { key: 'shortage_quantity_at_creation', label: 'Shortage (at creation)' },
          { key: 'priority', label: 'Priority' },
          { key: 'status', label: 'Status', render: (v) => <span className={statusClass(v)}>{v}</span> },
        ]}
        data={loadError ? [] : requirements}
        error={loadError}
        onRetry={() => load(page)}
        loading={pageLoading}
        onRowClick={(row) => navigate(`/procurement-requirements/${row.id}`)}
        emptyMessage="No procurement requirements yet. Create one from an order's material shortage."
      />
      {totalCount > REQUIREMENTS_PAGE_SIZE && (
        <Pagination currentPage={page} totalPages={Math.ceil(totalCount / REQUIREMENTS_PAGE_SIZE)} onPageChange={goToPage} loading={pageLoading} />
      )}
      <Modal isOpen={showAdd} title="Snapshot Shortage as Requirement" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Create Requirement" />
      </Modal>
    </div>
  );
}

// --- ProcurementRequirementDetailPage.jsx ---
function ProcurementRequirementDetailPage() {
  const { requirementId } = useParams();
  const [requirement, setRequirement] = useState(null);
  const [options, setOptions] = useState(null);
  const [purchase, setPurchase] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(() => {
    setPageLoading(true);
    setLoadError(false);
    procurementRequirementsAPI.get(requirementId).then((res) => {
      setRequirement(res.data);
    }).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view this requirement.' : 'Unable to load this requirement.');
    }).finally(() => setPageLoading(false));
  }, [requirementId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (requirement && !requirement.decision && requirement.status === 'Open') {
      procurementRequirementsAPI.supplierOptions(requirementId).then((res) => setOptions(res.data.options)).catch(() => setOptions([]));
    }
  }, [requirement, requirementId]);

  useEffect(() => {
    if (requirement?.purchase_id) {
      purchasesAPI.get(requirement.purchase_id).then((res) => setPurchase(res.data)).catch(() => setPurchase(null));
    }
  }, [requirement]);

  const handleDecision = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await procurementRequirementsAPI.recordDecision(requirementId, {
        requirement_id: Number(requirementId), selected_supplier_id: Number(formData.selected_supplier_id),
        decision_reason: formData.decision_reason,
      });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record the supplier decision.');
    } finally {
      setLoading(false);
    }
  };

  const handlePurchase = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await procurementRequirementsAPI.createPurchase(requirementId, {
        ...formData, quantity: formData.quantity, rate: formData.rate,
        gst_percent: formData.gst_percent || '18',
      });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create the purchase.');
    } finally {
      setLoading(false);
    }
  };

  if (pageLoading) return <div className="page"><p>Loading...</p></div>;
  if (loadError || !requirement) return (
    <div className="page">
      {error && <Alert type="error" message={error} />}
      {/* Defect repair (F138 P4.3): this detail load had no retry
          affordance on failure, unlike the loadError/Retry convention
          used on every other detail page in this codebase (e.g.
          ProcurementPages' Purchase/Supplier detail pages). */}
      <button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button>
    </div>
  );

  const decisionFields = [
    { name: 'selected_supplier_id', label: 'Selected Supplier', type: 'select', required: true,
      options: (options || []).map((o) => ({ value: o.supplier_id, label: `${o.supplier_name}${o.is_preferred ? ' (Preferred)' : ''}${o.price != null ? ` - ₹${o.price}` : ''}` })) },
    { name: 'decision_reason', label: 'Reason', type: 'textarea', placeholder: 'Why this supplier, if it diverges from the recommendation' },
  ];

  const purchaseFields = [
    { name: 'quantity', label: 'Quantity', type: 'number', required: true },
    { name: 'unit', label: 'Unit', required: true, placeholder: requirement.material_name ? '' : 'e.g. Sheets' },
    { name: 'rate', label: 'Rate', type: 'number', required: true },
    { name: 'gst_percent', label: 'GST %', type: 'number', placeholder: '18' },
    { name: 'expected_delivery_date', label: 'Expected Delivery', type: 'date' },
    { name: 'receipt_status', label: 'Receipt Status', type: 'select', options: [
      { value: 'Ordered', label: 'Ordered (not yet in hand)' }, { value: 'Received', label: 'Received (already in hand)' },
    ] },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>{requirement.material_name}</h1>
        <span className={statusClass(requirement.status)}>{requirement.status}</span>
      </div>
      {error && <Alert type="error" message={error} />}

      <Card title="Why this requirement exists">
        <div className="detail-grid">
          <div><div className="detail-meta-label">Required</div><h3>{requirement.required_quantity}</h3></div>
          <div><div className="detail-meta-label">Available (at creation)</div><h3>{requirement.available_quantity_at_creation}</h3></div>
          <div><div className="detail-meta-label">Shortage (at creation)</div><h3>{requirement.shortage_quantity_at_creation}</h3></div>
          <div><div className="detail-meta-label">Priority</div><h3>{requirement.priority || '-'}</h3></div>
        </div>
        {requirement.order_id && <p><Link to={`/orders/${requirement.order_id}`}>View the related order</Link></p>}
        {requirement.remarks && <p>{requirement.remarks}</p>}
      </Card>

      {!requirement.decision && requirement.status === 'Open' && (
        <Card title="Supplier Options">
          {options === null ? <p>Loading supplier options...</p> : options.length === 0 ? (
            <Alert type="info" message="No supplier is linked to this material yet - add a SupplierMaterial relationship first." />
          ) : (
            <>
              <ul>
                {options.map((o) => (
                  <li key={o.supplier_id}>
                    {o.supplier_name}{o.is_preferred ? ' - Preferred' : ''}{o.price != null ? ` - ₹${o.price}` : ' - no price on file'}
                    {o.lead_time_days != null ? `, ${o.lead_time_days}d lead time` : ''}
                  </li>
                ))}
              </ul>
              <Form fields={decisionFields} onSubmit={handleDecision} loading={loading} submitText="Record Supplier Decision" />
            </>
          )}
        </Card>
      )}

      {requirement.decision && (
        <Card title="Supplier Decision">
          <div className="detail-grid">
            <div><div className="detail-meta-label">Recommended</div><h3>{requirement.decision.recommended_supplier_name || 'None'}</h3></div>
            <div><div className="detail-meta-label">Selected</div><h3>{requirement.decision.selected_supplier_name}</h3></div>
            <div><div className="detail-meta-label">Followed Recommendation</div><h3>{requirement.decision.followed_recommendation === null ? 'N/A' : requirement.decision.followed_recommendation ? 'Yes' : 'No'}</h3></div>
          </div>
          {requirement.decision.decision_reason && <p>{requirement.decision.decision_reason}</p>}
        </Card>
      )}

      {requirement.decision && !requirement.purchase_id && (
        <Card title="Create Purchase">
          <Form fields={purchaseFields} onSubmit={handlePurchase} loading={loading} submitText="Create Purchase" />
        </Card>
      )}

      {purchase && (
        <Card title="Resulting Purchase">
          <div className="detail-grid">
            <div><div className="detail-meta-label">Purchase</div><h3><Link to={`/purchases/${purchase.id}`}>{purchase.purchase_code}</Link></h3></div>
            <div><div className="detail-meta-label">Receipt Status</div><h3>{purchase.receipt_status}</h3></div>
          </div>
        </Card>
      )}
    </div>
  );
}

// --- ../components/CartDrawer.jsx ---
function CartDrawer({ open, onClose }) {
  const items = useSelector((state) => state.cart.items);
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const shortfallOf = (item) => {
    if (item.currentStock === null || item.currentStock === undefined) return null;
    return Math.max(0, item.quantity - item.currentStock);
  };

  const itemsNeedingPurchase = items.filter((i) => {
    const s = shortfallOf(i);
    return s === null || s > 0;
  });
  const purchaseValue = items.reduce((sum, i) => {
    const s = shortfallOf(i);
    const purchaseQty = s === null ? i.quantity : s;
    return sum + (Number(i.rate) || 0) * purchaseQty;
  }, 0);

  const startPurchase = (item) => {
    const shortfall = shortfallOf(item);
    // Only the shortfall needs buying - if stock already covers what's
    // needed, don't send the full required quantity into a purchase.
    const purchaseQty = shortfall === null ? item.quantity : shortfall;
    navigate('/purchases', {
      state: {
        openCreate: true,
        prefill: {
          material_id: item.materialId,
          supplier_id: item.supplierId || '',
          quantity: purchaseQty,
          rate: item.rate || '',
          unit: item.unit || '',
        },
      },
    });
    onClose();
  };

  const buyAllFromCart = () => {
    // Purchase is genuinely one supplier per record (see PurchasesPage's
    // bulk mode) - group by supplier and pre-select whichever supplier
    // covers the most items, so the common case (everything from one
    // dealer) needs no manual re-selection at all.
    const bySupplier = {};
    itemsNeedingPurchase.forEach((item) => {
      const key = item.supplierId || 'unknown';
      (bySupplier[key] = bySupplier[key] || []).push(item);
    });
    const largestGroup = Object.entries(bySupplier).sort((a, b) => b[1].length - a[1].length)[0];
    const rows = itemsNeedingPurchase.map((item) => ({
      supplier_id: item.supplierId || '',
      material_id: item.materialId,
      quantity: shortfallOf(item) === null ? item.quantity : shortfallOf(item),
      rate: item.rate || '',
      unit: item.unit || '',
    }));
    navigate('/purchases', {
      state: {
        bulkRows: largestGroup ? rows.filter((r) => (r.supplier_id || 'unknown') === largestGroup[0]) : rows,
      },
    });
    onClose();
  };

  const [exporting, setExporting] = useState(false);
  const downloadCartExcel = async () => {
    setExporting(true);
    try {
      const res = await purchasesAPI.exportCart(items.map((i) => ({
        material_id: i.materialId, name: i.name, quantity: i.quantity,
        unit: i.unit || '', rate: i.rate || null, supplier_name: i.supplierName || '',
      })));
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'purchase-cart.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      // Silent - the button itself is a convenience shortcut; if it
      // fails, the "Start Purchase" per-item path (unaffected) still
      // works as the fallback way to buy the cart's contents.
    } finally {
      setExporting(false);
    }
  };

  return (
    <>
      <div className={`cart-drawer-backdrop ${open ? 'open' : ''}`} onClick={onClose} />
      <aside className={`cart-drawer ${open ? 'open' : ''}`} aria-hidden={!open}>
        <div className="cart-drawer-header">
          <h3><CartIcon width={18} height={18} /> Purchase Cart</h3>
          <button className="cart-drawer-close" onClick={onClose} aria-label="Close cart"><CloseIcon width={18} height={18} /></button>
        </div>

        {items.length === 0 ? (
          <div className="cart-drawer-empty">
            <p className="cart-drawer-empty-title">Your purchase cart is empty.</p>
            <p className="cart-drawer-empty-sub">Browse the Material Catalog and add what you need to purchase.</p>
            <button className="btn-secondary" onClick={() => { navigate('/materials'); onClose(); }}>Browse Materials</button>
          </div>
        ) : (
          <>
            <div className="cart-drawer-items">
              {items.map((item) => {
                const shortfall = shortfallOf(item);
                return (
                <div className="cart-drawer-item" key={item.materialId}>
                  <div className="cart-drawer-item-main">
                    <div className="cart-drawer-item-name">{item.name}</div>
                    {item.supplierName && <div className="cart-drawer-item-supplier">Preferred: {item.supplierName}</div>}
                    {shortfall !== null && (
                      <div className="cart-drawer-item-shortage">
                        Required: {item.quantity} &middot; Stock: {item.currentStock} &middot;{' '}
                        {shortfall > 0
                          ? <strong className="cart-drawer-shortage-buy">Purchase: {shortfall}</strong>
                          : <span className="cart-drawer-shortage-covered">Fully covered by stock</span>}
                      </div>
                    )}
                  </div>
                  <div className="cart-drawer-item-qty">
                    <button aria-label={`Decrease quantity of ${item.name}`} onClick={() => dispatch(updateQuantity({ materialId: item.materialId, quantity: item.quantity - 1 }))}>{'\u2212'}</button>
                    <span aria-live="polite">{item.quantity}</span>
                    <button aria-label={`Increase quantity of ${item.name}`} onClick={() => dispatch(updateQuantity({ materialId: item.materialId, quantity: item.quantity + 1 }))}>+</button>
                  </div>
                  <div className="cart-drawer-item-value">{item.rate ? formatCurrency(item.rate * item.quantity) : '\u2014'}</div>
                  <div className="cart-drawer-item-actions">
                    <button className="btn-link" onClick={() => startPurchase(item)} disabled={shortfall === 0}>
                      {shortfall === 0 ? 'No Purchase Needed' : 'Start Purchase'}
                    </button>
                    <button className="cart-drawer-remove" onClick={() => dispatch(removeFromCart(item.materialId))} aria-label="Remove item">
                      <CloseIcon width={14} height={14} />
                    </button>
                  </div>
                </div>
                );
              })}
            </div>
            <div className="cart-drawer-footer">
              <div className="cart-drawer-total">
                <span>Items to purchase</span>
                <strong>{itemsNeedingPurchase.length}</strong>
              </div>
              <div className="cart-drawer-total">
                <span>Estimated purchase value</span>
                <strong>{formatCurrency(purchaseValue)}</strong>
              </div>
              {itemsNeedingPurchase.length > 0 && (
                <button className="btn-primary" onClick={buyAllFromCart} style={{ width: '100%', marginBottom: 'var(--space-2)' }}>
                  Buy All From Cart ({itemsNeedingPurchase.length})
                </button>
              )}
              <div className="cart-drawer-footer-secondary">
                <button className="btn-secondary" onClick={downloadCartExcel} disabled={exporting}>
                  {exporting ? 'Preparing...' : 'Download Excel'}
                </button>
                <button className="btn-secondary" onClick={() => dispatch(clearCart())}>Clear Cart</button>
              </div>
            </div>
          </>
        )}
      </aside>
    </>
  );
}

export { ProcurementRequirementsPage, ProcurementRequirementDetailPage, CartDrawer };
