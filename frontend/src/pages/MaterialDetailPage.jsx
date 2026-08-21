import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { materialsAPI, purchasesAPI, issuesAPI, supplierMaterialsAPI, stockAPI, locationsAPI } from '../utils/api';
import { addToCart } from '../redux/slices/cartSlice';
import Table from '../components/common/Table';
import Card from '../components/common/Card';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { statusClass } from '../utils/statusColors';
import { formatCurrency } from '../utils/currency';

const TABS = ['Overview', 'Suppliers', 'Purchases', 'Issues'];

function MaterialDetailPage() {
  const { materialId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [material, setMaterial] = useState(null);
  const [purchases, setPurchases] = useState([]);
  const [issues, setIssues] = useState([]);
  const [supplierLinks, setSupplierLinks] = useState([]);
  const VALID_TABS = ['Overview', 'Suppliers', 'Purchases', 'Issues'];
  const requestedTab = searchParams.get('tab');
  const [tab, setTab] = useState(VALID_TABS.includes(requestedTab) ? requestedTab : 'Overview');
  const [addedToCart, setAddedToCart] = useState(false);
  const [allLocations, setAllLocations] = useState([]);
  const [locationStock, setLocationStock] = useState(null);
  const [showTransfer, setShowTransfer] = useState(false);
  const [showAdjust, setShowAdjust] = useState(false);
  const [stockLoading, setStockLoading] = useState(false);
  const [stockError, setStockError] = useState('');

  const load = useCallback(() => {
    materialsAPI.get(materialId).then((res) => setMaterial(res.data)).catch(() => setMaterial(null));
    purchasesAPI.list({ material_id: materialId }).then((res) => setPurchases(res.data)).catch(() => setPurchases([]));
    issuesAPI.list({ material_id: materialId }).then((res) => setIssues(res.data)).catch(() => setIssues([]));
    supplierMaterialsAPI.byMaterial(materialId).then((res) => setSupplierLinks(res.data)).catch(() => setSupplierLinks([]));
    locationsAPI.list().then((res) => setAllLocations(res.data)).catch(() => setAllLocations([]));
    stockAPI.locationStock(materialId).then((res) => setLocationStock(res.data)).catch(() => setLocationStock(null));
  }, [materialId]);

  useEffect(load, [load]);

  const handleTransfer = async (formData) => {
    setStockLoading(true);
    setStockError('');
    try {
      await stockAPI.transfer({
        material_id: Number(materialId), quantity: Number(formData.quantity),
        to_location_id: Number(formData.to_location_id),
        from_location_id: formData.from_location_id ? Number(formData.from_location_id) : undefined,
        remarks: formData.remarks,
      });
      setShowTransfer(false);
      load();
    } catch (err) {
      setStockError(err.response?.data?.detail || 'Transfer failed');
    } finally {
      setStockLoading(false);
    }
  };

  const handleAdjust = async (formData) => {
    setStockLoading(true);
    setStockError('');
    try {
      const isReturn = formData.adjustment_type === 'Return from Issue';
      const delta = isReturn
        ? Math.abs(Number(formData.quantity))
        : (formData.direction === 'decrease' ? -Math.abs(Number(formData.quantity)) : Math.abs(Number(formData.quantity)));
      await stockAPI.adjust({
        material_id: Number(materialId), adjustment_type: formData.adjustment_type,
        quantity_delta: delta, reason: formData.reason,
        related_issue_id: isReturn ? Number(formData.related_issue_id) : undefined,
        location_id: formData.location_id ? Number(formData.location_id) : undefined,
      });
      setShowAdjust(false);
      load();
    } catch (err) {
      setStockError(err.response?.data?.detail || 'Adjustment failed');
    } finally {
      setStockLoading(false);
    }
  };

  const handleAddToCart = () => {
    const preferred = supplierLinks.find((s) => s.is_preferred) || supplierLinks[0];
    dispatch(addToCart({
      materialId: material.id, name: material.name, unit: material.unit,
      rate: preferred?.supplier_price || material.average_rate,
      supplierId: preferred?.supplier_id, supplierName: preferred?.supplier_name,
      quantity: 1, currentStock: material.current_stock,
    }));
    setAddedToCart(true);
    setTimeout(() => setAddedToCart(false), 1500);
  };

  if (!material) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/materials" className="btn-link">&larr; Back to Materials</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{material.name}</h1>
          <div className="detail-subtitle">
            {material.material_code} &middot; {material.category || 'Uncategorized'}
            {' '}<span className={`status-badge ${statusClass(material.stock_status)}`}>{material.stock_status}</span>
            {material.business_id && <span className="business-id-badge">{material.business_id}</span>}
          </div>
        </div>
        <div className="detail-header-actions">
          <button className="btn-secondary" onClick={() => setShowTransfer(true)}>Transfer</button>
          <button className="btn-secondary" onClick={() => setShowAdjust(true)}>Adjust Stock</button>
          <button className="btn-primary" onClick={handleAddToCart}>
            {addedToCart ? 'Added!' : 'Add to Purchase Cart'}
          </button>
        </div>
      </div>

      {stockError && <Alert type="error" message={stockError} onClose={() => setStockError('')} />}

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Available Stock</div><h3>{material.current_stock} {material.unit}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Reorder Level</div><h3>{material.minimum_stock} {material.unit}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Average Rate</div><h3>{material.average_rate != null ? formatCurrency(material.average_rate) : 'Restricted'}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Stock Value</div><h3>{material.stock_value != null ? formatCurrency(material.stock_value) : 'Restricted'}</h3></div></Card>
      </div>

      <div className="tab-bar">
        {(isPrivileged ? TABS : TABS.filter((t) => t !== 'Purchases')).map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && (
        <Card title="Material Details">
          <div className="card-body">
            <div className="detail-meta">
              <div className="detail-meta-item"><span className="detail-meta-label">Brand/Grade</span><span className="detail-meta-value">{material.brand_grade || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Thickness/Size</span><span className="detail-meta-value">{material.thickness_size || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Opening Stock</span><span className="detail-meta-value">{material.opening_stock} {material.unit}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Total Purchased</span><span className="detail-meta-value">{material.total_purchased} {material.unit}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Total Issued</span><span className="detail-meta-value">{material.total_issued} {material.unit}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Location</span><span className="detail-meta-value">{material.location || '-'}</span></div>
            </div>
          </div>
        </Card>
      )}

      {tab === 'Overview' && locationStock?.locations?.length > 0 && (
        <Card title="Stock by Location">
          <div className="card-body">
            <Table
              columns={[
                { key: 'location_name', label: 'Location' },
                { key: 'quantity', label: 'Quantity', render: (v) => `${v} ${material.unit}` },
              ]}
              data={[...locationStock.locations, { location_id: 'total', location_name: 'Total', quantity: locationStock.total }]}
            />
          </div>
        </Card>
      )}

      {tab === 'Overview' && material.attribute_values?.length > 0 && (
        <Card title="Specifications">
          <div className="card-body">
            <div className="detail-meta">
              {material.attribute_values.map((attr) => (
                <div className="detail-meta-item" key={attr.id}>
                  <span className="detail-meta-label">{attr.attribute_name}</span>
                  <span className="detail-meta-value">{attr.display_value}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      {tab === 'Suppliers' && (
        supplierLinks.length === 0 ? (
          <Card><div className="card-body" style={{ color: 'var(--text-secondary)' }}>
            No suppliers linked to this material yet.
          </div></Card>
        ) : (
          <Table
            columns={[
              { key: 'supplier_name', label: 'Supplier' },
              { key: 'supplier_price', label: 'Price', render: (v) => v ? formatCurrency(v) : (isPrivileged ? '-' : 'Restricted') },
              { key: 'last_purchase_price', label: 'Last Purchase Price', render: (v) => v ? formatCurrency(v) : (isPrivileged ? '-' : 'Restricted') },
              { key: 'moq', label: 'MOQ', render: (v) => v || '-' },
              { key: 'lead_time_days', label: 'Lead Time', render: (v) => v ? `${v} days` : '-' },
              { key: 'is_preferred', label: 'Preferred', render: (v) => v ? <span className="status-badge status-ok">Preferred</span> : '' },
            ]}
            data={supplierLinks}
            emptyMessage="No suppliers linked to this material yet."
          />
        )
      )}

      {tab === 'Purchases' && isPrivileged && (
        <Table
          columns={[
            { key: 'purchase_code', label: 'Purchase' },
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'quantity', label: 'Quantity' }, { key: 'rate', label: 'Rate', render: formatCurrency },
            { key: 'invoice_total', label: 'Invoice Total', render: formatCurrency },
            { key: 'payment_status', label: 'Payment Status' },
          ]}
          data={purchases}
          emptyMessage="No purchase history for this material yet."
        />
      )}
      {tab === 'Purchases' && !isPrivileged && (
        <p className="page-summary">Purchase history is restricted to master accounts.</p>
      )}

      {tab === 'Issues' && (
        <Table
          columns={[
            { key: 'issue_code', label: 'Issue' },
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'quantity_issued', label: 'Quantity' }, { key: 'issued_to', label: 'Issued To' },
            { key: 'department', label: 'Department' },
          ]}
          data={issues}
          emptyMessage="No issue history for this material yet."
        />
      )}

      <Modal isOpen={showTransfer} title={`Transfer ${material.name}`} onClose={() => setShowTransfer(false)}>
        <p style={{ marginTop: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          Current stock: {material.current_stock} {material.unit} at {material.location || 'no location set'}.
        </p>
        <Form
          fields={[
            { name: 'to_location_id', label: 'Transfer To', type: 'select', required: true, options: allLocations.map((l) => ({ value: l.id, label: l.full_path })) },
            { name: 'from_location_id', label: 'Transfer From', type: 'select',
              options: allLocations.map((l) => ({ value: l.id, label: l.full_path })),
              placeholder: material.location || 'Primary location' },
            { name: 'quantity', label: `Quantity (${material.unit})`, type: 'number', required: true },
            { name: 'remarks', label: 'Remarks', type: 'textarea' },
          ]}
          onSubmit={handleTransfer} loading={stockLoading} submitText="Confirm Transfer"
        />
      </Modal>

      <Modal isOpen={showAdjust} title={`Adjust Stock - ${material.name}`} onClose={() => setShowAdjust(false)}>
        <p style={{ marginTop: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          Current stock: {material.current_stock} {material.unit}. Every adjustment is recorded with a reason.
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
              visibleIf: (fd) => fd.adjustment_type === 'Return from Issue',
              required: true,
              options: issues.map((i) => ({
                value: i.id, label: `${i.issue_code} - ${i.quantity_issued} ${material.unit} (${new Date(i.date).toLocaleDateString()})`,
              })) },
            { name: 'direction', label: 'Direction', type: 'select', required: true,
              visibleIf: (fd) => fd.adjustment_type !== 'Return from Issue',
              options: [
                { value: 'increase', label: 'Increase stock' }, { value: 'decrease', label: 'Decrease stock' },
              ] },
            { name: 'quantity', label: `Quantity (${material.unit})`, type: 'number', required: true },
            { name: 'location_id', label: 'Location', type: 'select',
              options: allLocations.map((l) => ({ value: l.id, label: l.full_path })),
              placeholder: material.location || 'Primary location' },
            { name: 'reason', label: 'Reason', type: 'textarea', required: true },
          ]}
          onSubmit={handleAdjust} loading={stockLoading} submitText="Confirm Adjustment"
        />
      </Modal>
    </div>
  );
}

export default MaterialDetailPage;
