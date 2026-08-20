import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { analyticsAPI, reportsAPI } from '../utils/api';
import Card from '../components/common/Card';
import KpiCard from '../components/common/KpiCard';
import Table from '../components/common/Table';
import SimpleBarChart from '../components/common/SimpleBarChart';
import { formatCurrency, formatPercent } from '../utils/currency';

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
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.sales(6).then((r) => setData(r.data)); }, []);
  if (!isPrivileged) return <Card><div className="card-body">Sales & revenue analytics are available to master accounts only.</div></Card>;
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
              { key: 'balance', label: 'Outstanding', render: formatCurrency },
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
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.inventory().then((r) => setData(r.data)); }, []);
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
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.purchases(6).then((r) => setData(r.data)); }, []);
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
            { key: 'material', label: 'Material' }, { key: 'invoice_total', label: 'Amount', render: formatCurrency },
            { key: 'payment_status', label: 'Status' },
          ]}
          data={data.pending_purchases}
        />
      </Card>
    </>
  );
}

function ProductionTab() {
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.production().then((r) => setData(r.data)); }, []);
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
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.projects().then((r) => setData(r.data)); }, []);
  if (!data) return <div className="card-body">Loading...</div>;
  return (
    <>
      <AlertList alerts={data.alerts} />
      <div className="secondary-metrics">
        <KpiCard label="Total Projects" value={data.total_projects} />
        <KpiCard label="On Hold / Stalled" value={data.on_hold_count + data.stalled_count} tone={data.on_hold_count + data.stalled_count > 0 ? 'warning' : 'success'} />
        {isPrivileged && <KpiCard label="Overall Gross Margin" value={data.overall_gross_margin_percent === null ? 'N/A' : formatPercent(data.overall_gross_margin_percent)} />}
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
              { key: 'order_value', label: 'Order Value', render: formatCurrency },
              { key: 'estimated_gross_profit', label: 'Gross Profit', render: formatCurrency },
              { key: 'gross_margin_percent', label: 'Margin', render: (v) => formatPercent(v * 100) },
            ]}
            data={data.order_profitability}
          />
        </Card>
      )}
    </>
  );
}

function TasksTab() {
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.tasks().then((r) => setData(r.data)); }, []);
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
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.payments(6).then((r) => setData(r.data)); }, []);
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
            { key: 'client', label: 'Client' }, { key: 'amount', label: 'Amount', render: formatCurrency },
            { key: 'mode', label: 'Mode' },
          ]}
          data={data.recent_payments}
        />
      </Card>
    </>
  );
}

function ExpensesTab() {
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.expenses(6).then((r) => setData(r.data)); }, []);
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
            { key: 'category', label: 'Category' }, { key: 'last_month', label: 'Last Month', render: formatCurrency },
            { key: 'this_month', label: 'This Month', render: formatCurrency },
            { key: 'delta', label: 'Change', render: formatCurrency },
          ]}
          data={data.category_change_this_month}
        />
      </Card>
      <Card title="Recent Expenses" actions={<ExcelButton href={reportsAPI.downloadUrl('project-expenses.xlsx')} />}>
        <Table
          columns={[
            { key: 'expense_id', label: 'Expense' }, { key: 'order', label: 'Order' },
            { key: 'category', label: 'Category' }, { key: 'amount', label: 'Amount', render: formatCurrency },
            { key: 'paid_to', label: 'Paid To' },
          ]}
          data={data.recent_expenses}
        />
      </Card>
    </>
  );
}

function WorkforceTab({ isPrivileged }) {
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.workforce().then((r) => setData(r.data)); }, []);
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
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.operations().then((r) => setData(r.data)); }, []);
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
  const [data, setData] = useState(null);
  useEffect(() => { analyticsAPI.whatsChanged().then((r) => setData(r.data)); }, []);
  if (!data) return null;
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

export default AnalyticsPage;
