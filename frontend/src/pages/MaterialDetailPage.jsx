import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { materialsAPI, purchasesAPI, issuesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Card from '../components/common/Card';
import { statusClass } from '../utils/statusColors';
import { formatCurrency } from '../utils/currency';

const TABS = ['Overview', 'Purchases', 'Issues'];

function MaterialDetailPage() {
  const { materialId } = useParams();
  const [material, setMaterial] = useState(null);
  const [purchases, setPurchases] = useState([]);
  const [issues, setIssues] = useState([]);
  const [tab, setTab] = useState('Overview');

  const load = useCallback(() => {
    materialsAPI.get(materialId).then((res) => setMaterial(res.data)).catch(() => setMaterial(null));
    purchasesAPI.list({ material_id: materialId }).then((res) => setPurchases(res.data));
    issuesAPI.list({ material_id: materialId }).then((res) => setIssues(res.data));
  }, [materialId]);

  useEffect(load, [load]);

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
          </div>
        </div>
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

      {tab === 'Purchases' && (
        <Table
          columns={[
            { key: 'purchase_code', label: 'Purchase' },
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'quantity', label: 'Quantity' }, { key: 'rate', label: 'Rate', render: money },
            { key: 'invoice_total', label: 'Invoice Total', render: money },
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
