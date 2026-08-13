import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import { materialsAPI, purchasesAPI, issuesAPI, supplierMaterialsAPI } from '../utils/api';
import { addToCart } from '../redux/slices/cartSlice';
import Table from '../components/common/Table';
import Card from '../components/common/Card';
import { statusClass } from '../utils/statusColors';
import { formatCurrency } from '../utils/currency';

const TABS = ['Overview', 'Suppliers', 'Purchases', 'Issues'];

function MaterialDetailPage() {
  const { materialId } = useParams();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const [material, setMaterial] = useState(null);
  const [purchases, setPurchases] = useState([]);
  const [issues, setIssues] = useState([]);
  const [supplierLinks, setSupplierLinks] = useState([]);
  const [tab, setTab] = useState('Overview');
  const [addedToCart, setAddedToCart] = useState(false);

  const load = useCallback(() => {
    materialsAPI.get(materialId).then((res) => setMaterial(res.data)).catch(() => setMaterial(null));
    purchasesAPI.list({ material_id: materialId }).then((res) => setPurchases(res.data));
    issuesAPI.list({ material_id: materialId }).then((res) => setIssues(res.data));
    supplierMaterialsAPI.byMaterial(materialId).then((res) => setSupplierLinks(res.data)).catch(() => setSupplierLinks([]));
  }, [materialId]);

  useEffect(load, [load]);

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
        <button className="btn-primary" onClick={handleAddToCart}>
          {addedToCart ? 'Added!' : 'Add to Purchase Cart'}
        </button>
      </div>

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Available Stock</div><h3>{material.current_stock} {material.unit}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Reorder Level</div><h3>{material.minimum_stock} {material.unit}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Average Rate</div><h3>{formatCurrency(material.average_rate)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Stock Value</div><h3>{formatCurrency(material.stock_value)}</h3></div></Card>
      </div>

      <div className="tab-bar">
        {TABS.map((t) => (
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
              { key: 'supplier_price', label: 'Price', render: (v) => v ? formatCurrency(v) : '-' },
              { key: 'last_purchase_price', label: 'Last Purchase Price', render: (v) => v ? formatCurrency(v) : '-' },
              { key: 'moq', label: 'MOQ', render: (v) => v || '-' },
              { key: 'lead_time_days', label: 'Lead Time', render: (v) => v ? `${v} days` : '-' },
              { key: 'is_preferred', label: 'Preferred', render: (v) => v ? <span className="status-badge status-ok">Preferred</span> : '' },
            ]}
            data={supplierLinks}
            emptyMessage="No suppliers linked to this material yet."
          />
        )
      )}

      {tab === 'Purchases' && (
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
    </div>
  );
}

export default MaterialDetailPage;
