import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ordersAPI, clientsAPI, paymentsAPI, projectExpensesAPI, issuesAPI,
  dailyTasksAPI, productionJobsAPI, materialsAPI, reportsAPI,
} from '../utils/api';
import Table from '../components/common/Table';
import Card from '../components/common/Card';
import Alert from '../components/common/Alert';

function money(v) {
  return `Rs ${Number(v || 0).toLocaleString()}`;
}

function statusClass(status) {
  const s = (status || '').toLowerCase().replace(/\s+/g, '-');
  if (['completed', 'paid', 'in stock'].includes(s)) return 'status-ok';
  if (['pending', 'in-progress', 'not-started'].includes(s)) return 'status-warning';
  if (['overdue', 'out-of-stock', 'cancelled'].includes(s)) return 'status-danger';
  return 'status-info';
}

const TABS = ['Overview', 'Payments', 'Expenses', 'Materials', 'Tasks', 'Production', 'Profitability'];

function OrderDetailPage() {
  const { orderId } = useParams();
  const [order, setOrder] = useState(null);
  const [client, setClient] = useState(null);
  const [materials, setMaterials] = useState([]);
  const [payments, setPayments] = useState(null);
  const [expenses, setExpenses] = useState(null);
  const [issues, setIssues] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [productionJobs, setProductionJobs] = useState([]);
  const [profitability, setProfitability] = useState(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('Overview');

  const load = useCallback(() => {
    ordersAPI.get(orderId).then((res) => {
      setOrder(res.data);
      clientsAPI.get(res.data.client_id).then((r) => setClient(r.data)).catch(() => {});
    }).catch(() => setError('Unable to load this order.'));

    materialsAPI.list().then((res) => setMaterials(res.data));
    issuesAPI.list({ order_id: orderId }).then((res) => setIssues(res.data));
    dailyTasksAPI.list({ order_id: orderId }).then((res) => setTasks(res.data));
    productionJobsAPI.list({ order_id: orderId }).then((res) => setProductionJobs(res.data));

    paymentsAPI.list({ order_id: orderId }).then((res) => setPayments(res.data)).catch(() => setPayments('forbidden'));
    projectExpensesAPI.list({ order_id: orderId }).then((res) => setExpenses(res.data)).catch(() => setExpenses('forbidden'));
    ordersAPI.profitability(orderId).then((res) => setProfitability(res.data)).catch(() => setProfitability('forbidden'));
  }, [orderId]);

  useEffect(load, [load]);

  if (error) return <div className="page"><Alert type="error" message={error} /></div>;
  if (!order) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/orders" className="btn-link">&larr; Back to Orders</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{order.order_code}</h1>
          <div className="detail-subtitle">
            {client?.name || 'Client'} &middot; {order.project_type || 'Project'}
          </div>
          <div className="detail-meta">
            <div className="detail-meta-item">
              <span className="detail-meta-label">Stage</span>
              <span className={`status-badge ${statusClass(order.project_status)}`}>{order.project_status}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Design</span>
              <span className={`status-badge ${statusClass(order.design_status)}`}>{order.design_status}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Execution</span>
              <span className={`status-badge ${statusClass(order.execution_status)}`}>{order.execution_status}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Delivery</span>
              <span className={`status-badge ${statusClass(order.delivery_status)}`}>{order.delivery_status}</span>
            </div>
          </div>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl(`orders/${order.id}/estimate.pdf`)} target="_blank" rel="noreferrer">
            Download Estimate PDF
          </a>
        </div>
      </div>

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Order Value</div><h3>{money(order.order_value)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Amount Received</div><h3>{money(order.total_received)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Outstanding Balance</div><h3>{money(order.balance)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Progress</div><h3>{order.progress_percent}%</h3></div></Card>
      </div>

      <div className="tab-bar">
        {TABS.map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Overview' && (
        <Card title="Project Overview">
          <div className="card-body">
            <div className="detail-meta">
              <div className="detail-meta-item"><span className="detail-meta-label">Client Phone</span><span className="detail-meta-value">{client?.phone || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Client Email</span><span className="detail-meta-value">{client?.email || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Order Date</span><span className="detail-meta-value">{new Date(order.order_date).toLocaleDateString()}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Delivery Date</span><span className="detail-meta-value">{order.delivery_date ? new Date(order.delivery_date).toLocaleDateString() : '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Supervisor</span><span className="detail-meta-value">{order.supervisor || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Priority</span><span className="detail-meta-value">{order.priority || '-'}</span></div>
            </div>
            {order.site_address && (
              <div style={{ marginTop: 16 }}>
                <span className="detail-meta-label">Site Address</span>
                <p>{order.site_address}</p>
              </div>
            )}
            {order.remarks && (
              <div style={{ marginTop: 16 }}>
                <span className="detail-meta-label">Remarks</span>
                <p>{order.remarks}</p>
              </div>
            )}
          </div>
        </Card>
      )}

      {tab === 'Payments' && (
        payments === 'forbidden'
          ? <Alert type="info" message="You do not have permission to view payments for this order." />
          : (
            <Table
              columns={[
                { key: 'receipt_code', label: 'Receipt' },
                { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
                { key: 'payment_type', label: 'Type' }, { key: 'payment_mode', label: 'Mode' },
                { key: 'amount', label: 'Amount', render: money },
                { key: 'received_by', label: 'Received By' },
              ]}
              data={payments || []}
              emptyMessage="No payments recorded for this order yet."
            />
          )
      )}

      {tab === 'Expenses' && (
        expenses === 'forbidden'
          ? <Alert type="info" message="You do not have permission to view expenses for this order." />
          : (
            <Table
              columns={[
                { key: 'expense_code', label: 'Expense' },
                { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
                { key: 'category', label: 'Category' }, { key: 'description', label: 'Description' },
                { key: 'amount', label: 'Amount', render: money },
              ]}
              data={expenses || []}
              emptyMessage="No project expenses recorded yet."
            />
          )
      )}

      {tab === 'Materials' && (
        <Table
          columns={[
            { key: 'issue_code', label: 'Issue' },
            { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
            { key: 'material_id', label: 'Material', render: (v) => materials.find((m) => m.id === v)?.name || v },
            { key: 'quantity_issued', label: 'Quantity' }, { key: 'issued_to', label: 'Issued To' },
          ]}
          data={issues}
          emptyMessage="No materials issued to this project yet."
        />
      )}

      {tab === 'Tasks' && (
        <Table
          columns={[
            { key: 'task_code', label: 'Task' }, { key: 'task_description', label: 'Description' },
            { key: 'priority', label: 'Priority' },
            { key: 'status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
            { key: 'completion_percent', label: 'Completion %' },
          ]}
          data={tasks}
          emptyMessage="No tasks assigned to this project yet."
        />
      )}

      {tab === 'Production' && (
        <Table
          columns={[
            { key: 'job_code', label: 'Job' }, { key: 'machine', label: 'Machine' },
            { key: 'operation', label: 'Operation' },
            { key: 'planned_qty', label: 'Planned' }, { key: 'completed_qty', label: 'Completed' },
            { key: 'status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
          ]}
          data={productionJobs}
          emptyMessage="No production jobs recorded for this project yet."
        />
      )}

      {tab === 'Profitability' && (
        profitability === 'forbidden'
          ? <Alert type="info" message="You do not have permission to view profitability for this order." />
          : profitability && (
            <Card title="Order Profitability">
              <div className="card-body">
                <div className="detail-meta">
                  <div className="detail-meta-item"><span className="detail-meta-label">Order Value</span><span className="detail-meta-value">{money(profitability.order_value)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Total Received</span><span className="detail-meta-value">{money(profitability.total_received)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Pending Payment</span><span className="detail-meta-value">{money(profitability.pending_payment)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Project Expenses</span><span className="detail-meta-value">{money(profitability.project_expenses)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Estimated Gross Profit</span><span className="detail-meta-value">{money(profitability.estimated_gross_profit)}</span></div>
                  <div className="detail-meta-item"><span className="detail-meta-label">Gross Margin</span><span className="detail-meta-value">{(profitability.gross_margin_percent * 100).toFixed(1)}%</span></div>
                </div>
              </div>
            </Card>
          )
      )}
    </div>
  );
}

export default OrderDetailPage;
