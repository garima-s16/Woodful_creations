import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardAPI, dailyTasksAPI, purchasesAPI, paymentsAPI } from '../utils/api';
import KpiCard from '../components/common/KpiCard';
import Card from '../components/common/Card';
import Table from '../components/common/Table';

function money(v) { return `Rs ${Number(v || 0).toLocaleString()}`; }

function AttentionRequired({ stock, orders, pendingTasks }) {
  const navigate = useNavigate();
  const lowStock = (stock?.low_stock_action_list || []).slice(0, 4);
  const onHoldOrders = (orders?.top_orders || []).filter((o) => o.status === 'On Hold').slice(0, 4);
  const outstandingOrders = (orders?.top_orders || []).filter((o) => o.pending > 0).slice(0, 4);
  const tasks = (pendingTasks || []).slice(0, 4);

  const hasAny = lowStock.length || onHoldOrders.length || outstandingOrders.length || tasks.length;
  if (!hasAny) {
    return (
      <Card title="Attention Required">
        <div className="card-body" style={{ color: 'var(--text-secondary)' }}>Nothing needs attention right now.</div>
      </Card>
    );
  }

  return (
    <Card title="Attention Required">
      <div className="card-body attention-grid">
        {lowStock.length > 0 && (
          <div className="attention-column">
            <h4>Low Stock Materials</h4>
            {lowStock.map((m) => (
              <button key={m.material} className="attention-item" onClick={() => navigate(`/materials/${m.id}`)}>
                <span>{m.material}</span>
                <span className="status-badge status-warning">{m.current}/{m.minimum}</span>
              </button>
            ))}
          </div>
        )}
        {onHoldOrders.length > 0 && (
          <div className="attention-column">
            <h4>Delayed Projects</h4>
            {onHoldOrders.map((o) => (
              <button key={o.order_id} className="attention-item" onClick={() => navigate(`/orders/${o.id}`)}>
                <span>{o.order_id} - {o.client}</span>
                <span className="status-badge status-danger">On Hold</span>
              </button>
            ))}
          </div>
        )}
        {outstandingOrders.length > 0 && (
          <div className="attention-column">
            <h4>Outstanding Payments</h4>
            {outstandingOrders.map((o) => (
              <button key={o.order_id} className="attention-item" onClick={() => navigate(`/orders/${o.id}`)}>
                <span>{o.order_id} - {o.client}</span>
                <span className="status-badge status-warning">Rs {o.pending.toLocaleString()}</span>
              </button>
            ))}
          </div>
        )}
        {tasks.length > 0 && (
          <div className="attention-column">
            <h4>Pending Tasks</h4>
            {tasks.map((t) => (
              <button key={t.id} className="attention-item" onClick={() => navigate(`/daily-tasks/${t.id}`)}>
                <span>{t.task_description}</span>
                <span className="status-badge status-warning">{t.priority || 'Normal'}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function RecentActivity({ items }) {
  if (!items.length) {
    return (
      <Card title="Recent Activity">
        <div className="card-body" style={{ color: 'var(--text-secondary)' }}>No recent activity yet.</div>
      </Card>
    );
  }
  return (
    <Card title="Recent Activity">
      <div className="card-body">
        {items.map((item, i) => (
          <div key={i} className="activity-row">
            <span className={`status-badge status-info`}>{item.type}</span>
            <span className="activity-desc">{item.description}</span>
            <span className="activity-date">{new Date(item.date).toLocaleDateString()}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function DashboardPage() {
  const [stock, setStock] = useState(null);
  const [orders, setOrders] = useState(null);
  const [staff, setStaff] = useState(null);
  const [pendingTasks, setPendingTasks] = useState([]);
  const [activity, setActivity] = useState([]);

  useEffect(() => {
    dashboardAPI.stock().then((res) => setStock(res.data)).catch(() => {});
    dashboardAPI.orders().then((res) => setOrders(res.data)).catch(() => {});
    dashboardAPI.staff().then((res) => setStaff(res.data)).catch(() => {});
    dailyTasksAPI.list({ status: 'Not Started' }).then((res) => setPendingTasks(res.data)).catch(() => {});

    Promise.all([
      purchasesAPI.list().then((r) => r.data).catch(() => []),
      paymentsAPI.list().then((r) => r.data).catch(() => []),
    ]).then(([purchases, payments]) => {
      const feed = [
        ...purchases.slice(0, 4).map((p) => ({ type: 'Purchase', description: `${p.purchase_code} - ${money(p.invoice_total)}`, date: p.date })),
        ...payments.slice(0, 4).map((p) => ({ type: 'Payment', description: `${p.receipt_code} - ${money(p.amount)}`, date: p.date })),
      ].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 8);
      setActivity(feed);
    });
  }, []);

  if (!stock || !orders || !staff) return <div className="page">Loading...</div>;

  const grossMargin = orders.total_order_value
    ? (orders.order_profitability.reduce((s, o) => s + o.estimated_gross_profit, 0) / orders.total_order_value) * 100
    : 0;

  return (
    <div className="page dashboard-page">
      <div className="dashboard-header">
        <span className="dashboard-eyebrow">Woodful Creations</span>
        <h1>Business Overview</h1>
      </div>

      <div className="hero-metrics">
        <div className="hero-metric">
          <span className="hero-label">Revenue</span>
          <span className="hero-value">{money(orders.total_order_value)}</span>
        </div>
        <div className="hero-metric">
          <span className="hero-label">Outstanding</span>
          <span className="hero-value hero-warning">{money(orders.pending_payment)}</span>
        </div>
        <div className="hero-metric">
          <span className="hero-label">Inventory Value</span>
          <span className="hero-value">{money(stock.total_stock_value)}</span>
        </div>
        <div className="hero-metric">
          <span className="hero-label">Gross Margin</span>
          <span className="hero-value">{grossMargin.toFixed(1)}%</span>
        </div>
      </div>

      <div className="secondary-metrics">
        <KpiCard label="Amount Received" value={money(orders.total_received)} />
        <KpiCard label="Active Orders" value={orders.active_orders} />
        <KpiCard label="Low Stock Items" value={stock.low_stock_items} tone={stock.low_stock_items > 0 ? 'warning' : 'success'} />
        <KpiCard label="Out of Stock" value={stock.out_of_stock_items} tone={stock.out_of_stock_items > 0 ? 'danger' : 'success'} />
        <KpiCard label="Active Employees" value={staff.active_employees} />
        <KpiCard label="Pending Tasks" value={staff.pending_tasks} tone={staff.pending_tasks > 0 ? 'warning' : 'success'} />
      </div>

      <section className="dashboard-section">
        <h2 className="section-heading">Business Activity</h2>
        <div className="dashboard-grid">
          <Card title="Order Pipeline">
            <Table columns={[{ key: 'status', label: 'Status' }, { key: 'orders', label: 'Orders' }]} data={orders.order_pipeline} />
          </Card>
          <Card title="Category Summary">
            <Table
              columns={[
                { key: 'category', label: 'Category' }, { key: 'items', label: 'Items' },
                { key: 'stock_value', label: 'Stock Value', render: money },
              ]}
              data={stock.category_summary}
            />
          </Card>
        </div>
      </section>

      <section className="dashboard-section">
        <h2 className="section-heading">Attention Required</h2>
        <AttentionRequired stock={stock} orders={orders} pendingTasks={pendingTasks} />
      </section>

      <section className="dashboard-section">
        <h2 className="section-heading">Projects &amp; Production</h2>
        <div className="dashboard-grid">
          <Card title="Task Status">
            <Table columns={[{ key: 'status', label: 'Status' }, { key: 'count', label: 'Count' }]} data={staff.task_status_summary} />
          </Card>
          <Card title="Top Orders & Payment Position">
            <Table
              columns={[
                { key: 'order_id', label: 'Order' }, { key: 'client', label: 'Client' },
                { key: 'pending', label: 'Pending', render: money }, { key: 'status', label: 'Status' },
              ]}
              data={orders.top_orders.slice(0, 6)}
            />
          </Card>
        </div>
      </section>

      <section className="dashboard-section">
        <h2 className="section-heading">Recent Activity</h2>
        <RecentActivity items={activity} />
      </section>
    </div>
  );
}

export default DashboardPage;
