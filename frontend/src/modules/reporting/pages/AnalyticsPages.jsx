// Reporting analytics pages: analytics dashboard and business-
// decision centre. Combines the former AnalyticsPage.jsx and
// BusinessDecisionCentrePage.jsx. DashboardPage.jsx remains separate.
import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { analyticsAPI, businessDecisionsAPI, dashboardAPI, reportsAPI } from '../../../utils/api';
import { Alert, Card, KpiCard, SimpleBarChart, Table } from '../../../components/common/UI';
import { formatCurrency, formatPercent } from '../../../utils/utils';

// --- AnalyticsPage.jsx ---
function useAnalyticsFetch(fetchFn) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [retryKey, setRetryKey] = useState(0);
  useEffect(() => {
    setError('');
    fetchFn().then((r) => setData(r.data)).catch(() => setError('Unable to load this data. Please try again.'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retryKey]);
  return { data, error, retry: () => setRetryKey((k) => k + 1) };
}

function AnalyticsErrorState({ error, onRetry }) {
  return (
    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
      <span style={{ color: 'var(--text-secondary)' }}>{error}</span>
      <button className="btn-secondary" onClick={onRetry}>Try Again</button>
    </div>
  );
}

const TABS_MASTER = ['Sales & Revenue', 'Inventory', 'Purchases', 'Production', 'Projects', 'Tasks',
  'Payments', 'Expenses', 'Workforce', 'Operations'];
const TABS_USER = ['Inventory', 'Production', 'Projects', 'Tasks', 'Workforce', 'Operations'];

function AlertList({ alerts, onNavigate }) {
  if (!alerts || alerts.length === 0) return null;
  return (
    <Card title="Alerts">
      <div className="card-body attention-grid">
        <div className="attention-column" style={{ width: '100%' }}>
          {alerts.map((a, i) => (
            <button
              key={i}
              className="attention-item"
              onClick={() => onNavigate && onNavigate(a.drill_down)}
              style={{ width: '100%' }}
            >
              <span>{a.message}</span>
              <span className={`status-badge ${a.severity === 'critical' ? 'status-danger' : 'status-warning'}`}>
                {a.severity}
              </span>
            </button>
          ))}
        </div>
      </div>
    </Card>
  );
}

function TrendChart({ title, data, valueKey = 'value', labelKey = 'month', formatValue = formatCurrency }) {
  return (
    <Card title={title}>
      <SimpleBarChart data={data} labelKey={labelKey} valueKey={valueKey} formatValue={formatValue} />
    </Card>
  );
}

function ExcelButton({ href, label = 'Export Excel' }) {
  return (
    <a className="btn-secondary" href={href} target="_blank" rel="noreferrer">{label}</a>
  );
}

function SalesTab({ isPrivileged }) {
  const navigate = useNavigate();
  const { data, error, retry } = useAnalyticsFetch(() => analyticsAPI.sales(6));
  if (!isPrivileged) return <Card><div className="card-body">Sales & revenue analytics are available to master accounts only.</div></Card>;
  if (error) return <Card><AnalyticsErrorState error={error} onRetry={retry} /></Card>;
  if (!data) return <div className="card-body">Loading...</div>;

  const scrollToOutstanding = (drill) => {
    if (drill === 'outstanding_orders') document.getElementById('outstanding-orders-table')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <>
      <AlertList alerts={data.alerts} onNavigate={scrollToOutstanding} />
      <div className="secondary-metrics">
        <KpiCard label="Total Order Value" value={formatCurrency(data.total_order_value)} />
        <KpiCard label="Total Received" value={formatCurrency(data.total_received)} />
        <KpiCard label="Outstanding" value={formatCurrency(data.total_outstanding)} tone={data.total_outstanding > 0 ? 'warning' : 'success'} />
        <KpiCard
          label="Revenue vs Last Month"
          value={data.revenue_change_percent === null ? 'N/A' : formatPercent(data.revenue_change_percent)}
          tone={data.revenue_change_percent < 0 ? 'warning' : 'success'}
        />
      </div>
      <div className="dashboard-grid">
        <TrendChart title="Sales Trend (Orders Booked)" data={data.sales_trend} labelKey="month" />
        <TrendChart title="Revenue Trend (Payments Received)" data={data.revenue_trend} labelKey="month" />
        <Card title="Outstanding by Client">
          <SimpleBarChart data={data.outstanding_by_client} labelKey="client" valueKey="amount" formatValue={formatCurrency} />
        </Card>
        <Card title="Outstanding Aging">
          <SimpleBarChart data={data.aging_buckets} labelKey="bucket" valueKey="amount" formatValue={formatCurrency} />
        </Card>
      </div>
      <Card title="Outstanding Orders (Drill-Down)" actions={<ExcelButton href={reportsAPI.downloadUrl('orders.xlsx')} />}>
        <div id="outstanding-orders-table">
          <Table
            columns={[
              { key: 'order_id', label: 'Order' }, { key: 'client', label: 'Client' },
              { key: 'balance', label: 'Outstanding', render: formatCurrency, align: 'right' },
              { key: 'status', label: 'Status' },
            ]}
            data={data.outstanding_orders}
            onRowClick={(row) => navigate(`/orders/${row.id}`)}
          />
        </div>
      </Card>
    </>
  );
}

function InventoryTab({ isPrivileged }) {
  const navigate = useNavigate();
  const { data, error, retry } = useAnalyticsFetch(() => analyticsAPI.inventory());
  if (error) return <AnalyticsErrorState error={error} onRetry={retry} />;
  if (!data) return <div className="card-body">Loading...</div>;
  return (
    <>
      <AlertList alerts={data.alerts} />
      <div className="secondary-metrics">
        <KpiCard label="Total Materials" value={data.total_materials} />
        <KpiCard label="Low Stock Items" value={data.low_stock_count} tone={data.low_stock_count > 0 ? 'warning' : 'success'} />
        <KpiCard label="Out of Stock" value={data.out_of_stock_count} tone={data.out_of_stock_count > 0 ? 'danger' : 'success'} />
        {isPrivileged && <KpiCard label="Total Stock Value" value={formatCurrency(data.total_stock_value)} />}
      </div>
      <div className="dashboard-grid">
        <Card title="Stock Value by Category">
          <SimpleBarChart
            data={data.category_breakdown} labelKey="category" valueKey="stock_value"
            formatValue={isPrivileged ? formatCurrency : (() => 'Restricted')}
          />
        </Card>
      </div>
      <Card title="Low / Out of Stock Materials (Drill-Down)" actions={<ExcelButton href={reportsAPI.downloadUrl('stock-dashboard.xlsx')} />}>
        <Table
          columns={[
            { key: 'material', label: 'Material' }, { key: 'current_stock', label: 'Current' },
            { key: 'minimum_stock', label: 'Minimum' }, { key: 'suggested_order', label: 'Suggested Order' },
            { key: 'supplier', label: 'Supplier' },
          ]}
          data={data.low_stock_materials}
          onRowClick={(row) => navigate(`/materials/${row.id}`)}
        />
      </Card>
    </>
  );
}

function PurchasesTab() {
  const { data, error, retry } = useAnalyticsFetch(() => analyticsAPI.purchases(6));
  if (error) return <AnalyticsErrorState error={error} onRetry={retry} />;
  if (!data) return <div className="card-body">Loading...</div>;
  return (
    <>
      <AlertList alerts={data.alerts} />
      <div className="secondary-metrics">
        <KpiCard label="Total Purchase Value" value={formatCurrency(data.total_purchase_value)} />
        <KpiCard label="Pending Payment" value={data.pending_payment_count} tone={data.pending_payment_count > 0 ? 'warning' : 'success'} />
        <KpiCard label="Pending Value" value={formatCurrency(data.pending_payment_value)} />
      </div>
      <div className="dashboard-grid">
        <TrendChart title="Purchase Trend" data={data.purchase_trend} labelKey="month" />
        <Card title="Top Suppliers by Spend">
          <SimpleBarChart data={data.top_suppliers_by_spend} labelKey="supplier" valueKey="amount" formatValue={formatCurrency} />
        </Card>
      </div>
      <Card title="Purchases Pending Payment (Drill-Down)" actions={<ExcelButton href={reportsAPI.downloadUrl('purchases.xlsx')} />}>
        <Table
          columns={[
            { key: 'purchase_id', label: 'Purchase' }, { key: 'supplier', label: 'Supplier' },
            { key: 'material', label: 'Material' }, { key: 'invoice_total', label: 'Amount', render: formatCurrency, align: 'right' },
            { key: 'payment_status', label: 'Status' },
          ]}
          data={data.pending_purchases}
        />
      </Card>
    </>
  );
}

function ProductionTab() {
  const { data, error, retry } = useAnalyticsFetch(() => analyticsAPI.production());
  if (error) return <AnalyticsErrorState error={error} onRetry={retry} />;
  if (!data) return <div className="card-body">Loading...</div>;
  return (
    <>
      <AlertList alerts={data.alerts} />
      <div className="secondary-metrics">
        <KpiCard label="Total Jobs" value={data.total_jobs} />
        <KpiCard label="Blocked" value={data.blocked_count} tone={data.blocked_count > 0 ? 'danger' : 'success'} />
        <KpiCard label="Open 7+ Days" value={data.open_7_plus_days_count} tone={data.open_7_plus_days_count > 0 ? 'warning' : 'success'} />
      </div>
      <div className="dashboard-grid">
        <Card title="Status Summary">
          <SimpleBarChart data={data.status_summary} labelKey="status" valueKey="count" />
        </Card>
        <Card title="Throughput by Stage (Completed Qty)">
          <SimpleBarChart data={data.stage_throughput} labelKey="stage" valueKey="completed_qty" />
        </Card>
      </div>
      <Card title="Blocked / Delayed Jobs (Drill-Down)" actions={<ExcelButton href={reportsAPI.downloadUrl('production.xlsx')} />}>
        <Table
          columns={[
            { key: 'job_id', label: 'Job' }, { key: 'operation', label: 'Operation' },
            { key: 'order', label: 'Order' }, { key: 'blocker_reason', label: 'Blocker / Status' },
          ]}
          data={[...data.blocked_jobs, ...data.delayed_jobs]}
        />
      </Card>
    </>
  );
}

function ProjectsTab({ isPrivileged }) {
  const navigate = useNavigate();
  const { data, error, retry } = useAnalyticsFetch(() => analyticsAPI.projects());
  if (error) return <AnalyticsErrorState error={error} onRetry={retry} />;
  if (!data) return <div className="card-body">Loading...</div>;
  return (
    <>
      <AlertList alerts={data.alerts} />
      <div className="secondary-metrics">
        <KpiCard label="Total Projects" value={data.total_projects} />
        <KpiCard label="On Hold / Stalled" value={data.on_hold_count + data.stalled_count} tone={data.on_hold_count + data.stalled_count > 0 ? 'warning' : 'success'} />
        {isPrivileged && <KpiCard label="Overall Gross Margin" value={data.overall_gross_margin_ratio === null ? 'N/A' : formatPercent(data.overall_gross_margin_ratio * 100)} />}
      </div>
      <div className="dashboard-grid">
        <Card title="Status Summary">
          <SimpleBarChart data={data.status_summary} labelKey="status" valueKey="count" />
        </Card>
      </div>
      <Card title="Delayed Projects (Drill-Down)" actions={<ExcelButton href={reportsAPI.downloadUrl('orders.xlsx')} />}>
        <Table
          columns={[
            { key: 'order_id', label: 'Order' }, { key: 'client', label: 'Client' },
            { key: 'status', label: 'Status' }, { key: 'progress_percent', label: 'Progress %' },
          ]}
          data={data.delayed_projects}
          onRowClick={(row) => navigate(`/orders/${row.id}`)}
        />
      </Card>
      {isPrivileged && data.order_profitability.length > 0 && (
        <Card title="Order Profitability" actions={<ExcelButton href={reportsAPI.downloadUrl('order-profitability.xlsx')} />}>
          <Table
            columns={[
              { key: 'order_id', label: 'Order' }, { key: 'client', label: 'Client' },
              { key: 'order_value', label: 'Order Value', render: formatCurrency, align: 'right' },
              { key: 'estimated_gross_profit', label: 'Gross Profit', render: formatCurrency, align: 'right' },
              { key: 'gross_margin_ratio', label: 'Margin', render: (v) => formatPercent(v * 100), align: 'right' },
            ]}
            data={data.order_profitability}
          />
        </Card>
      )}
    </>
  );
}

function TasksTab() {
  const { data, error, retry } = useAnalyticsFetch(() => analyticsAPI.tasks());
  if (error) return <AnalyticsErrorState error={error} onRetry={retry} />;
  if (!data) return <div className="card-body">Loading...</div>;
  return (
    <>
      <AlertList alerts={data.alerts} />
      <div className="secondary-metrics">
        <KpiCard label="Total Tasks" value={data.total_tasks} />
        <KpiCard label="Completion Rate" value={formatPercent(data.completion_rate_percent)} tone="success" />
        <KpiCard label="Overdue" value={data.overdue_count} tone={data.overdue_count > 0 ? 'warning' : 'success'} />
      </div>
      <div className="dashboard-grid">
        <Card title="Status Summary">
          <SimpleBarChart data={data.status_summary} labelKey="status" valueKey="count" />
        </Card>
      </div>
      <Card title="Overdue Tasks (Drill-Down)" actions={<ExcelButton href={reportsAPI.downloadUrl('tasks.xlsx')} />}>
        <Table
          columns={[
            { key: 'task', label: 'Task' }, { key: 'employee', label: 'Employee' },
            { key: 'order', label: 'Order' }, { key: 'status', label: 'Status' },
          ]}
          data={data.overdue_tasks}
        />
      </Card>
    </>
  );
}

function PaymentsTab() {
  const { data, error, retry } = useAnalyticsFetch(() => analyticsAPI.payments(6));
  if (error) return <AnalyticsErrorState error={error} onRetry={retry} />;
  if (!data) return <div className="card-body">Loading...</div>;
  return (
    <>
      <div className="secondary-metrics">
        <KpiCard label="Total Payments" value={data.total_payments} />
        <KpiCard label="Total Amount" value={formatCurrency(data.total_amount)} />
      </div>
      <div className="dashboard-grid">
        <TrendChart title="Payment Trend" data={data.payment_trend} labelKey="month" />
        <Card title="By Payment Type">
          <SimpleBarChart data={data.by_payment_type} labelKey="type" valueKey="amount" formatValue={formatCurrency} />
        </Card>
      </div>
      <Card title="Recent Payments" actions={<ExcelButton href={reportsAPI.downloadUrl('payments.xlsx')} />}>
        <Table
          columns={[
            { key: 'receipt_id', label: 'Receipt' }, { key: 'order', label: 'Order' },
            { key: 'client', label: 'Client' }, { key: 'amount', label: 'Amount', render: formatCurrency, align: 'right' },
            { key: 'mode', label: 'Mode' },
          ]}
          data={data.recent_payments}
        />
      </Card>
    </>
  );
}

function ExpensesTab() {
  const { data, error, retry } = useAnalyticsFetch(() => analyticsAPI.expenses(6));
  if (error) return <AnalyticsErrorState error={error} onRetry={retry} />;
  if (!data) return <div className="card-body">Loading...</div>;
  return (
    <>
      <AlertList alerts={data.alerts} />
      <div className="secondary-metrics">
        <KpiCard label="Total Expenses" value={formatCurrency(data.total_expenses)} />
        <KpiCard
          label="vs Last Month"
          value={data.expense_change_percent === null ? 'N/A' : formatPercent(data.expense_change_percent)}
          tone={data.expense_change_percent > 0 ? 'warning' : 'success'}
        />
      </div>
      <div className="dashboard-grid">
        <TrendChart title="Expense Trend" data={data.expense_trend} labelKey="month" />
        <Card title="By Category">
          <SimpleBarChart data={data.by_category} labelKey="category" valueKey="amount" formatValue={formatCurrency} />
        </Card>
      </div>
      <Card title="Category Change This Month">
        <Table
          columns={[
            { key: 'category', label: 'Category' }, { key: 'last_month', label: 'Last Month', render: formatCurrency, align: 'right' },
            { key: 'this_month', label: 'This Month', render: formatCurrency, align: 'right' },
            { key: 'delta', label: 'Change', render: formatCurrency, align: 'right' },
          ]}
          data={data.category_change_this_month}
        />
      </Card>
      <Card title="Recent Expenses" actions={<ExcelButton href={reportsAPI.downloadUrl('project-expenses.xlsx')} />}>
        <Table
          columns={[
            { key: 'expense_id', label: 'Expense' }, { key: 'order', label: 'Order' },
            { key: 'category', label: 'Category' }, { key: 'amount', label: 'Amount', render: formatCurrency, align: 'right' },
            { key: 'paid_to', label: 'Paid To' },
          ]}
          data={data.recent_expenses}
        />
      </Card>
    </>
  );
}

function WorkforceTab({ isPrivileged }) {
  const { data, error, retry } = useAnalyticsFetch(() => analyticsAPI.workforce());
  if (error) return <AnalyticsErrorState error={error} onRetry={retry} />;
  if (!data) return <div className="card-body">Loading...</div>;
  return (
    <>
      <AlertList alerts={data.alerts} />
      <div className="secondary-metrics">
        <KpiCard label="Active Employees" value={data.active_employees} />
        <KpiCard label="Total Working Hours" value={data.total_working_hours} />
        <KpiCard label="Total Overtime" value={data.total_overtime_hours} />
      </div>
      <div className="dashboard-grid">
        <Card title="By Department">
          <SimpleBarChart data={data.by_department} labelKey="department" valueKey="count" />
        </Card>
      </div>
      <Card title={isPrivileged ? 'Employee Performance' : 'My Performance'} actions={<ExcelButton href={reportsAPI.downloadUrl('attendance.xlsx')} />}>
        <Table
          columns={[
            { key: 'employee', label: 'Employee' }, { key: 'department', label: 'Department' },
            { key: 'completion_percent', label: 'Completion %' }, { key: 'overdue', label: 'Overdue' },
            { key: 'hours', label: 'Hours' }, { key: 'overtime', label: 'Overtime' },
          ]}
          data={data.employee_performance}
        />
      </Card>
    </>
  );
}

function OperationsTab({ isPrivileged }) {
  const { data, error, retry } = useAnalyticsFetch(() => analyticsAPI.operations());
  if (error) return <AnalyticsErrorState error={error} onRetry={retry} />;
  if (!data) return <div className="card-body">Loading...</div>;
  return (
    <div className="secondary-metrics">
      <KpiCard label="Active Orders" value={data.active_orders} />
      <KpiCard label="Open Production Jobs" value={data.open_production_jobs} />
      <KpiCard label="Open Tasks" value={data.open_tasks} />
      <KpiCard label="Total Materials" value={data.total_materials} />
      <KpiCard label="Total Suppliers" value={data.total_suppliers} />
      <KpiCard label="Total Clients" value={data.total_clients} />
      <KpiCard label="Low Stock Items" value={data.low_stock_items} tone={data.low_stock_items > 0 ? 'warning' : 'success'} />
      <KpiCard label="Out of Stock" value={data.out_of_stock_items} tone={data.out_of_stock_items > 0 ? 'danger' : 'success'} />
      {isPrivileged && <KpiCard label="Total Stock Value" value={formatCurrency(data.total_stock_value)} />}
    </div>
  );
}

function WhatsChanged() {
  const { data, error } = useAnalyticsFetch(() => analyticsAPI.whatsChanged());
  if (error || !data) return null;
  return (
    <Card title="What Changed This Month">
      <div className="card-body">
        {data.summary_lines.map((line, i) => <p key={i} style={{ margin: '4px 0' }}>{line}</p>)}
      </div>
    </Card>
  );
}

function AnalyticsPage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const tabs = isPrivileged ? TABS_MASTER : TABS_USER;
  const [tab, setTab] = useState(tabs[0]);

  return (
    <div className="page">
      <div className="dashboard-header">
        <span className="dashboard-eyebrow">Woodful Creations</span>
        <h1>Analytics & Reporting</h1>
        <p className="dashboard-subtitle">Grounded in real Woodful records - every KPI here drills down to the underlying data.</p>
      </div>

      <WhatsChanged />

      <div className="tab-bar">
        {tabs.map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Sales & Revenue' && <SalesTab isPrivileged={isPrivileged} />}
      {tab === 'Inventory' && <InventoryTab isPrivileged={isPrivileged} />}
      {tab === 'Purchases' && <PurchasesTab />}
      {tab === 'Production' && <ProductionTab />}
      {tab === 'Projects' && <ProjectsTab isPrivileged={isPrivileged} />}
      {tab === 'Tasks' && <TasksTab />}
      {tab === 'Payments' && <PaymentsTab />}
      {tab === 'Expenses' && <ExpensesTab />}
      {tab === 'Workforce' && <WorkforceTab isPrivileged={isPrivileged} />}
      {tab === 'Operations' && <OperationsTab isPrivileged={isPrivileged} />}
    </div>
  );
}

// --- BusinessDecisionCentrePage.jsx ---
const SEVERITY_TONE = { CRITICAL: 'danger', HIGH: 'warning', MEDIUM: 'default', LOW: 'default' };
const SEVERITY_BADGE_CLASS = {
  CRITICAL: 'status-badge status-danger', HIGH: 'status-badge status-warning',
  MEDIUM: 'status-badge status-neutral', LOW: 'status-badge status-neutral',
};

function BusinessDecisionCentrePage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState('ALL');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    setError('');
    businessDecisionsAPI.list().then((res) => setData(res.data)).catch((err) => {
      setError(err.response?.status === 403 ? 'You do not have permission to view business decisions.' : 'Unable to load business decisions right now.');
    }).finally(() => setLoading(false));
  };
  useEffect(load, []);

  if (loading) return <div className="page"><p>Loading...</p></div>;

  const risks = data?.risks || [];
  const filteredRisks = filter === 'ALL' ? risks : risks.filter((r) => r.severity === filter);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Business Attention</h1>
      </div>
      {error && (
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <Alert type="error" message={error} onClose={() => setError('')} />
          {/* Defect repair (F138 P4.3): this primary list load had no
              retry affordance on failure - matching the loadError/Retry
              convention used elsewhere (e.g. ClientDetailPage, MaterialPages). */}
          <button type="button" className="btn-secondary" onClick={load}>Retry</button>
        </div>
      )}

      {data && (
        <div className="secondary-metrics" style={{ marginBottom: 'var(--space-5)' }}>
          <KpiCard label="Needs Attention" value={data.total} onClick={() => setFilter('ALL')} />
          <KpiCard label="Critical" value={data.counts.CRITICAL} tone="danger" onClick={() => setFilter('CRITICAL')} />
          <KpiCard label="High" value={data.counts.HIGH} tone="warning" onClick={() => setFilter('HIGH')} />
          <KpiCard label="Medium" value={data.counts.MEDIUM} onClick={() => setFilter('MEDIUM')} />
          <KpiCard label="Low" value={data.counts.LOW} onClick={() => setFilter('LOW')} />
        </div>
      )}

      <div className="page-actions" style={{ marginBottom: 'var(--space-4)' }}>
        {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => (
          <button
            key={s} type="button"
            className={filter === s ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setFilter(s)}
          >
            {s === 'ALL' ? 'All' : s.charAt(0) + s.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {filteredRisks.length === 0 ? (
        <Card>
          <div className="card-body" style={{ color: 'var(--text-secondary)' }}>
            {risks.length === 0 ? 'Nothing needs attention right now.' : 'No items match this filter.'}
          </div>
        </Card>
      ) : (
        filteredRisks.map((risk) => (
          <Card key={`${risk.entity_type}-${risk.entity_id}-${risk.risk_type}`} style={{ marginBottom: 'var(--space-4)' }}>
            <div className="card-body">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                <div>
                  <span className={SEVERITY_BADGE_CLASS[risk.severity] || 'status-badge'}>{risk.severity}</span>
                  <span style={{ marginLeft: 'var(--space-2)', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{risk.risk_type}</span>
                  <h3 style={{ marginTop: 'var(--space-2)', marginBottom: 0 }}>{risk.title}</h3>
                </div>
                {risk.action_path && (
                  <button type="button" className="btn-secondary" onClick={() => navigate(risk.action_path)}>
                    Review
                  </button>
                )}
              </div>
              <p style={{ marginTop: 'var(--space-3)' }}>{risk.reason}</p>
              {risk.business_impact && (
                <p style={{ color: 'var(--text-secondary)' }}><strong>Impact:</strong> {risk.business_impact}</p>
              )}
              {risk.recommended_action && (
                <p><strong>Recommended:</strong> {risk.recommended_action}</p>
              )}
            </div>
          </Card>
        ))
      )}
    </div>
  );
}

// --- OwnerBriefingPage.jsx ---
// Family 137, features 11 (Owner Daily/Weekly Business Briefing) and
// 12 (Forward Cash-Flow Forecast). Master-only - both endpoints are
// gated server-side; this page assumes the route itself is already
// restricted to master (see App.jsx), matching every other
// master-only page in this app.
function OwnerBriefingPage() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState('daily');
  const [briefing, setBriefing] = useState(null);
  const [cashFlow, setCashFlow] = useState(null);
  const [briefingError, setBriefingError] = useState('');
  const [cashFlowError, setCashFlowError] = useState('');
  const [loading, setLoading] = useState(true);

  // Defect repair (F138 P4.1): briefing and cash-flow forecast are two
  // independent widgets on this page (see the separate `{briefing &&
  // ...}` / `{cashFlow && ...}` sections below) - firing them through
  // one Promise.all meant either endpoint failing blanked the WHOLE
  // page with a single error, even when the other had already
  // succeeded. Each now loads and fails independently, same pattern
  // as DashboardPage's per-widget loading.
  const load = (p) => {
    setLoading(true);
    setBriefingError('');
    setCashFlowError('');
    let settled = 0;
    const markSettled = () => { settled += 1; if (settled === 2) setLoading(false); };
    dashboardAPI.ownerBriefing(p).then((res) => setBriefing(res.data))
      .catch((err) => setBriefingError(err.response?.status === 403 ? 'You do not have permission to view the owner briefing.' : 'Unable to load the owner briefing right now.'))
      .finally(markSettled);
    dashboardAPI.cashFlowForecast(p === 'weekly' ? 6 : 2).then((res) => setCashFlow(res.data))
      .catch((err) => setCashFlowError(err.response?.status === 403 ? 'You do not have permission to view the cash-flow forecast.' : 'Unable to load the cash-flow forecast right now.'))
      .finally(markSettled);
  };
  useEffect(() => { load(period); }, [period]);

  if (loading) return <div className="page"><p>Loading...</p></div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Owner Briefing</h1>
      </div>
      {briefingError && <Alert type="error" message={briefingError} onClose={() => setBriefingError('')} />}
      {cashFlowError && <Alert type="error" message={cashFlowError} onClose={() => setCashFlowError('')} />}

      <div className="page-actions" style={{ marginBottom: 'var(--space-4)' }}>
        {['daily', 'weekly'].map((p) => (
          <button key={p} type="button" className={period === p ? 'btn-primary' : 'btn-secondary'} onClick={() => setPeriod(p)}>
            {p === 'daily' ? 'Daily' : 'Weekly'}
          </button>
        ))}
      </div>

      {briefing && (
        <Card style={{ marginBottom: 'var(--space-4)' }}>
          <div className="card-body">
            <p style={{ fontSize: '1.05rem' }}>{briefing.headline}</p>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{briefing.note}</p>
          </div>
        </Card>
      )}

      {cashFlow && (
        <Card title="Cash and Collections" style={{ marginBottom: 'var(--space-4)' }}>
          <div className="card-body">
            <div className="secondary-metrics" style={{ marginBottom: 'var(--space-3)' }}>
              <KpiCard label="Overdue (Fact)" value={formatCurrency(cashFlow.overdue_total)} tone="danger" />
              <KpiCard label="Expected This Week (Prediction)" value={formatCurrency(cashFlow.weekly_buckets?.[0]?.expected_total || 0)} />
              <KpiCard label="Unscheduled (Forecast)" value={formatCurrency(cashFlow.forecast_total)} />
              <KpiCard label="Total Outstanding" value={formatCurrency(cashFlow.total_outstanding)} />
            </div>
            {cashFlow.exceptions?.length > 0 && (
              <div>
                <strong>Exceptions - expected but not yet received:</strong>
                <ul>
                  {cashFlow.exceptions.slice(0, 8).map((ex, i) => (
                    <li key={i}>
                      <button className="btn-link" onClick={() => navigate(`/orders/${ex.order_id}`)}>{ex.order_code}</button>
                      {': '}{ex.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>
      )}

      {briefing && briefing.sections.length === 0 && (
        <Card>
          <div className="card-body" style={{ color: 'var(--text-secondary)' }}>Nothing else needs attention right now.</div>
        </Card>
      )}

      {briefing && briefing.sections.map((section) => (
        <Card key={section.key} title={section.title} style={{ marginBottom: 'var(--space-4)' }}>
          <div className="card-body">
            {section.facts?.map((f, i) => <p key={`f${i}`}><span className="status-badge status-neutral">FACT</span> {f}</p>)}
            {section.predictions?.map((p, i) => <p key={`p${i}`}><span className="status-badge status-warning">PREDICTION</span> {p}</p>)}
            {section.recommendations?.map((r, i) => <p key={`r${i}`}><span className="status-badge status-ok">RECOMMENDATION</span> {r}</p>)}
            {section.items?.length > 0 && (
              <ul>
                {section.items.slice(0, 10).map((item, i) => (
                  <li key={i}>
                    {item.path ? <Link to={item.path}>{item.label || item.title}</Link> : (item.label || item.title)}
                    {item.sublabel ? ` - ${item.sublabel}` : ''}
                    {item.reason ? ` - ${item.reason}` : ''}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}

export { AnalyticsPage, BusinessDecisionCentrePage, OwnerBriefingPage };
