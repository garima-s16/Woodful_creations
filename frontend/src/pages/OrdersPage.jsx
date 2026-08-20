import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { ordersAPI, clientsAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { formatCurrency } from '../utils/currency';
import { statusClass } from '../utils/statusColors';
import Pagination from '../components/common/Pagination';

const PAGE_SIZE = 25;

const STAGE_OPTIONS = ['Enquiry', 'Designing', 'Approved', 'Material Purchase', 'Cutting', 'Edge Banding',
  'Assembly', 'Painting', 'Ready for Dispatch', 'Installation', 'Completed', 'On Hold']
  .map((s) => ({ value: s, label: s }));
const SIMPLE_STATUS_OPTIONS = ['Pending', 'In Progress', 'Completed'].map((s) => ({ value: s, label: s }));
const PRIORITY_OPTIONS = ['Low', 'Medium', 'High', 'Urgent'].map((s) => ({ value: s, label: s }));

function OrdersPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [orders, setOrders] = useState([]);
  const [clients, setClients] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [statusOrder, setStatusOrder] = useState(null);
  const [editingOrder, setEditingOrder] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const activeFilters = () => {
    const params = {};
    if (statusFilter) params.status = statusFilter;
    if (overdueOnly) params.overdue_only = true;
    return params;
  };

  const load = (filterParams, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    setPageLoading(true);
    ordersAPI.list({ ...filterParams, limit: PAGE_SIZE, offset }).then((res) => {
      setOrders(res.data);
      setTotalCount(Number(res.headers['x-total-count'] || res.data.length));
    }).finally(() => setPageLoading(false));
    clientsAPI.list().then((res) => setClients(res.data));
  };

  useEffect(() => {
    load(activeFilters());
  }, []);

  const applyFilters = (nextStatus, nextOverdue) => {
    const params = {};
    if (nextStatus) params.status = nextStatus;
    if (nextOverdue) params.overdue_only = true;
    setPage(1);
    load(params, 1);
  };

  const handleFilterChange = (e) => {
    const value = e.target.value;
    setStatusFilter(value);
    applyFilters(value, overdueOnly);
  };

  const handleOverdueChange = (e) => {
    const checked = e.target.checked;
    setOverdueOnly(checked);
    applyFilters(statusFilter, checked);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(activeFilters(), pageNum);
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await ordersAPI.create({
        ...formData,
        client_id: Number(formData.client_id),
        order_date: new Date(formData.order_date).toISOString(),
        delivery_date: formData.delivery_date ? new Date(formData.delivery_date).toISOString() : null,
        order_value: formData.order_value || '0',
        advance: formData.advance || '0',
      });
      setShowAdd(false);
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create order');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await ordersAPI.update(statusOrder.id, {
        project_status: formData.project_status,
        design_status: formData.design_status,
        execution_status: formData.execution_status,
        delivery_status: formData.delivery_status,
        progress_percent: Number(formData.progress_percent),
      });
      setStatusOrder(null);
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update status');
    } finally {
      setLoading(false);
    }
  };

  const handleDetailsUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await ordersAPI.update(editingOrder.id, {
        project_type: formData.project_type,
        order_value: formData.order_value,
        delivery_date: formData.delivery_date ? new Date(formData.delivery_date).toISOString() : null,
        priority: formData.priority,
        supervisor: formData.supervisor,
        site_address: formData.site_address,
        remarks: formData.remarks,
      });
      setEditingOrder(null);
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update order');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'order_code', label: 'Order ID' },
    { key: 'client_id', label: 'Client', render: (v) => clients.find((c) => c.id === v)?.name || v },
    { key: 'project_type', label: 'Project Type' },
    { key: 'order_value', label: 'Order Value', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'total_received', label: 'Received', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'balance', label: 'Balance', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'payment_status', label: 'Payment Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
    { key: 'project_status', label: 'Stage' }, { key: 'progress_percent', label: 'Progress %' },
    { key: 'design_status', label: 'Design' }, { key: 'execution_status', label: 'Execution' },
    { key: 'delivery_status', label: 'Delivery' },
    {
      key: 'estimate_pdf', label: 'Estimate', render: (v, row) => (
        <a href={reportsAPI.downloadUrl(`orders/${row.id}/estimate.pdf`)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>Download PDF</a>
      ),
    },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingOrder(row); }}>Edit Details</button> : null
      ),
    },
    {
      key: 'status_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={(e) => { e.stopPropagation(); setStatusOrder(row); }}>Update Status</button>
      ),
    },
  ];

  const createFields = [
    { name: 'client_id', label: 'Client', type: 'select', required: true, section: 'Client & Project', options: clients.map((c) => ({ value: c.id, label: c.name })) },
    { name: 'project_type', label: 'Project Type', section: 'Client & Project' },
    { name: 'order_value', label: 'Order Value', type: 'number', required: true, section: 'Commercial' },
    { name: 'advance', label: 'Advance', type: 'number', section: 'Commercial' },
    { name: 'order_date', label: 'Order Date', type: 'date', required: true, section: 'Schedule' },
    { name: 'delivery_date', label: 'Delivery Date', type: 'date', section: 'Schedule' },
    { name: 'priority', label: 'Priority', type: 'select', section: 'Schedule', options: PRIORITY_OPTIONS },
    { name: 'supervisor', label: 'Supervisor', section: 'Site & Supervisor' },
    { name: 'site_address', label: 'Site Address', type: 'textarea', section: 'Site & Supervisor' },
  ];

  const detailsFields = [
    { name: 'project_type', label: 'Project Type' },
    { name: 'order_value', label: 'Order Value', type: 'number', required: true },
    { name: 'delivery_date', label: 'Delivery Date', type: 'date' },
    { name: 'priority', label: 'Priority', type: 'select', options: PRIORITY_OPTIONS },
    { name: 'supervisor', label: 'Supervisor' },
    { name: 'site_address', label: 'Site Address', type: 'textarea' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Orders</h1>
          <p className="page-summary">Track every order from confirmation through delivery and payment.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('order-profitability.xlsx')} target="_blank" rel="noreferrer">
            Export Profitability
          </a>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>New Order</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <form className="page-search" onSubmit={(e) => e.preventDefault()}>
        <select className="form-input" value={statusFilter} onChange={handleFilterChange}>
          <option value="">All Stages</option>
          {STAGE_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
          <input type="checkbox" checked={overdueOnly} onChange={handleOverdueChange} />
          Balance outstanding 30+ days
        </label>
      </form>
      <Table columns={columns} data={orders} loading={pageLoading} onRowClick={(row) => navigate(`/orders/${row.id}`)} emptyMessage="No orders yet. Create your first order to get started." />
      {totalCount > PAGE_SIZE && (
        <Pagination
          currentPage={page}
          totalPages={Math.ceil(totalCount / PAGE_SIZE)}
          onPageChange={goToPage}
        />
      )}
      <Modal isOpen={showAdd} title="New Order" onClose={() => setShowAdd(false)}>
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Create Order" />
      </Modal>

      <Modal isOpen={!!editingOrder} title={`Edit Order - ${editingOrder?.order_code || ''}`} onClose={() => setEditingOrder(null)}>
        {editingOrder && (
          <Form
            fields={detailsFields}
            onSubmit={handleDetailsUpdate}
            loading={loading}
            submitText="Save Changes"
            initialValues={{
              project_type: editingOrder.project_type, order_value: editingOrder.order_value,
              delivery_date: editingOrder.delivery_date ? editingOrder.delivery_date.slice(0, 10) : '',
              priority: editingOrder.priority, supervisor: editingOrder.supervisor,
              site_address: editingOrder.site_address, remarks: editingOrder.remarks,
            }}
          />
        )}
      </Modal>

      <Modal isOpen={!!statusOrder} title={`Update Status - ${statusOrder?.order_code || ''}`} onClose={() => setStatusOrder(null)}>
        {statusOrder && (
          <Form
            fields={[
              { name: 'project_status', label: 'Overall Stage', type: 'select', required: true, options: STAGE_OPTIONS },
              { name: 'design_status', label: 'Design Status', type: 'select', required: true, options: SIMPLE_STATUS_OPTIONS },
              { name: 'execution_status', label: 'Execution Status', type: 'select', required: true, options: SIMPLE_STATUS_OPTIONS },
              { name: 'delivery_status', label: 'Delivery Status', type: 'select', required: true, options: SIMPLE_STATUS_OPTIONS },
              { name: 'progress_percent', label: 'Progress %', type: 'number', required: true },
            ]}
            onSubmit={handleStatusUpdate}
            loading={loading}
            submitText="Update Status"
            initialValues={{
              project_status: statusOrder.project_status,
              design_status: statusOrder.design_status,
              execution_status: statusOrder.execution_status,
              delivery_status: statusOrder.delivery_status,
              progress_percent: statusOrder.progress_percent,
            }}
          />
        )}
      </Modal>
    </div>
  );
}

export default OrdersPage;
