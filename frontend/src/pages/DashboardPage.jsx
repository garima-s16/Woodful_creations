import React, { useEffect, useState } from 'react';
import { dashboardAPI } from '../utils/api';
import KpiCard from '../components/common/KpiCard';
import Card from '../components/common/Card';
import Table from '../components/common/Table';

function StockDashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    dashboardAPI.stock().then((res) => setData(res.data)).catch(() => setData(null));
  }, []);

  if (!data) return <div>Loading...</div>;

  return (
    <div className="dashboard-tab">
      <div className="kpi-row">
        <KpiCard label="Total Stock Value" value={`Rs ${data.total_stock_value.toLocaleString()}`} />
        <KpiCard label="Low Stock Items" value={data.low_stock_items} tone={data.low_stock_items > 0 ? 'warning' : 'success'} />
        <KpiCard label="Out of Stock" value={data.out_of_stock_items} tone={data.out_of_stock_items > 0 ? 'danger' : 'success'} />
        <KpiCard label="Purchase Value" value={`Rs ${data.purchase_value.toLocaleString()}`} />
      </div>
      <div className="dashboard-grid">
        <Card title="Low Stock Action List">
          <Table
            columns={[
              { key: 'material', label: 'Material' }, { key: 'current', label: 'Current' },
              { key: 'minimum', label: 'Minimum' }, { key: 'status', label: 'Status' },
              { key: 'suggested_order', label: 'Suggested Order' }, { key: 'supplier', label: 'Supplier' },
            ]}
            data={data.low_stock_action_list}
          />
        </Card>
        <Card title="Category Summary">
          <Table
            columns={[
              { key: 'category', label: 'Category' }, { key: 'items', label: 'Items' },
              { key: 'stock_quantity', label: 'Stock Qty' },
              { key: 'stock_value', label: 'Stock Value', render: (v) => `Rs ${v.toLocaleString()}` },
            ]}
            data={data.category_summary}
          />
        </Card>
      </div>
    </div>
  );
}

function OrdersDashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    dashboardAPI.orders().then((res) => setData(res.data)).catch(() => setData(null));
  }, []);

  if (!data) return <div>Loading...</div>;

  return (
    <div className="dashboard-tab">
      <div className="kpi-row">
        <KpiCard label="Total Order Value" value={`Rs ${data.total_order_value.toLocaleString()}`} />
        <KpiCard label="Total Received" value={`Rs ${data.total_received.toLocaleString()}`} tone="success" />
        <KpiCard label="Pending Payment" value={`Rs ${data.pending_payment.toLocaleString()}`} tone="warning" />
        <KpiCard label="Active Orders" value={data.active_orders} />
      </div>
      <div className="dashboard-grid">
        <Card title="Order Pipeline">
          <Table columns={[{ key: 'status', label: 'Status' }, { key: 'orders', label: 'Orders' }]} data={data.order_pipeline} />
        </Card>
        <Card title="Top Orders & Payment Position">
          <Table
            columns={[
              { key: 'order_id', label: 'Order ID' }, { key: 'client', label: 'Client' },
              { key: 'order_value', label: 'Order Value', render: (v) => `Rs ${v.toLocaleString()}` },
              { key: 'received', label: 'Received', render: (v) => `Rs ${v.toLocaleString()}` },
              { key: 'pending', label: 'Pending', render: (v) => `Rs ${v.toLocaleString()}` },
              { key: 'progress', label: 'Progress %' }, { key: 'status', label: 'Status' },
            ]}
            data={data.top_orders}
          />
        </Card>
      </div>
      <Card title="Order Profitability">
        <Table
          columns={[
            { key: 'order_id', label: 'Order ID' }, { key: 'client', label: 'Client' },
            { key: 'order_value', label: 'Sales', render: (v) => `Rs ${v.toLocaleString()}` },
            { key: 'project_expenses', label: 'Expenses', render: (v) => `Rs ${v.toLocaleString()}` },
            { key: 'estimated_gross_profit', label: 'Gross Profit', render: (v) => `Rs ${v.toLocaleString()}` },
            { key: 'gross_margin_percent', label: 'Margin %', render: (v) => `${(v * 100).toFixed(1)}%` },
            { key: 'status', label: 'Status' },
          ]}
          data={data.order_profitability}
        />
      </Card>
    </div>
  );
}

function StaffDashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    dashboardAPI.staff().then((res) => setData(res.data)).catch(() => setData(null));
  }, []);

  if (!data) return <div>Loading...</div>;

  return (
    <div className="dashboard-tab">
      <div className="kpi-row">
        <KpiCard label="Active Employees" value={data.active_employees} />
        <KpiCard label="Pending Tasks" value={data.pending_tasks} tone="warning" />
        <KpiCard label="Completed Tasks" value={data.completed_tasks} tone="success" />
        <KpiCard label="Total Overtime (hrs)" value={data.total_overtime} />
      </div>
      <div className="dashboard-grid">
        <Card title="Task Status Summary">
          <Table columns={[{ key: 'status', label: 'Status' }, { key: 'count', label: 'Count' }]} data={data.task_status_summary} />
        </Card>
        <Card title="Employee Performance">
          <Table
            columns={[
              { key: 'employee', label: 'Employee' }, { key: 'department', label: 'Department' },
              { key: 'tasks', label: 'Tasks' }, { key: 'completed', label: 'Completed' },
              { key: 'completion_percent', label: 'Completion %', render: (v) => `${(v * 100).toFixed(0)}%` },
              { key: 'hours', label: 'Hours' }, { key: 'overtime', label: 'Overtime' },
            ]}
            data={data.employee_performance}
          />
        </Card>
      </div>
    </div>
  );
}

function DashboardPage() {
  const [tab, setTab] = useState('stock');

  return (
    <div className="page">
      <h1>Dashboard</h1>
      <div className="tab-bar">
        <button className={tab === 'stock' ? 'tab active' : 'tab'} onClick={() => setTab('stock')}>Stock</button>
        <button className={tab === 'orders' ? 'tab active' : 'tab'} onClick={() => setTab('orders')}>Orders & Sales</button>
        <button className={tab === 'staff' ? 'tab active' : 'tab'} onClick={() => setTab('staff')}>Staff & Tasks</button>
      </div>
      {tab === 'stock' && <StockDashboard />}
      {tab === 'orders' && <OrdersDashboard />}
      {tab === 'staff' && <StaffDashboard />}
    </div>
  );
}

export default DashboardPage;
