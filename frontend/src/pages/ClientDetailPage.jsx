import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { clientsAPI, ordersAPI, estimatesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Card from '../components/common/Card';

function money(v) { return `Rs ${Number(v || 0).toLocaleString()}`; }

const TABS = ['Overview', 'Orders', 'Estimates'];

function ClientDetailPage() {
  const { clientId } = useParams();
  const navigate = useNavigate();
  const [client, setClient] = useState(null);
  const [orders, setOrders] = useState([]);
  const [estimates, setEstimates] = useState([]);
  const [tab, setTab] = useState('Overview');

  const load = useCallback(() => {
    clientsAPI.get(clientId).then((res) => setClient(res.data)).catch(() => setClient(null));
    ordersAPI.list({ client_id: clientId }).then((res) => setOrders(res.data));
    estimatesAPI.list({ client_id: clientId }).then((res) => setEstimates(res.data));
  }, [clientId]);

  useEffect(load, [load]);

  if (!client) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/clients" className="btn-link">&larr; Back to Clients</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{client.name}</h1>
          <div className="detail-subtitle">{client.client_code} &middot; {client.lead_source || 'Lead source not recorded'}</div>
        </div>
      </div>

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Total Orders</div><h3>{client.total_orders}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Total Sales</div><h3>{money(client.total_sales)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Phone</div><h3 style={{ fontSize: '1.1rem' }}>{client.phone || '-'}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Email</div><h3 style={{ fontSize: '1.1rem' }}>{client.email || '-'}</h3></div></Card>
      </div>

      <div className="tab-bar">
        {TABS.map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && (
        <Card title="Client Details">
          <div className="card-body">
            <div className="detail-meta">
              <div className="detail-meta-item"><span className="detail-meta-label">Address</span><span className="detail-meta-value">{client.address || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">First Contact</span><span className="detail-meta-value">{client.first_contact_date ? new Date(client.first_contact_date).toLocaleDateString() : '-'}</span></div>
            </div>
            {client.remarks && (
              <div style={{ marginTop: 16 }}>
                <span className="detail-meta-label">Remarks</span>
                <p>{client.remarks}</p>
              </div>
            )}
          </div>
        </Card>
      )}

      {tab === 'Orders' && (
        <Table
          columns={[
            { key: 'order_code', label: 'Order' }, { key: 'project_type', label: 'Project Type' },
            { key: 'order_value', label: 'Order Value', render: money },
            { key: 'total_received', label: 'Received', render: money },
            { key: 'balance', label: 'Balance', render: money },
            { key: 'project_status', label: 'Status' },
          ]}
          data={orders}
          onRowClick={(row) => navigate(`/orders/${row.id}`)}
          emptyMessage="No orders for this client yet."
        />
      )}

      {tab === 'Estimates' && (
        <Table
          columns={[
            { key: 'estimate_code', label: 'Estimate' }, { key: 'description', label: 'Description' },
            { key: 'total_cost', label: 'Total', render: money }, { key: 'status', label: 'Status' },
          ]}
          data={estimates}
          emptyMessage="No estimates for this client yet."
        />
      )}
    </div>
  );
}

export default ClientDetailPage;
