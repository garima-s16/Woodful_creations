import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { clientsAPI, ordersAPI, estimatesAPI, paymentsAPI, clientActivitiesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Card from '../components/common/Card';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { formatCurrency } from '../utils/currency';
import { today } from '../utils/dates';


function ClientDetailPage() {
  const { clientId } = useParams();
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const canViewFinancials = user?.role === 'master' || user?.role === 'manager';
  const TABS = canViewFinancials ? ['Overview', 'Orders', 'Estimates', 'Payments', 'Activity'] : ['Overview', 'Orders', 'Estimates', 'Activity'];
  const [client, setClient] = useState(null);
  const [orders, setOrders] = useState([]);
  const [estimates, setEstimates] = useState([]);
  const [payments, setPayments] = useState([]);
  const [activities, setActivities] = useState([]);
  const [tab, setTab] = useState('Overview');
  const [activeAction, setActiveAction] = useState(null); // 'order' | 'estimate' | 'payment' | 'activity'
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState('');

  const load = useCallback(() => {
    clientsAPI.get(clientId).then((res) => setClient(res.data)).catch(() => setClient(null));
    ordersAPI.list({ client_id: clientId }).then((res) => setOrders(res.data));
    if (canViewFinancials) {
      paymentsAPI.list({ client_id: clientId }).then((res) => setPayments(res.data)).catch(() => setPayments([]));
    }
    estimatesAPI.list({ client_id: clientId }).then((res) => setEstimates(res.data));
    clientActivitiesAPI.list({ client_id: clientId }).then((res) => setActivities(res.data));
  }, [clientId, canViewFinancials]);

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

  const handleLogActivity = async (formData) => {
    setActionLoading(true); setActionError('');
    try {
      await clientActivitiesAPI.create({
        ...formData, client_id: Number(clientId), date: new Date(formData.date).toISOString(),
      });
      closeAction(); load();
    } catch (err) { setActionError(err.response?.data?.detail || 'Failed to log activity'); }
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
          <button className="btn-secondary" onClick={() => setActiveAction('activity')}>Log Activity</button>
        </div>
      </div>

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Total Orders</div><h3>{client.total_orders}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Total Sales</div><h3>{formatCurrency(client.total_sales)}</h3></div></Card>
        {canViewFinancials && (
          <Card><div className="card-body"><div className="detail-meta-label">Outstanding Balance</div><h3>{formatCurrency(orders.reduce((sum, o) => sum + Number(o.balance || 0), 0))}</h3></div></Card>
        )}
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
            { key: 'order_value', label: 'Order Value', render: formatCurrency },
            { key: 'total_received', label: 'Received', render: formatCurrency },
            { key: 'balance', label: 'Balance', render: formatCurrency },
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
            { key: 'total_cost', label: 'Total', render: formatCurrency }, { key: 'status', label: 'Status' },
          ]}
          data={estimates}
          emptyMessage="No estimates for this client yet."
        />
      )}

      {tab === 'Payments' && (
        <Table
          columns={[
            { key: 'receipt_code', label: 'Receipt' },
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'order_id', label: 'Order', render: (v) => orders.find((o) => o.id === v)?.order_code || v },
            { key: 'payment_type', label: 'Type' }, { key: 'payment_mode', label: 'Mode' },
            { key: 'amount', label: 'Amount', render: formatCurrency },
          ]}
          data={payments}
          emptyMessage="No payments recorded for this client yet."
        />
      )}

      {tab === 'Activity' && (
        <Table
          columns={[
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleString() },
            { key: 'activity_type', label: 'Type' }, { key: 'summary', label: 'Summary' },
            { key: 'logged_by', label: 'Logged By' },
          ]}
          data={activities}
          emptyMessage="No activity logged for this client yet. Log calls, meetings, and site visits here."
        />
      )}

      <Modal isOpen={activeAction === 'order'} title="Create Order" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'project_type', label: 'Project Type' },
            { name: 'order_value', label: 'Order Value', type: 'number', required: true },
            { name: 'advance', label: 'Advance', type: 'number' },
            { name: 'order_date', label: 'Order Date', type: 'date', required: true },
          ]}
          onSubmit={handleCreateOrder} loading={actionLoading} submitText="Create Order"
          initialValues={{ order_date: today() }}
        />
      </Modal>

      <Modal isOpen={activeAction === 'estimate'} title="Create Estimate" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
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
          initialValues={{ date: today(), received_by: user?.full_name || user?.username || '' }}
        />
      </Modal>

      <Modal isOpen={activeAction === 'activity'} title="Log Activity" onClose={closeAction}>
        {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}
        <Form
          fields={[
            { name: 'activity_type', label: 'Activity Type', type: 'select', required: true, options: [
              { value: 'Call', label: 'Call' }, { value: 'Meeting', label: 'Meeting' },
              { value: 'Email', label: 'Email' }, { value: 'Site Visit', label: 'Site Visit' }, { value: 'Note', label: 'Note' },
            ] },
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'summary', label: 'Summary', type: 'textarea', required: true },
            { name: 'logged_by', label: 'Logged By' },
          ]}
          onSubmit={handleLogActivity} loading={actionLoading} submitText="Log Activity"
          initialValues={{ date: today(), logged_by: user?.full_name || user?.username || '' }}
        />
      </Modal>
    </div>
  );
}

export default ClientDetailPage;
