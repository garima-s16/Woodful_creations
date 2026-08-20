import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { dashboardAPI, dailyTasksAPI, purchasesAPI, paymentsAPI, productionJobsAPI, ordersAPI, clientActivitiesAPI } from '../utils/api';
import KpiCard from '../components/common/KpiCard';
import Card from '../components/common/Card';
import Table from '../components/common/Table';
import SimpleBarChart from '../components/common/SimpleBarChart';
import { formatCurrency } from '../utils/currency';
import { today } from '../utils/dates';


function AttentionRequired({ stock, orders, pendingTasks, upcomingDeliveries, pendingPurchases, delayedProduction }) {
  const navigate = useNavigate();
  const lowStock = (stock?.low_stock_action_list || []).slice(0, 4);
  const onHoldOrders = (orders?.top_orders || []).filter((o) => o.status === 'On Hold').slice(0, 4);
  const outstandingOrders = (orders?.top_orders || []).filter((o) => o.pending > 0).slice(0, 4);
  const tasks = (pendingTasks || []).slice(0, 4);

  const hasAny = lowStock.length || onHoldOrders.length || outstandingOrders.length || tasks.length
    || upcomingDeliveries.length || pendingPurchases.length || delayedProduction.length;
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
                <span className="status-badge status-neutral">On Hold</span>
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
        {upcomingDeliveries.length > 0 && (
          <div className="attention-column">
            <h4>Upcoming Deliveries</h4>
            {upcomingDeliveries.map((o) => (
              <button key={o.id} className="attention-item" onClick={() => navigate(`/orders/${o.id}`)}>
                <span>{o.order_code} - {o.client?.name || 'Client'}</span>
                <span className="status-badge status-info">{new Date(o.delivery_date).toLocaleDateString()}</span>
              </button>
            ))}
          </div>
        )}
        {pendingPurchases.length > 0 && (
          <div className="attention-column">
            <h4>Purchases Pending Payment</h4>
            {pendingPurchases.map((p) => (
              <button key={p.id} className="attention-item" onClick={() => navigate(`/purchases/${p.id}`)}>
                <span>{p.purchase_code} - {p.supplier?.name || 'Supplier'}</span>
                <span className="status-badge status-warning">{p.payment_status}</span>
              </button>
            ))}
          </div>
        )}
        {delayedProduction.length > 0 && (
          <div className="attention-column">
            <h4>Production Jobs Open 7+ Days</h4>
            {delayedProduction.map((j) => (
              <button key={j.id} className="attention-item" onClick={() => navigate(`/production-jobs/${j.id}`)}>
                <span>{j.job_code} - {j.operation || 'Job'}</span>
                <span className="status-badge status-warning">{j.status}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

const PRODUCTION_STAGES = ['Not Started', 'In Progress', 'Completed'];

function ProductionPipeline({ summary }) {
  const counts = Object.fromEntries((summary || []).map((s) => [s.status, s.count]));
  const total = PRODUCTION_STAGES.reduce((sum, stage) => sum + (counts[stage] || 0), 0);
  if (!total) {
    return (
      <Card title="Production Pipeline">
        <div className="card-body" style={{ color: 'var(--text-secondary)' }}>No production jobs yet.</div>
      </Card>
    );
  }
  return (
    <Card title="Production Pipeline">
      <div className="card-body production-pipeline">
        {PRODUCTION_STAGES.map((stage, i) => (
          <React.Fragment key={stage}>
            <div className="pipeline-stage">
              <span className="pipeline-count">{counts[stage] || 0}</span>
              <span className="pipeline-label">{stage}</span>
            </div>
            {i < PRODUCTION_STAGES.length - 1 && <span className="pipeline-arrow">&rarr;</span>}
          </React.Fragment>
        ))}
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
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [stock, setStock] = useState(null);
  const [orders, setOrders] = useState(null);
  const [staff, setStaff] = useState(null);
  const [dashboardError, setDashboardError] = useState('');
  const [pendingTasks, setPendingTasks] = useState([]);
  const [activity, setActivity] = useState([]);
  const [upcomingDeliveries, setUpcomingDeliveries] = useState([]);
  const [pendingPurchases, setPendingPurchases] = useState([]);
  const [delayedProduction, setDelayedProduction] = useState([]);
  const [myTasks, setMyTasks] = useState([]);
  const [followUps, setFollowUps] = useState([]);

  const loadCriticalDashboardData = () => {
    setDashboardError('');
    Promise.all([dashboardAPI.stock(), dashboardAPI.orders(), dashboardAPI.staff()])
      .then(([stockRes, ordersRes, staffRes]) => {
        setStock(stockRes.data);
        setOrders(ordersRes.data);
        setStaff(staffRes.data);
      })
      .catch(() => {
        setDashboardError('Unable to load dashboard data. Please check your connection and try again.');
      });
  };

  const loadFollowUps = () => {
    clientActivitiesAPI.pendingFollowUps().then((res) => setFollowUps(res.data)).catch(() => {});
  };

  const handleCompleteFollowUp = (id) => {
    // Optimistic - the whole point of surfacing these is to let a
    // user clear their list quickly; wait for the round trip on
    // every click and it stops feeling worth using.
    setFollowUps((prev) => prev.filter((f) => f.id !== id));
    clientActivitiesAPI.completeFollowUp(id).catch(() => loadFollowUps());
  };

  useEffect(() => {
    loadFollowUps();
    loadCriticalDashboardData();
    dailyTasksAPI.list({ status: 'TO DO' }).then((res) => setPendingTasks(res.data)).catch(() => {});
    if (!isPrivileged) {
      dailyTasksAPI.list({ mine: true }).then((res) => setMyTasks(res.data)).catch(() => {});
    }

    // Upcoming deliveries: orders with a delivery_date in the next 14
    // days that aren't already completed - a real, direct field query.
    ordersAPI.list().then((res) => {
      const now = Date.now();
      const twoWeeksOut = now + 14 * 24 * 60 * 60 * 1000;
      const upcoming = res.data.filter((o) => {
        if (!o.delivery_date || o.project_status === 'Completed') return false;
        const t = new Date(o.delivery_date).getTime();
        return t >= now && t <= twoWeeksOut;
      }).slice(0, 4);
      setUpcomingDeliveries(upcoming);
    }).catch(() => {});

    // Production jobs open 7+ days: there is no planned-completion-date
    // field on ProductionJob, so this is a stated approximation (same
    // pattern as the Orders "30+ days overdue" filter) - not a precise
    // "delayed" status the data doesn't actually support.
    productionJobsAPI.list().then((res) => {
      const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
      const stale = res.data.filter((j) => j.status !== 'Completed' && new Date(j.date).getTime() < cutoff).slice(0, 4);
      setDelayedProduction(stale);
    }).catch(() => {});

    Promise.all([
      purchasesAPI.list().then((r) => r.data).catch(() => []),
      paymentsAPI.list().then((r) => r.data).catch(() => []),
    ]).then(([purchases, payments]) => {
      const feed = [
        ...purchases.slice(0, 4).map((p) => ({ type: 'Purchase', description: `${p.purchase_code} - ${formatCurrency(p.invoice_total)}`, date: p.date })),
        ...payments.slice(0, 4).map((p) => ({ type: 'Payment', description: `${p.receipt_code} - ${formatCurrency(p.amount)}`, date: p.date })),
      ].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 8);
      setActivity(feed);

      // Purchases still pending payment to the supplier - a direct
      // field query on data already being fetched for the activity feed.
      setPendingPurchases(purchases.filter((p) => p.payment_status !== 'Paid').slice(0, 4));
    });
  }, [isPrivileged]);

  if (dashboardError) {
    return (
      <div className="page">
        <div className="dashboard-error-state">
          <p>{dashboardError}</p>
          <button className="btn-primary" onClick={loadCriticalDashboardData}>Try Again</button>
        </div>
      </div>
    );
  }
  if (!stock || !orders || !staff) return <div className="page">Loading...</div>;

  const grossMargin = orders.total_order_value
    ? (orders.order_profitability.reduce((s, o) => s + o.estimated_gross_profit, 0) / orders.total_order_value) * 100
    : 0;

  const hour = new Date().getHours();
  const greeting = hour < 5 ? 'Good night' : hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : hour < 21 ? 'Good evening' : 'Good night';
  const firstName = user?.full_name?.split(' ')[0] || '';

  // Same source data and same filter/slice logic as AttentionRequired
  // below - kept side by side rather than computed twice from scratch,
  // so this summary and the detailed sections can never show different
  // counts for the same underlying situation.
  const topAttentionItems = [
    ...(stock?.low_stock_action_list || []).slice(0, 4).map((m) => ({
      severity: 'critical', title: m.material, detail: `${m.current}/${m.minimum} ${m.unit || ''} remaining`.trim(),
      path: `/materials/${m.id}`,
    })),
    ...(orders?.top_orders || []).filter((o) => o.pending > 0).slice(0, 4).map((o) => ({
      severity: 'warning', title: `${o.client} - ${o.order_id}`, detail: `Rs ${o.pending.toLocaleString()} outstanding`,
      path: `/orders/${o.id}`,
    })),
    ...(delayedProduction || []).slice(0, 4).map((j) => ({
      severity: 'warning', title: `${j.job_code} - ${j.operation || 'Production'}`, detail: `Open ${j.status?.toLowerCase() || ''}`.trim(),
      path: '/production-jobs',
    })),
  ].slice(0, 3);

  return (
    <div className="page dashboard-page">
      <div className="dashboard-header">
        <span className="dashboard-eyebrow">Woodful Creations</span>
        <h1>{greeting}{firstName ? `, ${firstName}` : ''}.</h1>
        <p className="dashboard-subtitle">A live snapshot of inventory, sales, and operations across the business.</p>
      </div>

      {topAttentionItems.length > 0 && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>{topAttentionItems.length} thing{topAttentionItems.length > 1 ? 's' : ''} need{topAttentionItems.length === 1 ? 's' : ''} your attention</h3>
            <div className="founder-attention-list">
              {topAttentionItems.map((item, idx) => (
                <div className="founder-attention-row" key={idx}>
                  <span className={`founder-attention-dot founder-attention-${item.severity}`} aria-hidden="true" />
                  <div className="founder-attention-text">
                    <strong>{item.title}</strong>
                    <span>{item.detail}</span>
                  </div>
                  <button className="btn-secondary" onClick={() => navigate(item.path)}>Review</button>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      <h2 className="section-heading">{isPrivileged ? 'Primary Business Metrics' : 'My Work'}</h2>
      <div className="hero-metrics">
        {isPrivileged ? (
          <>
            <div className="hero-metric">
              <span className="hero-label">Revenue</span>
              <span className="hero-value">{formatCurrency(orders.total_order_value)}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Outstanding</span>
              <span className="hero-value hero-warning">{formatCurrency(orders.pending_payment)}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Inventory Value</span>
              <span className="hero-value">{formatCurrency(stock.total_stock_value)}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Gross Margin</span>
              <span className="hero-value">{grossMargin.toFixed(1)}%</span>
            </div>
          </>
        ) : (
          <>
            <div className="hero-metric">
              <span className="hero-label">My Open Tasks</span>
              <span className="hero-value">{myTasks.filter((t) => t.status !== 'DONE').length}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Due Today</span>
              <span className="hero-value">{myTasks.filter((t) => t.status !== 'DONE' && t.date?.slice(0, 10) === today()).length}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Overdue</span>
              <span className="hero-value hero-warning">{myTasks.filter((t) => t.status !== 'DONE' && t.date?.slice(0, 10) < today()).length}</span>
            </div>
            <div className="hero-metric">
              <span className="hero-label">Blocked</span>
              <span className="hero-value">{myTasks.filter((t) => t.status === 'BLOCKED').length}</span>
            </div>
          </>
        )}
      </div>

      <h2 className="section-heading">Operations Snapshot</h2>
      <div className="secondary-metrics">
        {isPrivileged && <KpiCard label="Amount Received" value={formatCurrency(orders.total_received)} />}
        <KpiCard label="Active Orders" value={orders.active_orders} />
        <KpiCard label="Active Employees" value={staff.active_employees} />
        <KpiCard label="Pending Tasks" value={staff.pending_tasks} tone={staff.pending_tasks > 0 ? 'warning' : 'success'} />
        <KpiCard label="Completed Tasks" value={staff.completed_tasks} tone="success" />
      </div>

      <ProductionPipeline summary={staff.production_status_summary} />

      <section className="dashboard-section">
        <h2 className="section-heading">Attention Required</h2>
        <AttentionRequired
          stock={stock} orders={orders} pendingTasks={pendingTasks}
          upcomingDeliveries={upcomingDeliveries} pendingPurchases={pendingPurchases} delayedProduction={delayedProduction}
        />
      </section>

      {followUps.length > 0 && (
        <section className="dashboard-section">
          <h2 className="section-heading">Client Follow-ups Due</h2>
          <Card>
            {followUps.map((f) => (
              <div className="follow-up-row" key={f.id}>
                <div>
                  <span
                    className="btn-link" onClick={() => navigate(`/clients/${f.client_id}`)}
                    style={{ fontWeight: 600, cursor: 'pointer' }}
                  >
                    {f.client_name || f.client_code}
                  </span>
                  {' \u2014 '}{f.summary}
                  <span className={f.overdue ? 'follow-up-overdue' : ''} style={{ marginLeft: 8 }}>
                    ({new Date(f.follow_up_date).toLocaleDateString()}{f.overdue ? ', overdue' : ''})
                  </span>
                </div>
                <span />
                <button className="btn-secondary" onClick={() => handleCompleteFollowUp(f.id)}>Mark Done</button>
              </div>
            ))}
          </Card>
        </section>
      )}

      <section className="dashboard-section">
        <h2 className="section-heading">Business at a Glance</h2>
        <div className="dashboard-grid">
          <Card title="Order Pipeline">
            <SimpleBarChart data={orders.order_pipeline} labelKey="status" valueKey="orders" />
          </Card>
          <Card title="Stock Value by Category">
            <SimpleBarChart data={stock.category_summary} labelKey="category" valueKey="stock_value" formatValue={formatCurrency} />
          </Card>
          <Card title="Top Orders & Payment Position">
            <Table
              columns={[
                { key: 'order_id', label: 'Order' }, { key: 'client', label: 'Client' },
                { key: 'pending', label: 'Pending', render: formatCurrency }, { key: 'status', label: 'Status' },
              ]}
              data={orders.top_orders.slice(0, 5)}
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
