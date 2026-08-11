import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { estimatesAPI, clientsAPI, ordersAPI, reportsAPI } from '../utils/api';
import Card from '../components/common/Card';
import { statusClass } from '../utils/statusColors';

function money(v) { return `Rs ${Number(v || 0).toLocaleString()}`; }

function EstimateDetailPage() {
  const { estimateId } = useParams();
  const [estimate, setEstimate] = useState(null);
  const [client, setClient] = useState(null);
  const [order, setOrder] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    estimatesAPI.get(estimateId).then((res) => {
      setEstimate(res.data);
      if (res.data.client_id) clientsAPI.get(res.data.client_id).then((r) => setClient(r.data)).catch(() => {});
      if (res.data.order_id) ordersAPI.get(res.data.order_id).then((r) => setOrder(r.data)).catch(() => {});
    }).catch(() => setError('Unable to load this estimate.'));
  }, [estimateId]);

  useEffect(load, [load]);

  if (error) return <div className="page">{error}</div>;
  if (!estimate) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/estimates" className="btn-link">&larr; Back to Estimates</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{estimate.estimate_code}</h1>
          <div className="detail-subtitle">
            {client?.name || 'Client'}
            {' '}<span className={`status-badge ${statusClass(estimate.status)}`}>{estimate.status}</span>
          </div>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl(`estimates/${estimate.id}/quote.pdf`)} target="_blank" rel="noreferrer">
            Download Quote PDF
          </a>
        </div>
      </div>

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Material Cost</div><h3>{money(estimate.material_cost)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Labor Cost</div><h3>{money(estimate.labor_cost)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Tax ({Number(estimate.tax_percent)}%)</div><h3>{money(estimate.tax_amount)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Total Estimate</div><h3>{money(estimate.total_cost)}</h3></div></Card>
      </div>

      <Card title="Estimate Details">
        <div className="card-body">
          <div className="detail-meta">
            <div className="detail-meta-item"><span className="detail-meta-label">Client</span><span className="detail-meta-value">{client ? <Link to={`/clients/${client.id}`}>{client.name}</Link> : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Related Order</span><span className="detail-meta-value">{order ? <Link to={`/orders/${order.id}`}>{order.order_code}</Link> : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Valid Until</span><span className="detail-meta-value">{estimate.valid_until ? new Date(estimate.valid_until).toLocaleDateString() : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Created</span><span className="detail-meta-value">{new Date(estimate.created_at).toLocaleDateString()}</span></div>
          </div>
          {estimate.description && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Scope</span>
              <p>{estimate.description}</p>
            </div>
          )}
          {estimate.remarks && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Remarks</span>
              <p>{estimate.remarks}</p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

export default EstimateDetailPage;
