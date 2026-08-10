import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { clientsAPI, ordersAPI, estimatesAPI, paymentsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Card from '../components/common/Card';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function money(v) { return `Rs ${Number(v || 0).toLocaleString()}`; }

const TABS = ['Overview', 'Orders', 'Estimates'];

function ClientDetailPage() {
  const { clientId } = useParams();
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const canViewFinancials = user?.role === 'master' || user?.role === 'manager';
  const [client, setClient] = useState(null);
  const [orders, setOrders] = useState([]);
  const [estimates, setEstimates] = useState([]);
  const [tab, setTab] = useState('Overview');
  const [activeAction, setActiveAction] = useState(null); // 'order' | 'estimate' | 'payment'
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState('');

  const load = useCallback(() => {
    clientsAPI.get(clientId).then((res) => setClient(res.data)).catch(() => setClient(null));
    ordersAPI.list({ client_id: clientId }).then((res) => setOrders(res.data));
    estimatesAPI.list({ client_id: clientId }).then((res) => setEstimates(res.data));
  }, [clientId]);

  useEffect(load, [load]);

  const closeAction = () => { setActiveAction(null); setActionError(''); };

  const handleCreateOrder = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await ordersAPI.create({
        ...formData, client_id: Number(clientId),
        order_date: new Date(formData.order_date).toISOString(),
        order_value: formData.order_value || '0', advance: formData.advance || '0',
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to create order'); }
    finally { setActionLoading(false); }
  };

  const handleCreateEstimate = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await estimatesAPI.create({
        ...formData, client_id: Number(clientId),
        material_cost: formData.material_cost || '0', labor_cost: formData.labor_cost || '0',
        tax_percent: formData.tax_percent || '18',
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to create estimate'); }
    finally { setActionLoading(false); }
  };

  const handleRecordPayment = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await paymentsAPI.create({
        ...formData, order_id: Number(formData.order_id), date: new Date(formData.date).toISOString(),
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to record payment'); }
    finally { setActionLoading(false); }
  };

  if (!client) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/clients" className="btn-link">&larr; Back to Clients</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{client.name}</h1>
          <div className="detail-subtitle">{client.client_code} &middot; {client.lead_source || 'Lead source not recorded'}</div>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => setActiveAction('order')}>Create Order</button>
          <button className="btn-secondary" onClick={() => setActiveAction('estimate')}>Create Estimate</button>
          {canViewFinancials && orders.length > 0 && (
            <button className="btn-secondary" onClick={() => setActiveAction('payment')}>Record Payment</button>
          )}
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

      <Modal isOpen={activeAction === 'order'} title="Create Order" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'order_code', label: 'Order Code', required: true, placeholder: 'WC-2026-011' },
            { name: 'project_type', label: 'Project Type' },
            { name: 'order_value', label: 'Order Value', type: 'number', required: true },
            { name: 'advance', label: 'Advance', type: 'number' },
            { name: 'order_date', label: 'Order Date', type: 'date', required: true },
          ]}
          onSubmit={handleCreateOrder} loading={actionLoading} submitText="Create Order"
        />
      </Modal>

      <Modal isOpen={activeAction === 'estimate'} title="Create Estimate" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'estimate_code', label: 'Estimate Code', required: true, placeholder: 'EST-011' },
            { name: 'description', label: 'Scope / Description', type: 'textarea' },
            { name: 'material_cost', label: 'Material Cost', type: 'number', required: true },
            { name: 'labor_cost', label: 'Labor Cost', type: 'number', required: true },
            { name: 'tax_percent', label: 'Tax %', type: 'number', placeholder: '18' },
          ]}
          onSubmit={handleCreateEstimate} loading={actionLoading} submitText="Create Estimate"
        />
      </Modal>

      <Modal isOpen={activeAction === 'payment'} title="Record Payment" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'order_id', label: 'Order', type: 'select', required: true, options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
            { name: 'receipt_code', label: 'Receipt Code', required: true, placeholder: 'RCPT-011' },
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'payment_type', label: 'Payment Type', type: 'select', required: true, options: [
              { value: 'Advance', label: 'Advance' }, { value: 'Progress Payment', label: 'Progress Payment' }, { value: 'Internal', label: 'Internal' },
            ] },
            { name: 'payment_mode', label: 'Payment Mode', type: 'select', required: true, options: [
              { value: 'Cash', label: 'Cash' }, { value: 'UPI', label: 'UPI' }, { value: 'Bank', label: 'Bank' }, { value: 'Credit Card', label: 'Credit Card' },
            ] },
            { name: 'amount', label: 'Amount', type: 'number', required: true },
            { name: 'received_by', label: 'Received By' },
          ]}
          onSubmit={handleRecordPayment} loading={actionLoading} submitText="Record Payment"
        />
      </Modal>
    </div>
  );
}

export default ClientDetailPage;
