import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { purchasesAPI, suppliersAPI, materialsAPI } from '../utils/api';
import Card from '../components/common/Card';
import Alert from '../components/common/Alert';
import { formatCurrency } from '../utils/currency';
import { statusClass } from '../utils/statusColors';

function PurchaseDetailPage() {
  const { purchaseId } = useParams();
  const [purchase, setPurchase] = useState(null);
  const [supplier, setSupplier] = useState(null);
  const [material, setMaterial] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    purchasesAPI.get(purchaseId).then((res) => {
      setPurchase(res.data);
      if (res.data.supplier_id) suppliersAPI.get(res.data.supplier_id).then((r) => setSupplier(r.data)).catch(() => {});
      if (res.data.material_id) materialsAPI.get(res.data.material_id).then((r) => setMaterial(r.data)).catch(() => {});
    }).catch(() => setError('Unable to load this purchase.'));
  }, [purchaseId]);

  useEffect(load, [load]);

  if (error) return <div className="page"><Alert type="error" message={error} /></div>;
  if (!purchase) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{purchase.purchase_code}</h1>
          <div className="detail-subtitle">
            {supplier?.name || 'Supplier'} &middot; {material?.name || 'Material'}
            {purchase.business_id && <span className="business-id-badge">{purchase.business_id}</span>}
          </div>
        </div>
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
              <span className="detail-meta-value">{supplier?.name || '-'}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Material</span>
              <span className="detail-meta-value">{material?.name || '-'}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Taxable Value</span>
              <span className="detail-meta-value">{formatCurrency(purchase.taxable_value)}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Payment Status</span>
              <span className={`status-badge ${statusClass(purchase.payment_status)}`}>{purchase.payment_status}</span>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default PurchaseDetailPage;
